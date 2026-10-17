"""EasyCrypt wrapper core: no web framework, no MCP. Both servers import this.

Route A (file-as-state): every call shells out to `easycrypt llm`; nothing is held in memory.

Config (env vars):
  EASYCRYPT_BIN    path to easycrypt binary (default "easycrypt")
  EASYCRYPT_ARGS   extra args for every `llm` call, e.g. "-p Alt-Ergo -p Z3 -timeout 10"
                   (check exact flag names with `easycrypt llm -help` once built)
  EASYCRYPT_ROOT   if set, only files under this directory may be checked
  EASYCRYPT_WALL   wall-clock limit per call in seconds (default 120)
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

EC_BIN = os.environ.get("EASYCRYPT_BIN", "easycrypt")
EC_ARGS = shlex.split(os.environ.get("EASYCRYPT_ARGS", ""))
EC_ROOT = os.environ.get("EASYCRYPT_ROOT")
WALL = float(os.environ.get("EASYCRYPT_WALL", "120"))

# ⚠️ The one place to fix if real `llm` output differs.
# Two location formats (src/ecTerminal.ml `_notice`, src/ecLocation.ml `tostring`):
#   [warning]  [File.ec:12] msg                    notices without a precise location
#   [critical] [File.ec: line 12 (3-10)] msg       errors; also "line 12 (3)" and
#                                                   "line 12 (3) to line 14 (7)"
DIAG_RE = re.compile(
    r"^\[(?P<severity>[A-Za-z]+)\]\s*\[(?P<file>.+?)"
    r"(?::(?P<line>\d+)(?::(?P<col>\d+))?"
    r"|: line (?P<line2>\d+) \((?P<col2>\d+)(?:-\d+)?\)(?: to line \d+ \(\d+\))?)"
    r"\]\s*(?P<message>.*)$"
)


@dataclass
class Diagnostic:
    severity: str
    file: str
    line: int
    col: int | None
    message: str


@dataclass
class Result:
    ok: bool
    exit_code: int
    diagnostics: list[Diagnostic] = field(default_factory=list)
    goals: str = ""
    raw_stderr: str = ""  # only filled when nothing parsed, so the agent still sees *something*
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ECError(Exception):
    """Raised for usage errors the agent can fix (bad path, bad line)."""


def _resolve(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if EC_ROOT and not p.is_relative_to(Path(EC_ROOT).resolve()):
        raise ECError(f"{p} is outside EASYCRYPT_ROOT={EC_ROOT}")
    if not p.is_file():
        raise ECError(f"No such file: {p}")
    if p.suffix not in (".ec", ".eca"):
        raise ECError(f"Expected a .ec or .eca file, got {p.name}")
    return p


def parse_diagnostics(stderr: str) -> tuple[list[Diagnostic], str]:
    """Parse stderr; lines that don't match DIAG_RE are continuation lines of the previous diagnostic."""
    diags: list[Diagnostic] = []
    unmatched: list[str] = []
    for line in stderr.splitlines():
        m = DIAG_RE.match(line.strip())
        if m:
            diags.append(Diagnostic(
                severity=m["severity"].lower(),
                file=m["file"],
                line=int(m["line"] or m["line2"]),
                col=int(m["col"] or m["col2"]) if (m["col"] or m["col2"]) else None,
                message=m["message"].strip(),
            ))
        elif diags and line.strip():
            diags[-1].message += "\n" + line.rstrip()
        elif line.strip():
            unmatched.append(line)
    return diags, "\n".join(unmatched)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [EC_BIN, *args], cwd=cwd, capture_output=True, text=True, timeout=WALL
        )
    except FileNotFoundError:
        raise ECError(f"EasyCrypt binary not found: {EC_BIN!r}. Set EASYCRYPT_BIN.")
    except subprocess.TimeoutExpired:
        raise ECError(
            f"EasyCrypt exceeded {WALL:.0f}s. Likely a hung `smt` call: try a smaller step, "
            "add hints (`smt(lemma)`), or raise EASYCRYPT_WALL."
        )


def _llm(file: Path, extra: list[str]) -> Result:
    proc = _run(["llm", *EC_ARGS, *extra, file.name], cwd=file.parent)
    diags, leftover = parse_diagnostics(proc.stderr)
    return Result(
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        diagnostics=diags,
        goals=proc.stdout.strip(),
        raw_stderr=leftover if (leftover and not diags) or proc.returncode not in (0, 1) else "",
    )


# ---------------------------------------------------------------- public API

def config() -> dict:
    proc = _run(["config"], cwd=Path.cwd())
    return {"ok": proc.returncode == 0, "binary": EC_BIN, "extra_args": EC_ARGS,
            "output": (proc.stdout + proc.stderr).strip()}


def check_file(path: str) -> Result:
    """Check the whole file; on failure, include remaining goals."""
    return _llm(_resolve(path), ["-lastgoals"])


def goals_at(path: str, line: int, col: int | None = None) -> Result:
    """Proof state after checking up to LINE[:COL]."""
    f = _resolve(path)
    n = len(f.read_text().splitlines())
    if not 1 <= line <= n:
        raise ECError(f"line {line} out of range (file has {n} lines)")
    pos = f"{line}:{col}" if col is not None else str(line)
    return _llm(f, ["-upto", pos])


def try_snippet(path: str, snippet: str, line: int | None = None) -> Result:
    """Insert SNIPPET before LINE (default: end of file) in a temp copy, check up to the
    end of the snippet, and report goals there. Never touches the original file."""
    f = _resolve(path)
    lines = f.read_text().splitlines(keepends=True)
    at = len(lines) + 1 if line is None else line
    if not 1 <= at <= len(lines) + 1:
        raise ECError(f"line {line} out of range (file has {len(lines)} lines)")
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    snip = snippet if snippet.endswith("\n") else snippet + "\n"
    patched = lines[: at - 1] + [snip] + lines[at - 1 :]
    end_line = at - 1 + len(snip.splitlines())

    # Same directory so `require` of sibling theories resolves; unique name so parallel calls
    # don't collide. Theory name comes from the filename, so keep it a valid identifier.
    tmp = f.parent / f"Try_{uuid.uuid4().hex[:12]}{f.suffix}"
    try:
        tmp.write_text("".join(patched))
        # `-upto L` stops BEFORE the command starting at line L (exclusive, src/ec.ml
        # `past_upto`), so to execute the whole snippet we stop at the line after it.
        res = _llm(tmp, ["-upto", str(end_line + 1)])
    finally:
        for p in (tmp, tmp.with_suffix(".eco")):
            p.unlink(missing_ok=True)

    for d in res.diagnostics:
        if Path(d.file).name == tmp.name:
            d.file = f.name
    res.note = (f"Snippet occupied lines {at}-{end_line} of a temp copy; "
                f"diagnostic line numbers refer to that copy. Original file unchanged.")
    return res