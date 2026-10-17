# Architecture

*Decisions as of 2026-10-17 (hack day). Facts marked **[src]** were verified by reading EasyCrypt's
source (`main` @ 2026-10-17); facts marked **[run]** were verified against a built binary. Nothing is
**[run]**-verified yet — the Docker image is being built. Owners: ①② @davidscode404, ③④ @Anna-199.*

## 0. What this is

An MCP endpoint that lets an agent drive EasyCrypt proofs, plus a strategy layer that tells the agent
how to use it. The endpoint is the thing the judging brief says scientific software lacks; the
strategy layer is what makes the demo an agent proving something rather than an API being poked.

Non-goals: a stateful REPL (Route B, see D1); a general prover UI; any claim of being first — the Lean
ecosystem (lean `repl`, PyPantograph, LeanDojo) did this years ago. Our novelty is EasyCrypt + MCP +
the strategy layer.

## 1. Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│ ④ Demo proof      one .ec from easycrypt/examples (candidate: elgamal.ec) │  @Anna-199   TODO
├──────────────────────────────────────────────────────────────────────┤
│ ③ Strategy        .claude/skills/easycrypt-prover/SKILL.md               │  @Anna-199   TODO
│                   the agent loop as a state machine, see §4               │
├──────────────────────────────────────────────────────────────────────┤
│ ② Endpoint        easycrypt_core.py + mcp_server.py (+ http_api.py)      │  @davidscode404  DONE*
│                   6 tools, see §2 — the only frozen interface             │
├──────────────────────────────────────────────────────────────────────┤
│ ① EasyCrypt       Docker: ghcr.io/easycrypt/ec-build-box + easycrypt     │  @davidscode404  BUILDING
└──────────────────────────────────────────────────────────────────────┘
   * DONE against a fake binary; three source-verified bugs queued, see §7
```

Each layer can be replaced without touching the others **as long as the ②↔③ contract in §2 holds**.
The strategy layer is developed against `tests/fake_easycrypt.py` for plumbing and against the Docker
image for semantics — the fake does not understand tactics, so it can only prove the loop runs, not
that the strategy proves anything.

## 2. The ②↔③ contract (frozen)

All tools return a dict. Success shape:

```
{ ok: bool, exit_code: int,
  diagnostics: [{severity: "warning"|"critical", file, line, col|null, message}],
  goals: str,          # pretty-printed open goals (stdout of easycrypt), "" if none
  raw_stderr: str,     # only when nothing parsed, so the agent still sees something
  note: str }
```
Usage errors the agent can fix (bad path, line out of range, binary missing, wall-clock exceeded)
come back as `{ ok: false, error: "<actionable message>" }`, never as exceptions.

| Tool | Wraps | Semantics the agent must know |
|---|---|---|
| `easycrypt_config()` | `easycrypt config` | Call once. No solvers listed ⇒ every `smt` will fail. |
| `check_file(path)` | `llm -lastgoals F` | Whole file. `ok` ⇔ exit 0. On failure `goals` = goals at the failing point. |
| `goals_at(path, line, col?)` | `llm -upto L[:C] F` | State **before** the command starting at `line` runs (Proof General semantics). |
| `try_snippet(path, snippet, line?)` | temp copy + `llm -upto` | Inserts `snippet` before `line` in a temp copy, runs **through** the snippet, returns goals after it. Never writes the real file. Insert before `qed.`, not at EOF (at EOF there is no next command to stop at, so no goals are printed). |
| `apply_snippet(path, snippet, line?)` **(new, D4)** | `try_snippet` + write + `git commit` | Same check; if `ok`, writes the real file and commits with message `agent: <first line of snippet>`. The only write path. |
| `search_lib(pattern, limit?)` **(new, D5)** | grep over the stdlib `theories/` inside the container | `[{file, line, text}]`. Names found here are then inspected with `try_snippet(path, "print <name>.", line)`. |

Exact statement of a known name: `try_snippet(path, "print Foo.", line)` — `print` writes to stdout
**[src]**, so it comes back in `goals`. Pattern search via EasyCrypt's own `search` does **not** work
through this interface, see §3.

## 3. Verified facts about `easycrypt llm` **[src]**

| Fact | Where | Consequence for ② |
|---|---|---|
| Goals (`-upto`, `-lastgoals`) → **stdout**; diagnostics → **stderr** | `ec.ml`, `ecTerminal.ml` | as designed |
| Exit 0 = accepted or `-upto` reached; 1 = failure | `ec.ml` | `ok = (exit == 0)` |
| `-upto L` is **exclusive**: a command whose start line ≥ L is not run; goals are printed and the process exits 0 | `ec.ml` `past_upto` | **B1** `try_snippet` must use `end_line + 1` |
| Diagnostics have **two** location formats: `[level] [file:LINE] msg` for notices without a precise location, and `[level] [file: line L (c)]`, `[file: line L (c1-c2)]`, `[file: line L1 (c1) to line L2 (c2)]` for errors carrying a location — i.e. **every proof failure** | `ecTerminal.ml` `_notice`, `ecLocation.ml` `tostring` | **B2** `DIAG_RE` must accept both |
| Multi-line messages continue on following lines | `ecTerminal.ml` | continuation logic already correct |
| Log threshold is hard-coded **Warning**: `info`/`debug` never reach stderr; levels print lowercase | `ecTerminal.ml`, `ecGState.ml` | no `added lemma:` noise; `search`/`locate` output is Info and therefore **dropped** |
| `print` writes to `Format.std_formatter` | `ecCommands.ml` `process_print` | exact-name lookup works through `try_snippet` |
| Flags: `-p NAME` (repeatable), `-timeout SEC`, `-quorum N`, `-cpu-factor N`, `-check-all`, `-pragmas a,b`, `-lastgoals`, `-upto L[:C]` | `ecOptions.ml` | `EASYCRYPT_ARGS` as documented is correct |
| Default SMT timeout is **3 s** | `ec.ml` `cm_timeout = odfl 3` | set `EASYCRYPT_ARGS="-timeout 10"` for agent use |
| Silent progress mode writes nothing else to stderr | `ecTerminal.ml` | stderr is clean, parse everything |

## 4. The agent loop (③) as a state machine

```
          ┌────────────────────────────────────────────────────────────┐
          ▼                                                            │
  INSPECT  goals_at(file, L)  ──►  PLAN  pick tactic for first goal    │
                                       │                               │
                                       ▼                               │
                                  TRY  try_snippet(file, tactic, L)    │
                                   │ ok                  │ fail        │
                                   ▼                     ▼             │
          APPLY  apply_snippet (writes + commits)    RECOVER  ladder:   │
                 │                                   1. simpler/explicit tactic
                 ▼                                   2. smt with hints ← search_lib + print
          CHECK  check_file ── ok ──► DONE           3. split the goal
                 │ not ok                            tries < budget? ──► TRY ─┘
                 └────────────────────────────────────┘ budget spent
                                                             │
                                                             ▼
                                                   HANDOFF  stop, report:
                                                   goal stuck on, tactics tried,
                                                   remaining goals, last diagnostics
```

Budgets (defaults in the skill): N tries per goal, M total `try_snippet` calls, wall-clock per call
from `EASYCRYPT_WALL`. HANDOFF is a designed terminal state, not a failure: proof search is
stochastic (SMT timeouts, tactic choice) and a real user needs the agent to say precisely where it
stopped. The demo narrative holds in either terminal state.

## 5. Trace

Every accepted step is one commit made by `apply_snippet`, so `git log -p` on the proof file is the
complete, replayable agent trace independent of which client drove it. The live demo additionally
shows the tool-call stream in Claude Code. Nothing else is logged.

## 6. Decisions

| # | Decision | Why | Rejected |
|---|---|---|---|
| D1 | **Route A, file-as-state.** Server holds nothing; every call re-runs `easycrypt llm`. | Free crash recovery and parallelism; git history is the trace; same tool schema works if we ever add Route B. | Route B (child `easycrypt cli`, snapshot ids) — a session manager we don't need for the demo. |
| D2 | **Docker on EasyCrypt's own CI image**, not opam. | Solvers pre-installed; 5–10 min build; build-time self-test. The demo machine is an Intel Mac, so the amd64 image runs natively. | opam install (20–40 min, network-fragile). Kept as documented fallback. |
| D3 | **Strategy layer = Claude Code skill in this repo.** | Versioned, visible to judges, writable before ① exists. | MCP prompts (uneven client support); system prompt only (nothing to show). |
| D4 | **Server owns writes: `apply_snippet` writes and commits.** | Works with any MCP client (pitch stays true); trace is guaranteed by mechanism, not by the agent remembering to commit; one audit point. Still Route A — the file is the state, the server just writes it. | Agent edits with its own editor (ties the system to Claude Code; trace depends on obedience). |
| D5 | **Discovery = `print` via `try_snippet` + `search_lib` grep inside the container.** | `search` output is Info-level and filtered **[src]**; the stdlib lives in the container where the agent's own grep cannot see it. | Agent greps the stdlib itself (impossible across the container boundary). |
| D6 | **③ has an explicit HANDOFF state.** | See §4. | Loop until budget, report vaguely. |
| D7 | **Demo candidate: `examples/elgamal.ec`** — 134 lines, IND-CPA ⇔ DDH in three game hops, ends with `print conclusion.` | Smallest example that reads as crypto; exactly the §6 brief. Pending: it carries a "DiffieHellman is really out of date" warning — must check it still compiles in the image before committing to it. | Writing a new proof (brief says don't). |

## 7. Bugs queued on branch `anna` (all **[src]**-verified)

| # | Bug | Fix |
|---|---|---|
| B1 | `try_snippet` passes `-upto end_line`; `-upto` is exclusive, so a one-line snippet is never executed and `ok` is always the prefix's result. | `-upto end_line + 1`. |
| B2 | `DIAG_RE` only matches `file:LINE`; real proof errors use `file: line L (c-d)`. Every failure falls into `raw_stderr` with no line number. | Second alternative in the regex; `line` = L, `col` = c. |
| B3 | `tests/fake_easycrypt.py` implements `-upto` as *inclusive* (`lines[:upto]`), the opposite of the binary, so the smoke tests pass against the wrong semantics. | Make the fake exclusive; add a test that a one-line snippet is actually exercised. |
| B4 | README/notes say `.eco` caches verified *prefixes*, making re-runs cheap. **[src]** `.eco` is a whole-file digest cache: if the file is byte-identical to the last successful check, `llm` exits 0 immediately — and the check is skipped entirely when `-upto` is set (`ec.ml`: `if … state.upto = None then … check_eco`). So `check_file` on an unchanged file is free; `goals_at` and `try_snippet` always replay from line 1. | Correct the claim. Cost per `try_snippet` = full check of the prefix (seconds for elgamal.ec). Acceptable for the demo; the reason to revisit Route B for large files. |

## 8. Risks

| Risk | Status / mitigation | Owner |
|---|---|---|
| `ghcr.io` pull or image build fails | Building now on Anna's Intel Mac (colima). Fallback: build `ec-build-box` from EasyCrypt's repo (~1 h). | @Anna-199 today, then @davidscode404 |
| `DIAG_RE` still never run against the binary | First thing after the build: `llm -lastgoals` on a good and a bad file, diff stderr against §3. | @davidscode404 |
| `elgamal.ec` no longer compiles on `main` | Check in the image; fall back to `SchnorrPK.ec` / `Pedersen.ec` (~5 KB each). | @Anna-199 |
| SMT nondeterminism in the live demo | `-timeout 10`; pre-run the demo several times; HANDOFF state makes a partial run presentable. | @Anna-199 |
| Local dev needs Python ≥ 3.10 (`mcp` SDK); Anna's default is 3.8 | Use Docker for the server; tests still run on 3.8. | — |

## 9. Demo script (sketch)

1. `easycrypt_config` — show solvers detected.
2. Open `elgamal.ec` with one lemma's proof body replaced by `admit.` (or removed); `check_file` shows it failing with goals.
3. Ask Claude (skill loaded) to complete the proof. Watch INSPECT → TRY → APPLY commits scroll by.
4. `check_file` → ok. `git log --oneline` — one commit per accepted step.
5. If it HANDOFFs: show the report; finish the step by hand; say this is the point.
