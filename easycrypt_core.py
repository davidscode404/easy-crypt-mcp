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

# Verified against a real build (r2026.09) and src/ecLocation.ml `tostring`. Three location forms:
#   [critical] [Bad.ec: line 2 (16-20)] msg              same line, cols 16..20
#   [critical] [Bad.ec: line 2 (16)] msg                 single point
#   [critical] [Bad.ec: line 2 (16) to line 4 (3)] msg   spans lines
# Columns are 0-based.
DIAG_RE = re.compile(
    r"^\[(?P<severity>[A-Za-z]+)\]\s*"
    r"\[(?P<file>.+?): line (?P<line>\d+) \((?P<col>\d+)(?:-(?P<end_col>\d+))?\)"
    r"(?: to line (?P<end_line>\d+) \((?P<end_col2>\d+)\))?\]\s*"
    r"(?P<message>.*)$"
)


@dataclass
class Diagnostic:
    severity: str
    file: str
    line: int
    col: int | None  # 0-based
    end_line: int | None
    end_col: int | None
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
            line_no = int(m["line"])
            end_line = int(m["end_line"]) if m["end_line"] else line_no
            end_col = m["end_col"] or m["end_col2"] or m["col"]
            diags.append(Diagnostic(
                severity=m["severity"].lower(),
                file=m["file"],
                line=line_no,
                col=int(m["col"]),
                end_line=end_line,
                end_col=int(end_col),
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
    """Proof state just BEFORE the first command starting at LINE (or at LINE:COL, col 0-based),
    i.e. after everything above it. EasyCrypt's -upto is exclusive (src/ec.ml `past_upto`)."""
    f = _resolve(path)
    n = len(f.read_text().splitlines())
    if not 1 <= line <= n:
        raise ECError(f"line {line} out of range (file has {n} lines)")
    pos = f"{line}:{col}" if col is not None else str(line)
    res = _llm(f, ["-upto", pos])
    if res.ok and not res.goals:
        res.note = ("No command starts at or after this position, so EasyCrypt printed no goals. "
                    "Use check_file for the end-of-file state.")
    return res


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
    # -upto is exclusive and prints goals only when it meets a later command, so stop at the
    # line after the snippet and append a stop marker in case nothing follows. The marker is
    # only parsed, never executed: EasyCrypt halts before running the first command past -upto.
    patched = lines[: at - 1] + [snip] + lines[at - 1 :] + ["qed.\n"]
    end_line = at - 1 + len(snip.splitlines())

    # Same directory so `require` of sibling theories resolves; unique name so parallel calls
    # don't collide. Theory name comes from the filename, so keep it a valid identifier.
    tmp = f.parent / f"Try_{uuid.uuid4().hex[:12]}{f.suffix}"
    try:
        tmp.write_text("".join(patched))
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