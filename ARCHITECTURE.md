# Architecture

*2026-10-17. **[run]** = verified against the real binary in the Docker image (CI + local);
**[src]** = verified by reading EasyCrypt's source (`main` @ 2026-10-17) but not yet exercised.*

## What it is

```
 Claude Code (+ SKILL.md)  ──MCP/stdio──▶  mcp_server.py (6 tools) ──▶ easycrypt llm (upstream, unmodified)
            ▲                                                               │
            └──── the .ec file is the state: proofs/*.ec, bind-mounted or local ◀┘

 Live demo (demo/repair): browser ──SSE──▶ live_server.py ──▶ headless `claude -p` with the same
 MCP server + SKILL.md as system prompt; per-session git repo; verdict = EasyCrypt's final check_file.
```

Two ways to run EasyCrypt behind the server: the Docker image (`bin/easycrypt-mcp`, `.mcp.json`;
server and binary both in the container) or a native/opam install (`live_server.py`; or the Docker
binary through `scripts/ec-docker` with the server on the host).

One container, one Python wrapper, no state of our own. Every tool call re-runs `easycrypt llm`
on the file (Route A). The strategy — which tactic to try, when to call SMT, when to stop — lives
in a Claude Code skill in this repo, not in the server.

Non-goals: a stateful REPL (snapshot ids, undo); any claim of novelty beyond *EasyCrypt + MCP +
strategy layer* — the Lean ecosystem (lean `repl`, PyPantograph, LeanDojo) did the pattern first.

## The tools (frozen contract between server and skill)

All return a dict `{ok, exit_code, diagnostics[{severity,file,line,col,end_line,end_col,message}]
(columns 0-based), goals, raw_stderr, note, commit}`; usage errors return `{ok:false, error}` with an
actionable message.

| Tool | Runs | What the skill must know |
|---|---|---|
| `easycrypt_config()` | `easycrypt config` | Call once; lists solvers. |
| `check_file(path)` | `llm -lastgoals F` | Whole file. On failure `goals` holds the goals at the failing point. |
| `goals_at(path, line, col?)` | `llm -upto L` | State **before** the command at `line` runs. |
| `try_snippet(path, snippet, line?)` | temp copy + stop marker, `-upto end+1` | Inserts before `line` (default: EOF), runs **through** the snippet, returns goals after it. Never writes the file. |
| `apply_snippet(path, snippet, line?, commit=True)` | `try_snippet` + write + `git commit` | Same check; if ok, writes the real file and commits `agent: <first line>`. Nothing written on failure. The only write path — one accepted step = one commit = the trace. |
| `search_lib(pattern, limit?)` | regex over `theories/` source | Finds textual declarations; names made by `clone … rename` (e.g. `dbool1E`) are invisible to it **[run]** — list the theory with `print <Theory>.` instead. Needs the theories on the same filesystem as the server (true in the image and with a native install; with `scripts/ec-docker` set `EASYCRYPT_THEORIES` to a copy). |

Discovery recipe: `search_lib` → `print <name>.` → `print <Theory>.` (lists a whole theory with
statements **[run]**). EasyCrypt's own `search` prints nothing in batch mode **[run]**.

## Decisions

1. **File-as-state (Route A).** No session manager; crash recovery and parallel calls are free;
   `git log -p` of the proof file is the complete agent trace. Cost: every `-upto` call replays from
   line 1 (see Costs). Route B is the upgrade path if that ever hurts; the tool schema would not change.
2. **Docker on EasyCrypt's own CI image.** Solvers preinstalled; the build self-tests `llm`; CI
   publishes `ghcr.io/davidscode404/easy-crypt-mcp:<branch>` so nobody builds locally. amd64 only
   (native on Intel, emulated on Apple Silicon).
3. **Strategy = `.claude/skills/easycrypt-prover/SKILL.md`.** Versioned, visible to judges, written
   against the fake binary for plumbing and the image for semantics. Clients other than Claude Code
   paste it into their system prompt.
4. **The server owns writes** (`apply_snippet`). Works for any MCP client; the trace is a mechanism,
   not an instruction the agent might skip; the written bytes are exactly the tested bytes.
5. **Discovery is a tool** (`search_lib`), because the stdlib is inside the container where the
   agent's own grep cannot see it, and `search` is silent in batch mode.
6. **The loop has a terminal HANDOFF state.** Proof search is stochastic (SMT timeouts, tactic
   choice). When the budget is spent the agent stops and reports: goal, tactics tried, remaining
   goals. A partial run is still a correct demo. Details in the skill.
7. **Demo: `examples/elgamal.ec`** — IND-CPA ⇔ DDH in three game hops, 134 lines, in EasyCrypt's
   CI **[run]**. Two tasks from it: *repair* — `demo/repair` deletes any one proof line on stage
   (`demo/elgamal.ec` is the intact original) and a headless agent puts the proof back; *fill* —
   `proofs/elgamal.ec` has `cpa_ddh0`'s body removed, used from Claude Code interactively and in the
   with-vs-without-MCP comparison (`demo/replay`). Recorded fallbacks for both live in the repo
   (`demo/repair/run`, `demo/replay/traces`): real EasyCrypt output; the agent prose shown with
   `demo/repair`'s recording was written at recording time (`build_trace.py` NOTES).

## Facts about `easycrypt llm` the design depends on

| Fact | Status |
|---|---|
| goals → stdout; diagnostics → stderr as `[level] [loc] msg`; exit 0 ok / 1 fail | [run] |
| `-upto L` is exclusive: the command starting at line L is not run | [run] |
| `[loc]` formats: `File.ec: line 12 (3-10)` / `(3)` / `(3) to line 14 (7)` for errors **[run]**, `File.ec:12` / `File.ec:-1` for notices without a location (e.g. the OCaml-version warning) **[run]** — `DIAG_RE` accepts all | [run] |
| Log threshold is Warning: no `info` noise, and `search`/`locate` output is dropped | [run] |
| `print` goes to stdout; `print <Theory>.` lists its contents | [run] |
| `trivial`/`auto` never fail — an unclosed goal errors later at `qed.` ("cannot save an incomplete proof"). Closing attempts must be `by <tactic>.` | [run] |
| `llm` mode neither reads nor writes `.eco` (its `eco` field is the *no-eco* flag): there is no caching, every call replays the file from line 1 | [run] |
| Flags `-p NAME` (repeatable), `-timeout SEC`, `-lastgoals`, `-upto L[:C]`; default SMT timeout **3 s** → run with `EASYCRYPT_ARGS="-timeout 10"` | [src] |

## The agent loop (summary; the skill is the spec)

`check_file` → first failure → `goals_at(line)` → pick a tactic → `try_snippet` → ok: `apply_snippet`
→ `check_file` → repeat. On failure: simpler/explicit tactic → `smt` with hints found via
`search_lib`/`print` → split the goal → budget spent → HANDOFF. Closing attempts always `by …`.

## Costs (Route A, measured in the image)

| Call | Time |
|---|---|
| Load `AllCore` only | 0.5 s |
| `elgamal.ec` up to the first lemma (`-upto 71`: imports + clones, no proofs) | 4.7 s |
| `elgamal.ec` whole file (four lemmas, SMT included) | 5.1 s |

Measured on 1 vCPU, so an upper bound. The cost is almost all fixed overhead (loading the
theories `elgamal.ec` clones); the proofs add ~0.3 s. So a `try_snippet` on this file costs ≈ 5 s
regardless of where it is inserted, and there is no cache to exploit — Route B would only pay off
on files whose *proofs* are expensive.

## Status

- **Done [run]:** image builds and publishes from CI; 6 tools; real-binary tests; three
  source-found bugs fixed (`-upto` off-by-one, error-location regex, fake binary semantics); costs
  measured; the MCP server answers `initialize` / `tools/list` / `tools/call` over stdio inside the
  image; `proofs/elgamal.ec` fails exactly at the blanked `qed.` with the expected goal.
- **Rehearsed [run]:** a fresh agent with only the tools + skill filled `cpa_ddh0` from empty (25 calls,
  6 commits; `wp; call` and `smt(expM)` differ from the shipped proof) and, in a second run, repaired
  the file with `swap{1} 7 -5.` deleted (6 calls, 1 commit). The agent disclosed recognising the
  shipped example; its goal-based reasoning is recorded. The repair run exposed that the skill lacked
  repair guidance — now its *Repairing an existing proof* section.
- **Open:** rehearse `demo/repair` live on the demo machine (needs Python ≥ 3.10, `claude` CLI, and
  EasyCrypt native or via `scripts/ec-docker`); pin `EC_REF`.
- **Owners:** ①② @davidscode404 · ③ @Anna-199 · `demo/` @JingxinQiao. Repo rules: tests run on Python ≥ 3.8 with the
  fake binary; real-binary tests auto-skip without `easycrypt` on PATH and run in CI.
