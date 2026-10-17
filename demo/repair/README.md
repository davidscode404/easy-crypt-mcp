# Proof repair demo

Delete one line of `demo/elgamal.ec` on stage. A headless Claude Code agent then repairs it
using only the EasyCrypt MCP tools, and the page streams each tool call as it happens. The
"fixed" verdict comes from EasyCrypt checking the final file, not from the agent.

## Run it live

One-time setup (Intel macOS: keep Python ≤ 3.13 and an older `cryptography` wheel):

```bash
python3.13 -m venv .venv && .venv/bin/pip install --only-binary=cryptography "cryptography<45" mcp
```

Log `claude` in once: run `claude` in a terminal and type `/login`. Or export `ANTHROPIC_API_KEY`.

```bash
.venv/bin/python demo/repair/live_server.py
```

Open http://127.0.0.1:8766, click a line inside a proof, then click **Delete line N & repair**.

- EasyCrypt comes from `$EASYCRYPT_BIN`, then `PATH`, then `~/.opam/easycrypt/bin/easycrypt`.
- Claude Code comes from `--claude` or `$CLAUDE_BIN`, then `PATH`, then `~/.local/bin/claude`.
- Use `--model` to pick a model.
- Each run gets its own git repo in `sessions/<id>/`, so every accepted step is a commit there.

## Rehearse without an LLM

```bash
.venv/bin/python demo/repair/live_server.py --agent replay --port 8767
```

This mode replays the recorded run's tool calls against real EasyCrypt. It only works for line 79.

## Recorded run

Opening `index.html` without the server, for example from any static host, replays
`trace.js`. That file is built from `run/` by `python3 build_trace.py`.

## Event stream (for other agents or frontends)

`GET /api/sessions/<id>/events` sends server-sent events in this order:
`note` (agent prose) → `call` (tool started) → `step` (tool finished, with result) … → `done`
(final `check_file`). The docstring in `live_server.py` has the full contract. Any agent that
emits Claude Code `stream-json` lines can be dropped in, as `replay_agent.py` does.
