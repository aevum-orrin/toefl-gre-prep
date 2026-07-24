"""SM-2 + proficiency card math, vendored from prep_core.srs so the Vercel bundle does not
need the whole prep-core package.

This is a faithful copy of `prep_core.srs.SRS.review` operating on a single card dict instead
of a file-backed collection. tests/test_sm2_parity.py asserts it stays bit-identical to
prep_core, so the deployed scheduler can never silently drift from the local one.
"""
from __future__ import annotations

from datetime import date, timedelta

PROF_REWARD = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.45, 4: 0.8, 5: 1.0}
PROF_ALPHA = 0.4
MAX_INTERVAL = 36500           # see prep_core.srs: guards `today + interval` against date.max

GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}
GRADUATED_DUE = "9999-12-31"
CARD_FIELDS = ("ease", "interval", "reps", "due", "prof")


def new_card(term: str, definition: str = "") -> dict:
    return {"term": term, "definition": definition, "ease": 2.5, "interval": 0,
            "reps": 0, "due": "", "prof": 0.5}


def is_due(card: dict, today: date) -> bool:
    return not card["due"] or date.fromisoformat(card["due"]) <= today


def review(card: dict, grade: int, today: date | None = None) -> dict:
    """Mutates and returns the card. Identical math to prep_core.srs.SRS.review."""
    today = today or date.today()
    card["prof"] = round((1 - PROF_ALPHA) * card["prof"] + PROF_ALPHA * PROF_REWARD.get(grade, 0.5), 4)
    if grade < 3:
        card["reps"] = 0
        card["interval"] = 1
        card["ease"] = max(1.3, card["ease"] - 0.2)
    else:
        card["reps"] += 1
        if card["reps"] == 1:
            card["interval"] = 1
        elif card["reps"] == 2:
            card["interval"] = 6
        else:
            card["interval"] = max(1, round(card["interval"] * card["ease"] * (0.5 + card["prof"])))
        card["interval"] = min(card["interval"], MAX_INTERVAL)
        card["ease"] = max(1.3, card["ease"] + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
    card["due"] = (today + timedelta(days=card["interval"])).isoformat()
    return card


def graduate(card: dict) -> dict:
    """Enter = 'I know it, never show me again'."""
    card["reps"] = max(card["reps"], 8)
    card["interval"] = 36500
    card["ease"] = max(card["ease"], 2.6)
    card["due"] = GRADUATED_DUE
    card["prof"] = 1.0
    return card


def snapshot(card: dict) -> dict:
    return {k: card[k] for k in CARD_FIELDS}


def restore(card: dict, snap: dict) -> dict:
    card.update(snap)
    return card
