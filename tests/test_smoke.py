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
    # Captured verbatim from EasyCrypt r2026.09, plus the other two forms from ecLocation.ml.
    d, left = ec.parse_diagnostics(
        "[critical] [Bad.ec: line 2 (16-20)] cannot save an incomplete proof\n"
        "  more detail\n"
        "[warning] [My File.ec: line 5 (3)] point\n"
        "[error] [sub/X.ec: line 2 (16) to line 4 (3)] span\n"
        "[warning] [Bad.ec:7] prover not found\n"  # notice without a precise location (subloc=None)
    )
    assert [(x.severity, x.file, x.line, x.col, x.end_line, x.end_col) for x in d] == [
        ("critical", "Bad.ec", 2, 16, 2, 20),
        ("warning", "My File.ec", 5, 3, 5, 3),
        ("error", "sub/X.ec", 2, 16, 4, 3),
        ("warning", "Bad.ec", 7, None, 7, None),
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

def test_apply_snippet_writes_and_commits(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    body = "lemma l : true.\nproof.\nqed.\n"
    f = make(tmp_path, body)
    bad = ec.apply_snippet(str(f), "FAIL.", line=3)
    assert not bad.ok and f.read_text() == body and bad.commit == ""
    good = ec.apply_snippet(str(f), "close.", line=3)
    assert good.ok and f.read_text() == "lemma l : true.\nproof.\nclose.\nqed.\n"  # no stop marker leaked
    assert good.commit, good.note
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "agent: close." in log


def test_apply_snippet_outside_a_repo(tmp_path_factory):
    d = tmp_path_factory.mktemp("norepo")  # not inside any repo
    f = make(d, "lemma l : true.\nproof.\nqed.\n")
    r = ec.apply_snippet(str(f), "close.", line=3)
    assert r.ok and r.commit == "" and "Not committed" in r.note, r.note


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
    with pytest.raises(ec.ECError):
        ec.search_lib("(")


def test_snippet_inherits_indentation(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    f = make(tmp_path, "lemma l : true.\n  proof.\n  qed.\n")
    r = ec.apply_snippet(str(f), "close.", line=3)
    assert r.ok and f.read_text() == "lemma l : true.\n  proof.\n  close.\n  qed.\n"


def test_negative_line_notice_is_parsed():
    d, left = ec.parse_diagnostics("[warning] [elgamal.ec:-1] running on OCaml 5.2.1: regression\n")
    assert left == "" and d[0].severity == "warning" and d[0].line == -1
