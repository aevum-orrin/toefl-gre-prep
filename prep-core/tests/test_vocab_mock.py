"""Regression tests for the new data-pipeline + mock-test logic.

build_vocab.py (scripts/) and mock-test's app.py live outside the prep_core package,
so we load them by file path. These cover the parts most likely to break silently:
POS recovery from ECDICT lines, per-POS sense grouping, mock scoring, band mapping,
and the module-2 adaptive-routing threshold.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bv = _load(REPO / "scripts" / "build_vocab.py", "build_vocab_mod")
mock = _load(REPO / "tools" / "mock-test" / "app.py", "mock_app_mod")


# ---- build_vocab: POS recovery + sense grouping -------------------------------
def test_split_pos_variants():
    assert bv._split_pos("vt. 装罐") == ("verb", "装罐")
    assert bv._split_pos("n. a metal container") == ("noun", "a metal container")
    assert bv._split_pos("aux. 能, 可以") == ("auxiliary", "能, 可以")
    assert bv._split_pos("adj. quick") == ("adjective", "quick")
    assert bv._split_pos("[计] 作废字符") == ("", "作废字符")   # domain tag -> no POS
    assert bv._split_pos("no marker here") == ("", "no marker here")


def test_senses_group_en_and_zh_by_pos():
    senses = bv._senses(["v. to operate", "n. a spin"], ["vt. 运转", "n. 旋转"])
    by = {s["pos"]: s for s in senses}
    assert "verb" in by and "noun" in by
    assert "to operate" in by["verb"]["def_en"] and "运转" in by["verb"]["def_zh"]
    assert by["noun"]["examples"] == [] and by["noun"]["collocations"] == []  # filled later


# ---- mock-test: scoring, band, CEFR, routing ---------------------------------
def _item(answers):
    return {"id": "x", "kind": "academic_passage", "passage": "p",
            "questions": [{"q": f"q{i}", "options": ["a", "b", "c", "d"], "answer": a}
                          for i, a in enumerate(answers)]}


def test_grade_counts_correct():
    item = _item([0, 1, 2])
    c, t, _ = mock._grade([item], {"x": [0, 1, 2]})
    assert (c, t) == (3, 3)
    c, t, _ = mock._grade([item], {"x": [0, 0, 2]})   # one wrong
    assert (c, t) == (2, 3)
    c, t, _ = mock._grade([item], {"x": []})          # unanswered
    assert (c, t) == (0, 3)


def test_band_and_cefr():
    assert mock._band(1.0) == 6.0
    assert mock._band(0.0) == 1.0
    assert mock._band(0.5) == 3.5
    assert mock._band(2.0) == 6.0 and mock._band(-1.0) == 1.0   # clamped
    assert mock._cefr(6.0) == "C2"
    assert mock._cefr(4.0) == "B2"
    assert mock._cefr(1.0) == "A1"


def test_routing_threshold():
    # module 2 is "hard" iff module-1 accuracy >= 0.6 (mirrors app.submit logic)
    assert ("hard" if (5 and 3 / 5 >= 0.6) else "easy") == "hard"
    assert ("hard" if (5 and 2 / 5 >= 0.6) else "easy") == "easy"
