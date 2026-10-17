"""Tests against a REAL easycrypt binary. Skipped automatically when none is on PATH,
so `pytest tests` still works locally with just the fake.

Inside the image:
  docker run --rm -v "$PWD:$PWD" -w "$PWD" easycrypt-mcp \
    sh -c 'pip3 install --user --break-system-packages -q pytest && python3 -m pytest -q tests/test_real.py'

Each test pins one claim from ARCHITECTURE.md §3 / §7 so that a regression in
EasyCrypt's output format, or in our parser, fails loudly with the raw output.
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

BIN = shutil.which(os.environ.get("EASYCRYPT_BIN", "easycrypt"))
pytestmark = pytest.mark.skipif(BIN is None, reason="no real easycrypt on PATH")

import easycrypt_core as ec  # noqa: E402


@pytest.fixture(autouse=True)
def _use_real_binary(monkeypatch):
    monkeypatch.setattr(ec, "EC_BIN", BIN)

GOOD = "lemma t : true.\nproof.\ntrivial.\nqed.\n"
# `by trivial.` not `trivial.`: bare `trivial` never fails, it just leaves the goal open and
# the error surfaces at `qed.` ("cannot save an incomplete proof") one line later. [run]-verified.
BAD = "lemma t : false.\nproof.\nby trivial.\nqed.\n"


def make(tmp_path, body, name="T.ec"):
    f = tmp_path / name
    f.write_text(body)
    return f


def test_config_detects_a_solver():
    c = ec.config()
    assert c["ok"], c["output"]
    assert any(p in c["output"] for p in ("Alt-Ergo", "Z3", "CVC5")), c["output"]


def test_check_file_good_and_bad(tmp_path):
    assert ec.check_file(str(make(tmp_path, GOOD))).ok

    r = ec.check_file(str(make(tmp_path, BAD)))
    assert not r.ok and r.exit_code == 1
    # B2: the proof error must be PARSED (file: line L (c-d) form), not dumped raw.
    assert r.diagnostics, f"nothing parsed from stderr: {r.raw_stderr!r}"
    d = r.diagnostics[0]
    assert d.severity == "critical", d
    assert d.line == 3, d  # the failing `by trivial.`
    assert d.file.endswith("T.ec"), d
    # -lastgoals printed the remaining goal to stdout
    assert "false" in r.goals, r.goals


def test_goals_at_is_state_before_the_line(tmp_path):
    # §2: goals_at(L) = state before the command starting at L runs (-upto is exclusive)
    r = ec.goals_at(str(make(tmp_path, GOOD)), 3)
    assert r.ok, r
    assert "true" in r.goals, r.goals


def test_try_snippet_actually_runs_the_snippet(tmp_path):
    # B1: a one-line snippet must be executed; a failing tactic must fail.
    f = make(tmp_path, "lemma t : true.\nproof.\nqed.\n")
    bad = ec.try_snippet(str(f), "rewrite no_such_lemma.", line=3)
    assert not bad.ok, "snippet was not executed — -upto off-by-one (B1)"
    assert bad.diagnostics and bad.diagnostics[0].line == 3, bad

    good = ec.try_snippet(str(f), "trivial.", line=3)
    assert good.ok, good
    assert f.read_text() == "lemma t : true.\nproof.\nqed.\n"  # untouched


def test_print_output_comes_back_on_stdout(tmp_path):
    # D5: `print` is usable through try_snippet (search is not: Info-level, filtered).
    # Appended after `qed.` there is no next command to stop at, so the run goes to EOF;
    # stdout still carries the print output.
    r = ec.try_snippet(str(make(tmp_path, GOOD)), "print t.")
    assert r.ok, r
    assert "lemma t" in r.goals, r.goals
