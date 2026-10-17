"""Run: cd ec_agent && python -m pytest -q tests   (uses the fake binary)."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
os.environ["EASYCRYPT_BIN"] = str(HERE / "fake_easycrypt.py")
sys.path.insert(0, str(HERE.parent))

import easycrypt_core as ec  # noqa: E402


def make(tmp_path, body):
    f = tmp_path / "Toy.ec"
    f.write_text(body)
    return f


def test_parse_real_format():
    # Captured verbatim from EasyCrypt r2026.09, plus the other two forms from ecLocation.ml.
    d, left = ec.parse_diagnostics(
        "[critical] [Bad.ec: line 2 (16-20)] cannot save an incomplete proof\n"
        "  more detail\n"
        "[warning] [My File.ec: line 5 (3)] point\n"
        "[error] [sub/X.ec: line 2 (16) to line 4 (3)] span\n"
    )
    assert [(x.severity, x.file, x.line, x.col, x.end_line, x.end_col) for x in d] == [
        ("critical", "Bad.ec", 2, 16, 2, 20),
        ("warning", "My File.ec", 5, 3, 5, 3),
        ("error", "sub/X.ec", 2, 16, 4, 3),
    ]
    assert d[0].message == "cannot save an incomplete proof\n  more detail" and left == ""


def test_unparsed_output_is_surfaced():
    d, left = ec.parse_diagnostics("something unexpected\n")
    assert d == [] and left == "something unexpected"


def test_check_ok_and_fail(tmp_path):
    assert ec.check_file(str(make(tmp_path, "lemma l : true.\nproof. trivial. qed.\n"))).ok
    r = ec.check_file(str(make(tmp_path, "lemma l : true.\nproof. admit. qed.\n")))
    assert not r.ok and r.diagnostics[0].line == 2 and "false" in r.goals


def test_goals_at_is_exclusive(tmp_path):
    f = make(tmp_path, "lemma l : false.\nclose.\nqed.\n")
    assert "false" in ec.goals_at(str(f), 2).goals          # before `close` runs
    assert ec.goals_at(str(f), 3).goals == "No more goals"  # after it


def test_try_snippet_reports_state_after_snippet(tmp_path):
    # Regression: real -upto is exclusive; the snippet must actually run, mid-file and at EOF.
    f = make(tmp_path, "lemma l : false.\nproof.\nqed.\n")
    assert ec.try_snippet(str(f), "close.", line=3).goals == "No more goals"
    assert ec.try_snippet(str(f), "close.").goals == "No more goals"  # appended at end of file
    assert "false" in ec.try_snippet(str(f), "proof.", line=3).goals


def test_try_snippet_never_mutates(tmp_path):
    f = make(tmp_path, "lemma l : true.\nproof.\nqed.\n")
    before = f.read_text()
    assert ec.try_snippet(str(f), "trivial.", line=3).ok
    bad = ec.try_snippet(str(f), "FAIL.", line=3)
    assert not bad.ok and bad.diagnostics[0].file == "Toy.ec" and bad.diagnostics[0].line == 3
    assert f.read_text() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Toy.ec"]  # temp files cleaned up


def test_bad_inputs(tmp_path):
    import pytest
    with pytest.raises(ec.ECError):
        ec.goals_at(str(make(tmp_path, "a\n")), 99)
    with pytest.raises(ec.ECError):
        ec.check_file(str(tmp_path / "nope.ec"))