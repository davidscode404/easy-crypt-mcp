"""EasyCrypt wrapper core: no web framework, no MCP. Both servers import this.

Route A (file-as-state): every call shells out to `easycrypt llm`; nothing is held in memory.

Config (env vars):
  EASYCRYPT_BIN    path to easycrypt binary (default "easycrypt")
  EASYCRYPT_ARGS   extra args for every `llm` call, e.g. "-p Alt-Ergo -p Z3 -timeout 10"
                   (check exact flag names with `easycrypt llm -help` once built)
  EASYCRYPT_ROOT   if set, only files under this directory may be checked
  EASYCRYPT_WALL   wall-clock limit per call in seconds (default 120)
  EASYCRYPT_THEORIES   stdlib dir for search_lib (default: first `<system>@` entry of `easycrypt config`)
  EASYCRYPT_GIT_AUTHOR author of apply_snippet commits (default "easycrypt-agent <agent@easycrypt-mcp>")
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
THEORIES_ROOT = os.environ.get("EASYCRYPT_THEORIES")
GIT_AUTHOR = os.environ.get("EASYCRYPT_GIT_AUTHOR", "easycrypt-agent <agent@easycrypt-mcp>")

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
    commit: str = ""      # apply_snippet only: short sha of the commit it made, "" if none

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


# ---------------------------------------------------------------- snippets

def _patch(f: Path, snippet: str, line: int | None) -> tuple[str, int, int]:
    """(patched text, first line, last line) with SNIPPET inserted before LINE (default: EOF)."""
    lines = f.read_text().splitlines(keepends=True)
    at = len(lines) + 1 if line is None else line
    if not 1 <= at <= len(lines) + 1:
        raise ECError(f"line {line} out of range (file has {len(lines)} lines)")
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    snip = snippet if snippet.endswith("\n") else snippet + "\n"
    patched = lines[: at - 1] + [snip] + lines[at - 1 :]
    return "".join(patched), at, at - 1 + len(snip.splitlines())


def _check_patch(f: Path, text: str, end_line: int) -> Result:
    """Check TEXT (a patched copy of F) through END_LINE, in a temp file next to F."""
    # Same directory so `require` of sibling theories resolves; unique name so parallel calls
    # don't collide. Theory name comes from the filename, so keep it a valid identifier.
    tmp = f.parent / f"Try_{uuid.uuid4().hex[:12]}{f.suffix}"
    try:
        tmp.write_text(text)
        # `-upto L` stops BEFORE the command starting at line L (exclusive, src/ec.ml
        # `past_upto`), so to execute the whole snippet we stop at the line after it.
        res = _llm(tmp, ["-upto", str(end_line + 1)])
    finally:
        for p in (tmp, tmp.with_suffix(".eco")):
            p.unlink(missing_ok=True)
    for d in res.diagnostics:
        if Path(d.file).name == tmp.name:
            d.file = f.name
    return res


def try_snippet(path: str, snippet: str, line: int | None = None) -> Result:
    """Insert SNIPPET before LINE (default: end of file) in a temp copy, check through the
    end of the snippet, and report goals there. Never touches the original file."""
    f = _resolve(path)
    text, at, end_line = _patch(f, snippet, line)
    res = _check_patch(f, text, end_line)
    res.note = (f"Snippet occupied lines {at}-{end_line} of a temp copy; "
                f"diagnostic line numbers refer to that copy. Original file unchanged.")
    return res


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    # safe.directory=*: the mounted repo is usually owned by a different uid than the container user
    return subprocess.run(["git", "-c", "safe.directory=*", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=60)


def _commit(f: Path, message: str) -> tuple[str, str]:
    """Commit F. Returns (short sha, "") or ("", why it was not committed)."""
    try:
        top = _git(["rev-parse", "--show-toplevel"], f.parent)
    except FileNotFoundError:
        return "", "git not installed"
    if top.returncode != 0:
        return "", "not inside a git repository"
    name, _, email = GIT_AUTHOR.rpartition(" <")
    _git(["add", "--", str(f)], f.parent)
    r = _git(["-c", f"user.name={name or GIT_AUTHOR}", "-c", f"user.email={email.rstrip('>')}",
              "commit", "-q", "-m", message, "--", str(f)], f.parent)
    if r.returncode != 0:
        return "", (r.stderr or r.stdout).strip() or "git commit failed"
    return _git(["rev-parse", "--short", "HEAD"], f.parent).stdout.strip(), ""


def apply_snippet(path: str, snippet: str, line: int | None = None, commit: bool = True) -> Result:
    """try_snippet, and if the check passes, write the result into the real file and commit it
    as `agent: <first line of snippet>`. On failure nothing is written."""
    f = _resolve(path)
    text, at, end_line = _patch(f, snippet, line)
    res = _check_patch(f, text, end_line)
    if not res.ok:
        res.note = "Check failed; file unchanged."
        return res
    f.write_text(text)
    res.note = f"Wrote lines {at}-{end_line} of {f.name}."
    if commit:
        sha, why = _commit(f, f"agent: {snippet.strip().splitlines()[0][:72]}")
        res.commit = sha
        res.note += f" Committed {sha}." if sha else f" Not committed: {why}."
    return res


# ---------------------------------------------------------------- library search

_DECL = ("lemma", "local lemma", "axiom", "op", "abbrev", "theory", "abstract theory",
         "module", "type", "pred", "inductive", "hint", "declare", "clone")


def theories_root() -> Path:
    """EasyCrypt's standard library: $EASYCRYPT_THEORIES, else the first `<system>@…` entry
    of `easycrypt config`'s load-path (cached)."""
    global THEORIES_ROOT
    if not THEORIES_ROOT:
        for ln in config()["output"].splitlines():
            if ln.strip().startswith("<system>@"):
                THEORIES_ROOT = ln.strip()[len("<system>@"):]
                break
        else:
            raise ECError("cannot locate EasyCrypt's theories; set EASYCRYPT_THEORIES")
    return Path(THEORIES_ROOT)


def search_lib(pattern: str, limit: int = 40) -> dict:
    """Case-insensitive regex search over the standard library. Declaration lines first.
    (EasyCrypt's own `search` command prints nothing in batch mode: its output is Info-level
    and the `llm` terminal only shows Warning and above.)"""
    if not pattern.strip():
        raise ECError("empty pattern")
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ECError(f"bad regex {pattern!r}: {e}")
    root = theories_root()
    decls: list[dict] = []
    others: list[dict] = []
    for p in sorted(root.rglob("*")):
        if p.suffix not in (".ec", ".eca") or not p.is_file():
            continue
        for i, ln in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if rx.search(ln):
                hit = {"file": os.path.relpath(p, root), "line": i, "text": ln.strip()[:200]}
                (decls if ln.lstrip().startswith(_DECL) else others).append(hit)
    hits = decls + others
    return {"ok": True, "root": str(root), "pattern": pattern,
            "total": len(hits), "matches": hits[:limit]}
