# Architecture

*2026-10-17. **[run]** = verified against the real binary in the Docker image (CI + local);
**[src]** = verified by reading EasyCrypt's source (`main` @ 2026-10-17) but not yet exercised.*

## What it is

```
 Claude Code (+ SKILL.md)  ──MCP/stdio──▶  docker run easycrypt-mcp
                                             ├─ mcp_server.py   (6 tools)
                                             └─ easycrypt llm   (upstream, unmodified)
            ▲                                           │
            └──── proofs/*.ec on the host, bind-mounted at the same path; the file is the state
```

One container, one Python wrapper, no state of our own. Every tool call re-runs `easycrypt llm`
on the file (Route A). The strategy — which tactic to try, when to call SMT, when to stop — lives
in a Claude Code skill in this repo, not in the server.

Non-goals: a stateful REPL (snapshot ids, undo); any claim of novelty beyond *EasyCrypt + MCP +
strategy layer* — the Lean ecosystem (lean `repl`, PyPantograph, LeanDojo) did the pattern first.

## The tools (frozen contract between server and skill)

All return a dict `{ok, exit_code, diagnostics[{severity,file,line,col,message}], goals, raw_stderr,
note, commit}`; usage errors return `{ok:false, error}` with an actionable message.

| Tool | Runs | What the skill must know |
|---|---|---|
| `easycrypt_config()` | `easycrypt config` | Call once; lists solvers. |
| `check_file(path)` | `llm -lastgoals F` | Whole file. On failure `goals` holds the goals at the failing point. |
| `goals_at(path, line, col?)` | `llm -upto L` | State **before** the command at `line` runs. |
| `try_snippet(path, snippet, line?)` | temp copy, `-upto end+1` | Inserts before `line`, runs **through** the snippet, returns goals after it. Never writes the file. Insert before `qed.`, not at EOF. |
| `apply_snippet(path, snippet, line?, commit=True)` | `try_snippet` + write + `git commit` | Same check; if ok, writes the real file and commits `agent: <first line>`. Nothing written on failure. The only write path — one accepted step = one commit = the trace. |
| `search_lib(pattern, limit?)` | regex over `theories/` source in the container | Finds textual declarations; names made by `clone … rename` (e.g. `dbool1E`) are invisible to it **[run]** — list the theory with `print <Theory>.` instead. |

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
   CI **[run]**. Blank one lemma's proof body and let the agent fill it.

## Facts about `easycrypt llm` the design depends on

| Fact | Status |
|---|---|
| goals → stdout; diagnostics → stderr as `[level] [loc] msg`; exit 0 ok / 1 fail | [run] |
| `-upto L` is exclusive: the command starting at line L is not run | [run] |
| Two `[loc]` formats: `File.ec:12` (notices) and `File.ec: line 12 (3-10)` (errors) — `DIAG_RE` accepts both | [run] |
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

- **Done [run]:** image builds and publishes from CI; 6 tools; 10/10 real-binary tests; three
  source-found bugs fixed (`-upto` off-by-one, error-location regex, fake binary semantics); costs measured.
- **Open:** SKILL.md (③); the demo file with one proof blanked (④).
- **Owners:** ①② @davidscode404 · ③④ @Anna-199. Repo rules: tests run on Python ≥ 3.8 with the
  fake binary; real-binary tests auto-skip without `easycrypt` on PATH and run in CI.
