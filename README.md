# EasyCrypt × Agents — Project Notes

*Reinvent the Wheel Hack, Oct 17 2026. Research & verification done against primary sources (EasyCrypt source code, official READMEs); items marked ⚠️ are not yet tested against a built binary.*

## 1. What we're building

EasyCrypt is the standard tool for machine-checked cryptographic proofs (game-hopping style). Its only interface is the Emacs front-end (Proof General) — designed for a human's hands and eyes. An agent has **no endpoint to control it**: can't load a proof, step a tactic, or read the current goal programmatically.

We add that endpoint: an **MCP server** wrapping EasyCrypt's CLI, so any MCP-capable agent (Claude in our demo) can drive proofs end-to-end. A skill/prompt layer on top encodes proof strategy (which tactics to try, when to fire SMT solvers, how to recover from a failed step).

Why this fits the judging brief: the brief's list of bad-scientific-software traits names "no endpoints for agentic control" — our deliverable is literally that endpoint. Install pain (see §3) is itself evidence of the "needs reinventing" claim.

## 2. What EasyCrypt's CLI already gives us (verified in source, main branch 2026-10-17)

From `src/ecOptions.ml{,i}`, `src/ec.ml`, `src/ecTerminal.ml`:

```
easycrypt compile <file.ec>   # batch-check whole file; -trace saves goals/messages to .eco
easycrypt llm <file.ec>       # "LLM-friendly batch compilation" (upstream's own!)
    -lastgoals                #   on failure, pretty-print remaining goals to stdout
    -upto LINE[:COL]          #   check up to position, print goals there, exit 0
easycrypt cli [-emacs]        # interactive toplevel on stdin/stdout (what Proof General drives)
easycrypt config              # print detected provers/why3 config
easycrypt why3config          # (re)detect SMT solvers
```

- Output contract (`llm` mode): diagnostics → **stderr** as `[Severity] [file:LINE] message`; goals → **stdout**; exit 0 = accepted / upto reached, 1 = failure.
- Prover selection: repeated `-p <name>` flags.
- Interactive mode supports positional undo (`ecCommands.mli: val undo : int -> unit`).
- The existence of upstream's `llm` subcommand = maintainers already want this direction; we build the agent layer on top of their entry point.

## 3. Install (Ubuntu/Debian; macOS: `brew install opam gmp mpfr`)

Official method is opam (no official Docker image, no prebuilt binaries). Steps ✅ were run successfully in a container; ⚠️ steps are correct per README but our container's egress policy blocked the source downloads, so finish them on a normal network (hotel Wi-Fi, not necessarily venue Wi-Fi).

```bash
# ✅ system deps
sudo apt-get update && sudo apt-get install -y opam libgmp-dev libmpfr-dev

# ✅ init opam (if opam.ocaml.org is blocked, use the GitHub mirror form below)
opam init -y
# fallback: opam init -y --bare git+https://github.com/ocaml/opam-repository.git

# ✅ switch using the system OCaml — skips a ~30 min compiler build
opam switch create ec ocaml-system -y
eval $(opam env --switch=ec)

# ✅ pin sources
opam pin -yn add easycrypt https://github.com/EasyCrypt/easycrypt.git

# ⚠️ deps (43 pkgs, 20–40 min). OPAMDEPEXTYES=1 avoids an interactive prompt.
OPAMDEPEXTYES=1 opam install -y --deps-only easycrypt

# ⚠️ pinned solver + easycrypt itself
opam install -y alt-ergo.2.6.0
opam install -y easycrypt
easycrypt why3config
easycrypt --version
```

Version constraints (official README): Alt-Ergo **2.6.0**, Z3 **4.12.x**, CVC5 **1.0.8** (optional but more solvers = more proofs close), Why3 **≥1.8 <1.9** (opam resolves 1.8.2 automatically).

Gotchas we actually hit: opam.ocaml.org unreachable → GitHub mirror works; full compiler build unnecessary → `ocaml-system`; depext interactive prompt ignores `-y` → preinstall gmp/mpfr + env var; why3/uutf/topkg sources live on `why3.gitlabpages.inria.fr` / `erratique.ch` (not GitHub) → restrictive networks break there. **Only one machine needs a working install** — everyone else goes through the MCP server.

## 4. Architecture decision: stateless, file-as-state ("Route A")

A proof session is inherently stateful (accepted steps + open goals). The design question is who holds the state.

- **Route A (chosen):** the `.ec` file IS the state. Every tool call shells out to `easycrypt llm`, which replays the file (cheap: `.eco` caches verified prefixes). MCP server holds nothing → free crash recovery, free parallelism, and the file's git history is the full agent trace.
- **Route B (upgrade path):** keep `easycrypt cli` alive as a child process; tools become incremental `step/get_goals/rollback`. Finer-grained + faster per step, but the server becomes a session manager. If we do it, expose state as **immutable snapshot IDs** (map rollback → EasyCrypt's positional `undo`), not PG-style undo counting.

Prior art (all primary sources): the Lean community's **[repl](https://github.com/leanprover-community/repl)** — the standard verification backend in LLM-prover work — is a stateful JSON process whose state is addressed by immutable `env` snapshot IDs (backtrack = reuse an old ID), *and* it ships a batch file mode; **[PyPantograph](https://github.com/stanford-centaur/PyPantograph)** (Stanford) likewise offers both per-tactic interaction and whole-file checking; **[LeanDojo](https://github.com/lean-dojo/LeanDojo)** (NeurIPS 2023) wrapped interaction in gym-style sessions and its v1 is deprecated — interaction layers rot; file-level ground truth survives. Same tool schema works for A and B, so we can swap the backend without touching the agent side.

Tool design follows Anthropic's [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents): few consolidated tools, high-signal returns (pretty goals, not dumps), actionable error messages.

## 5. The MCP server (server.py, ~150 lines, Python + `mcp` SDK)

| tool | wraps | returns |
|---|---|---|
| `easycrypt_config()` | `easycrypt config` | install health, detected solvers |
| `check_file(path)` | `llm -lastgoals` | `ok`, diagnostics `[{severity,file,line,message}]`, pretty `goals` |
| `goals_at(path, line[, col])` | `llm -upto` | proof state at a position |
| `try_snippet(path, snippet[, line])` | temp-copy + insert + check | does this tactic work — **never mutates the real file** |

Agent loop: `goals_at` → `try_snippet` a tactic → if ok, apply the edit with the editor tool → `check_file` → repeat.

Setup:
```bash
pip install mcp
claude mcp add easycrypt -e EASYCRYPT_BIN=easycrypt -- python /abs/path/server.py
```

⚠️ The output parser was written against EasyCrypt's printer source but has **not run against a built binary**. First thing after install:
```bash
easycrypt config                   # lists Alt-Ergo etc.?
easycrypt llm -lastgoals some.ec   # exit 0 on a known-good file?
```
If the diagnostic regex misses lines, fix `DIAG_RE` in server.py (one place).

## 6. Demo plan & risks

**Demo:** Claude autonomously completes a small game-hopping proof (e.g., IND-CPA of a toy scheme) through the MCP tools, with the full tool-call trace shown; replayable because state = file. Pick the example from `easycrypt/examples/` — don't write a new proof from scratch.

**Pitch lines that are earned, not puffed:**
- "The brief says bad scientific software has no endpoints for agentic control — we built that endpoint for the standard crypto-proof tool."
- "Interface is isomorphic to how the Lean community exposes provers to LLMs (lean repl's snapshot model)."
- "Upstream already added an `llm` batch mode — we built the agent layer they left open. Works with any MCP client, demoed on Claude."

**Risks:** install chain breaks on venue Wi-Fi (→ do it on hotel Wi-Fi; one machine suffices); `llm` output format drifts from our parser (→ smoke test, fix one regex); demo proof too hard for the agent (→ choose the smallest example that still reads "crypto", pre-run it); do **not** claim "first ever LLM×prover" — Lean ecosystem is full of prior art, our novelty is EasyCrypt + MCP + the strategy layer.

## Sources

- [EasyCrypt repo/README](https://github.com/EasyCrypt/easycrypt) + its source (`src/ecOptions.ml`, `src/ec.ml`, `src/ecTerminal.ml`, `src/ecCommands.mli`), main @ 2026-10-17
- [leanprover-community/repl](https://github.com/leanprover-community/repl) · [PyPantograph](https://github.com/stanford-centaur/PyPantograph) · [LeanDojo](https://github.com/lean-dojo/LeanDojo)
- [Anthropic: Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
