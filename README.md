# easycrypt-mcp

Lets an AI agent (e.g. Claude) drive [EasyCrypt](https://github.com/EasyCrypt/easycrypt), the
proof assistant for cryptographic security proofs.

EasyCrypt is normally used through an Emacs front-end, built for a human at a keyboard. This
project gives it a programmatic endpoint: an [MCP](https://modelcontextprotocol.io) server that
lets an agent check a proof file, read the open goals at any line, and test a tactic before
committing to it. Everything runs in one Docker image, so you don't install EasyCrypt or its
SMT solvers yourself.

---

## Quick start (Docker)

You need [Docker](https://docs.docker.com/get-docker/) and, to talk to it from Claude,
[Claude Code](https://docs.claude.com/en/docs/claude-code). Run everything from this repo's folder.

**1. Check you can reach EasyCrypt's base image** (it holds OCaml, all dependencies and the solvers):

```bash
docker pull --platform linux/amd64 ghcr.io/easycrypt/ec-build-box:main
```

If this fails, see [Troubleshooting](#troubleshooting) before going further.

**2. Build the image** (about 5–10 minutes; it compiles EasyCrypt and tests it):

```bash
docker build --platform linux/amd64 -t easycrypt-mcp .
```

The build ends by checking EasyCrypt on a proof that should pass and one that should fail.
If it finishes, EasyCrypt works.

**3. Check the solvers were detected:**

```bash
docker run --rm --platform linux/amd64 easycrypt-mcp easycrypt config
```

You should see Alt-Ergo, Z3 and CVC5 listed.

**4. Connect it to Claude Code.** `cd` into the folder holding your `.ec` proof files, then:

```bash
claude mcp add easycrypt -- docker run -i --rm --platform linux/amd64 \
  -v "$PWD:$PWD" -w "$PWD" -e EASYCRYPT_ROOT="$PWD" easycrypt-mcp
```

**5. Try it.** Start `claude` in that folder and ask, for example:

> Check `MyProof.ec` with the easycrypt tools, then show me the goals at line 40.

> On Apple Silicon Macs the image runs under emulation (the solvers are Intel-only builds).
> It works, but SMT calls are slower; see [Configuration](#configuration) to raise the timeout.

---

## What the agent can do

| Tool | What it does |
|---|---|
| `easycrypt_config` | Checks the install and lists the SMT solvers EasyCrypt found. |
| `check_file(path)` | Checks a whole `.ec` file. Returns whether it passed, any errors with line numbers, and the unproved goals if it failed. |
| `goals_at(path, line, col?)` | Shows the proof state (what's left to prove) at a given line. |
| `try_snippet(path, snippet, line?)` | Tests a tactic on a temporary copy of the file and returns the resulting goals. **Never changes your file.** |

A typical loop: look at the goals with `goals_at`, test a tactic with `try_snippet`, and if it
works, write it into the file and confirm with `check_file`.

## How it works

The server keeps no state. The `.ec` file *is* the proof state: every tool call runs EasyCrypt's
batch checker (`easycrypt llm`) on the file and returns the result. So the server can be
restarted at any time, several calls can run in parallel, and the file's git history is a full
record of what the agent did.

Your folder is mounted into the container **at the same path** (`-v "$PWD:$PWD"`). That's why
step 4 must be run from the folder with your proofs: a path like `/Users/you/proofs/A.ec` then
means the same file on your machine and inside the container.

## Configuration

Set these with `-e NAME=value` in the `docker run` part of step 4.

| Variable | Default | Purpose |
|---|---|---|
| `EASYCRYPT_ARGS` | *(empty)* | Extra flags for every check, e.g. `-timeout 20` (SMT timeout, seconds) or `-p Z3` (choose a solver; repeatable). |
| `EASYCRYPT_ROOT` | *(none)* | Only files inside this folder may be checked. Step 4 sets it to your folder. |
| `EASYCRYPT_WALL` | `120` | Hard time limit per call, in seconds; stops a stuck solver from hanging the agent. |
| `EASYCRYPT_BIN` | `easycrypt` | Path to the EasyCrypt binary (only needed outside Docker). |

To pin a specific EasyCrypt version for a reproducible demo, build with
`--build-arg EC_REF=<commit-or-tag>`.

## Browser / REST access (optional)

For poking at the tools by hand, the same functions are available over HTTP:

```bash
docker run --rm --platform linux/amd64 -p 8000:8000 -v "$PWD:$PWD" -w "$PWD" easycrypt-mcp \
  python3 -m uvicorn --app-dir /app http_api:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/docs> for an interactive page where you can try each call.

## Troubleshooting

**Step 1 fails (`denied` / `forbidden` / can't reach `ghcr.io`).** Build the base image yourself
from EasyCrypt's repo. It's slower (around an hour, it compiles OCaml) but needs only GitHub:

```bash
git clone https://github.com/EasyCrypt/easycrypt
docker build --platform linux/amd64 --target build -t ec-build-box easycrypt/scripts/docker
docker build --platform linux/amd64 --build-arg BASE=ec-build-box -t easycrypt-mcp .
```

**The build fails at the self-test step.** EasyCrypt's `llm` command no longer behaves as this
server expects. Try a known-good version with `--build-arg EC_REF=<older commit>`.

**A tool returns `raw_stderr` but no `diagnostics`.** EasyCrypt printed errors in a format the
parser doesn't recognise. Adjust `DIAG_RE` in `easycrypt_core.py` (the only place it's defined)
and rebuild.

**`No such file` for a file that exists.** You ran `claude mcp add` from a different folder, so it
isn't mounted. Remove it with `claude mcp remove easycrypt` and repeat step 4 from the right folder.

**Calls time out.** Raise `-timeout` in `EASYCRYPT_ARGS` and/or `EASYCRYPT_WALL`, especially on
Apple Silicon.

## Development

The tests use a fake EasyCrypt binary, so they run anywhere with Python 3.10+, no Docker needed:

```bash
pip install mcp fastapi uvicorn pytest
python -m pytest -q tests
```

To run the server against a local EasyCrypt install instead of Docker:

```bash
claude mcp add easycrypt -e EASYCRYPT_BIN=easycrypt -- python "$PWD/mcp_server.py"
```

| File | Purpose |
|---|---|
| `easycrypt_core.py` | All EasyCrypt logic: runs the CLI and parses its output. |
| `mcp_server.py` | MCP server exposing the four tools to agents. |
| `http_api.py` | Optional REST mirror of the same tools. |
| `Dockerfile` | The image: EasyCrypt + solvers + this server. |
| `tests/` | Fake `easycrypt` binary and smoke tests. |