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

def test_apply_snippet_writes_and_commits(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    body = "lemma l : true.\nproof.\nqed.\n"
    f = make(tmp_path, body)
    bad = ec.apply_snippet(str(f), "FAIL.", line=3)
    assert not bad.ok and f.read_text() == body and bad.commit == ""
    good = ec.apply_snippet(str(f), "trivial.", line=3)
    assert good.ok and f.read_text() == "lemma l : true.\nproof.\ntrivial.\nqed.\n"
    assert good.commit, good.note
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "agent: trivial." in log


def test_apply_snippet_outside_a_repo(tmp_path_factory):
    # written, not committed, still ok
    d = tmp_path_factory.mktemp("norepo")  # sibling of tmp_path, not inside any repo
    f = make(d, "lemma l : true.\nproof.\nqed.\n")
    r = ec.apply_snippet(str(f), "trivial.", line=3)
    assert r.ok and r.commit == "" and "Not committed" in r.note, r.note
    assert f.read_text() == "lemma l : true.\nproof.\ntrivial.\nqed.\n"


def test_search_lib(tmp_path, monkeypatch):
    lib = tmp_path / "theories"
    (lib / "sub").mkdir(parents=True)
    (lib / "DBool.ec").write_text("theory DBool.\n  (* dbool1E is used below *)\nlemma dbool1E b : mu1 dbool b = 1%r/2%r.\nend DBool.\n")
    (lib / "sub" / "X.eca").write_text("op foo : int.\n")
    (lib / "README.md").write_text("foo dbool1E\n")  # not .ec: ignored
    monkeypatch.setattr(ec, "THEORIES_ROOT", str(lib))
    r = ec.search_lib("dbool1e")
    assert r["total"] == 2 and r["matches"][0]["line"] == 3  # declaration first
    assert ec.search_lib("foo")["matches"] == [{"file": "sub/X.eca", "line": 1, "text": "op foo : int."}]
    import pytest
    with pytest.raises(ec.ECError):
        ec.search_lib("(")
