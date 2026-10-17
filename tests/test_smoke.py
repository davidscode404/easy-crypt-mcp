"""Run: python -m pytest -q tests   (uses the fake binary)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

import easycrypt_core as ec  # noqa: E402


@pytest.fixture(autouse=True)
def _use_fake_binary(monkeypatch):
    # per-test, so it cannot leak into / be clobbered by tests/test_real.py
    monkeypatch.setattr(ec, "EC_BIN", str(HERE / "fake_easycrypt.py"))


def make(tmp_path, body):
    f = tmp_path / "Toy.ec"
    f.write_text(body)
    return f


def test_parse_real_format():
    d, left = ec.parse_diagnostics("[error] [Foo.ec:12:3] bad\n  more\n[warning] [Foo.ec:2] w")
    assert [(x.severity, x.line, x.col) for x in d] == [("error", 12, 3), ("warning", 2, None)]
    assert d[0].message == "bad\n  more" and left == ""
    # the format real proof errors use (ecLocation.tostring)
    d2, left2 = ec.parse_diagnostics(
        "[critical] [Foo.ec: line 12 (3-10)] cannot apply\n"
        "[critical] [Foo.ec: line 5 (1) to line 7 (4)] x\n"
        "[critical] [Foo.ec: line 9 (2)] y")
    assert [(x.line, x.col) for x in d2] == [(12, 3), (5, 1), (9, 2)] and left2 == ""


def test_check_ok_and_fail(tmp_path):
    assert ec.check_file(str(make(tmp_path, "lemma l : true.\nproof. trivial. qed.\n"))).ok
    r = ec.check_file(str(make(tmp_path, "lemma l : true.\nproof. admit. qed.\n")))
    assert not r.ok and r.diagnostics[0].line == 2 and "forall" in r.goals


def test_goals_at(tmp_path):
    r = ec.goals_at(str(make(tmp_path, "a\nb\nc\n")), 2)
    assert r.ok and "line 2" in r.goals


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