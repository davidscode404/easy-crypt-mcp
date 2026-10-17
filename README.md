# EasyCrypt agent server

```
easycrypt_core.py   all EasyCrypt logic (subprocess + output parsing); DIAG_RE lives here
mcp_server.py       MCP tools for Claude / any MCP client (works with mcp 1.x and 2.x)
http_api.py         optional REST mirror for humans: uvicorn http_api:app → /docs
tests/              fake easycrypt binary + smoke tests (no install needed)
```

## Run
```bash
pip install mcp fastapi uvicorn pytest
python -m pytest -q tests                       # passes without EasyCrypt installed
claude mcp add easycrypt -e EASYCRYPT_BIN=easycrypt \
  -e EASYCRYPT_ARGS="-p Alt-Ergo -p Z3" -- python $PWD/mcp_server.py
uvicorn http_api:app --port 8000                # optional
```

Env: `EASYCRYPT_BIN`, `EASYCRYPT_ARGS` (extra `llm` flags, e.g. solvers and SMT timeout),
`EASYCRYPT_ROOT` (sandbox: only files under it), `EASYCRYPT_WALL` (seconds per call, default 120).

## First thing once EasyCrypt is built
```bash
easycrypt llm -help                      # confirm -lastgoals, -upto, -p, timeout flag names
easycrypt llm -lastgoals known_good.ec   # exit 0?
easycrypt llm -lastgoals broken.ec       # does stderr match DIAG_RE in easycrypt_core.py?
```
If a call returns `raw_stderr` with no `diagnostics`, the regex missed: fix `DIAG_RE`.

## Notes
- `try_snippet` writes `Try_<hex>.ec` next to the original (so `require` of siblings resolves),
  checks it with `-upto` the end of the snippet, then deletes it and its `.eco`.
- A wall-clock timeout surfaces as an actionable error rather than hanging the agent.