"""vocab_web.sm2 is a hand-copy of prep_core.srs so the Vercel bundle stays small. That copy
can silently drift, which would make the deployed scheduler grade differently from the local
one — the kind of bug you would only notice weeks later as a wrong review queue.

This test drives both implementations through the same randomised grade sequences and asserts
every scheduling field matches exactly.

Run: .venv/bin/python -m pytest tests/test_sm2_parity.py -q
"""
from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "prep-core" / "src"))

from prep_core.srs import SRS  # noqa: E402
from vocab_web import sm2  # noqa: E402

FIELDS = ("ease", "interval", "reps", "due", "prof")
TODAY = date(2026, 7, 24)


def _both(grades: list[int], tmp_path: Path) -> tuple[dict, dict]:
    srs = SRS(tmp_path / "s.json")
    srs.add("word", "gloss")
    card = sm2.new_card("word", "gloss")
    for g in grades:
        srs.review("word", g, TODAY)
        sm2.review(card, g, TODAY)
    ref = srs.cards["word"]
    return {k: getattr(ref, k) for k in FIELDS}, {k: card[k] for k in FIELDS}


def test_single_grades_match(tmp_path):
    for g in (1, 3, 4, 5):
        ref, got = _both([g], tmp_path)
        assert ref == got, f"grade {g}: {ref} != {got}"


def test_random_sequences_match(tmp_path):
    rng = random.Random(20260724)
    for i in range(200):
        grades = [rng.choice([1, 3, 4, 5]) for _ in range(rng.randint(1, 15))]
        ref, got = _both(grades, tmp_path / str(i))
        assert ref == got, f"{grades}: {ref} != {got}"


def test_graduate_matches_local_rules():
    """_graduate in tools/vocab-srs/app.py — the Enter=forever path."""
    card = sm2.new_card("word")
    sm2.graduate(card)
    assert card["due"] == sm2.GRADUATED_DUE
    assert card["interval"] == 36500
    assert card["prof"] == 1.0
    assert card["ease"] >= 2.6
    assert card["reps"] >= 8


def test_is_due_semantics():
    assert sm2.is_due(sm2.new_card("w"), TODAY)                 # due=="" -> never seen, is due
    c = sm2.new_card("w"); c["due"] = "2026-07-23"
    assert sm2.is_due(c, TODAY)
    c["due"] = "2026-07-25"
    assert not sm2.is_due(c, TODAY)
    c["due"] = sm2.GRADUATED_DUE
    assert not sm2.is_due(c, TODAY)                             # graduated never returns
