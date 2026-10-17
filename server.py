"""MCP server exposing EasyCrypt's batch CLI (`easycrypt llm`) to agents.

Stateless ("Route A"): the .ec file is the proof state. Every tool call
shells out to EasyCrypt, which replays the file (.eco caches verified prefixes).

Configuration (environment variables):
  EASYCRYPT_BIN      command used to run EasyCrypt (default: "easycrypt").
                     May contain arguments, e.g. a Docker wrapper:
                     EASYCRYPT_BIN="scripts/ec-docker"
  EASYCRYPT_PROVERS  comma-separated provers passed as `-p` flags
                     (default: let EasyCrypt pick), e.g. "Alt-Ergo,Z3"
  EASYCRYPT_TIMEOUT  seconds before a call is killed (default: 120)
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path

try:  # mcp >= 2 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

EASYCRYPT_BIN = shlex.split(os.environ.get("EASYCRYPT_BIN", "easycrypt"))
PROVERS = [p.strip() for p in os.environ.get("EASYCRYPT_PROVERS", "").split(",") if p.strip()]
TIMEOUT = float(os.environ.get("EASYCRYPT_TIMEOUT", "120"))

# `[Severity] [file:LINE] message`; COL and a range suffix are accepted too,
# since the exact location format has not been checked against a built binary.
DIAG_RE = re.compile(
    r"^\[(?P<severity>[A-Za-z]+)\]\s*"
    r"\[(?P<file>[^\]]*?):(?P<line>\d+)(?::(?P<col>\d+))?[^\]]*\]\s*"
    r"(?P<message>.*)$"
)

mcp = MCPServer("easycrypt")


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str] | str:
    """Run EasyCrypt; return the process, or an error string if it could not run."""
    cmd = EASYCRYPT_BIN + args
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError:
        return (
            f"EasyCrypt binary not found: {cmd[0]!r}. Install EasyCrypt or set EASYCRYPT_BIN "
            "(run `eval $(opam env)` first if it was installed with opam)."
        )
    except subprocess.TimeoutExpired:
        return f"EasyCrypt timed out after {TIMEOUT:g}s (raise EASYCRYPT_TIMEOUT or simplify the goal)."


def _parse_diagnostics(stderr: str) -> list[dict]:
    """Split stderr into diagnostics; unmatched lines continue the previous message."""
    diags: list[dict] = []
    for raw in stderr.splitlines():
        m = DIAG_RE.match(raw)
        if m:
            diags.append({
                "severity": m["severity"].lower(),
                "file": m["file"],
                "line": int(m["line"]),
                **({"col": int(m["col"])} if m["col"] else {}),
                "message": m["message"].strip(),
            })
        elif raw.strip():
            if diags:
                diags[-1]["message"] = (diags[-1]["message"] + "\n" + raw.rstrip()).strip()
            else:
                diags.append({"severity": "unparsed", "message": raw.rstrip()})
    return diags


def _check(path: Path, extra: list[str]) -> dict:
    """Run `easycrypt llm` on path and package the result for the agent."""
    if not path.is_file():
        return {"ok": False, "error": f"File not found: {path}"}
    args = ["llm", *extra]
    for p in PROVERS:
        args += ["-p", p]
    args.append(path.name)
    proc = _run(args, cwd=path.parent)
    if isinstance(proc, str):
        return {"ok": False, "error": proc}
    result = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "diagnostics": _parse_diagnostics(proc.stderr),
        "goals": proc.stdout.strip(),
    }
    if any(d["severity"] == "unparsed" for d in result["diagnostics"]):
        # Parser drift is the main untested risk; keep the raw text visible.
        result["raw_stderr"] = proc.stderr[-4000:]
    return result


@mcp.tool()
def easycrypt_config() -> dict:
    """Report EasyCrypt install health: version and detected SMT provers.

    Call this first if any other tool returns an error about the binary or provers.
    """
    proc = _run(["config"])
    if isinstance(proc, str):
        return {"ok": False, "error": proc}
    return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr).strip()}


@mcp.tool()
def check_file(path: str) -> dict:
    """Check a whole .ec file with EasyCrypt.

    Returns ok (true if every proof is accepted), diagnostics as
    [{severity, file, line, col?, message}], and the remaining goals at the
    first failure, pretty-printed.
    """
    return _check(Path(path).expanduser().resolve(), ["-lastgoals"])


@mcp.tool()
def goals_at(path: str, line: int, col: int | None = None) -> dict:
    """Show the proof state at a position in a .ec file.

    EasyCrypt checks the file up to line[:col] (1-based) and prints the open
    goals there. ok is true if everything before that point is accepted.
    """
    pos = f"{line}:{col}" if col is not None else str(line)
    return _check(Path(path).expanduser().resolve(), ["-upto", pos])


@mcp.tool()
def try_snippet(path: str, snippet: str, line: int | None = None) -> dict:
    """Test whether some EasyCrypt text (usually a tactic) works, without editing the file.

    The snippet is inserted after `line` (1-based; omit to append at the end) in
    a temporary copy next to the original, so local `require`s still resolve.
    With a line, checking stops right after the snippet and goals shows the
    proof state it leaves; without one, the whole copy is checked.
    The real file is never modified. Apply a working snippet with your editor.
    """
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        return {"ok": False, "error": f"File not found: {src}"}
    lines = src.read_text().splitlines(keepends=True)
    if line is not None and not 0 <= line <= len(lines):
        return {"ok": False, "error": f"line must be between 0 and {len(lines)} (the file's length)."}

    at = len(lines) if line is None else line
    if lines[:at] and not lines[at - 1].endswith("\n"):
        lines[at - 1] += "\n"
    body = snippet if snippet.endswith("\n") else snippet + "\n"
    start, end = at + 1, at + body.count("\n")
    new_text = "".join(lines[:at]) + body + "".join(lines[at:])

    # Same directory (Docker mounts, local requires); name must be a valid theory name.
    tmp = src.with_name(f"{src.stem}_try{uuid.uuid4().hex[:8]}.ec")
    try:
        tmp.write_text(new_text)
        result = _check(tmp, ["-upto", str(end + 1)] if line is not None else ["-lastgoals"])
    finally:
        for f in (tmp, tmp.with_suffix(".eco")):
            f.unlink(missing_ok=True)

    for d in result.get("diagnostics", []):
        if d.get("file") and Path(d["file"]).name == tmp.name:
            d["file"] = src.name
    result["snippet_lines"] = [start, end]
    result["note"] = "Line numbers refer to the temporary copy; the snippet occupies snippet_lines."
    return result


if __name__ == "__main__":
    mcp.run()
