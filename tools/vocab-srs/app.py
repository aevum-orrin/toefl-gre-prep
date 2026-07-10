"""vocab-srs: local SM-2 spaced-repetition trainer over big ECDICT-backed decks.

Deck JSON schema (built by scripts/build_vocab.py, enriched by scripts/enrich_vocab.py):
  [{term, phonetic, gloss_en,
    senses:[{pos, def_en[], def_zh[], examples[], collocations[]}],
    collins, oxford, bnc, frq, tags[], exchange{}}]

TOEFL and GRE are two decks (~7k words each) sharing one engine. Scheduling state
persists per deck in data/srs/<deck>.json (gitignored) and is joined to word
content by term. Because a fresh deck has thousands of never-seen cards, we cap how
many NEW cards are introduced per day (Anki-style, default 20) so a session stays
sane; reviews that come due are always shown first. New cards are introduced
most-frequent-first (deck JSON is frequency-sorted).

Run:  source ../../env.sh && uvicorn app:app --reload --port 8003
"""
from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import SRS

HERE = Path(__file__).parent
REPO = HERE.parents[1]
DATA_DIR = REPO / "data" / "srs"            # gitignored scheduling + intro state

DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
}

# Three buttons after Space: 1 Again (repeat in <1 day), 2 Hard (fuzzy), 3 Good (fine).
# "easy" is kept only for backward-compat; the 4th button is gone — a word you know cold
# is handled by Enter-before-reveal (graduate-forever) instead. Values are SM-2 grades.
GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}
DEFAULT_NEW_PER_DAY = 100000  # effectively unlimited: a 2-week sprint needs to blast whole deck

GRADUATED_DUE = "9999-12-31"  # a card marked "known" gets a due so far out it never returns
_CARD_FIELDS = ("ease", "interval", "reps", "due")
# Per-deck undo/redo stacks (single-user, single-process app). Each record captures a card's
# state before+after an action so Left=undo restores it and Right=redo re-applies it.
_UNDO: dict[str, list[dict]] = {}
_REDO: dict[str, list[dict]] = {}

CONTENT: dict[str, dict[str, dict]] = {}    # deck -> term -> full entry
ORDER: dict[str, list[str]] = {}            # deck -> terms, frequency-sorted
SRS_BY_DECK: dict[str, SRS] = {}


def _gloss(w: dict) -> str:
    """Short gloss stored on the SRS card (fallback only; UI serves from CONTENT)."""
    senses = w.get("senses") or [{}]
    zh = senses[0].get("def_zh") or []
    en = senses[0].get("def_en") or []
    return (zh[0] if zh else (en[0] if en else "")) or ""


def _load_deck(deck: str) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    CONTENT[deck] = {w["term"]: w for w in words}
    ORDER[deck] = [w["term"] for w in words]
    srs = SRS(DATA_DIR / f"{deck}.json")
    for w in words:                          # idempotent: add new terms, keep schedules
        srs.add(w["term"], _gloss(w))
    srs.save()
    SRS_BY_DECK[deck] = srs


for _d in DECK_FILES:
    _load_deck(_d)

app = FastAPI(title="Vocab SRS")


class Review(BaseModel):
    deck: str
    term: str
    grade: str                               # again | hard | good | easy


def _intro_path(deck: str) -> Path:
    return DATA_DIR / f"{deck}.intro.json"


def _intro_today(deck: str) -> int:
    p = _intro_path(deck)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return data.get(date.today().isoformat(), 0)


def _intro_adjust(deck: str, delta: int) -> None:
    p = _intro_path(deck)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    k = date.today().isoformat()
    data[k] = max(0, data.get(k, 0) + delta)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def _intro_bump(deck: str) -> None:
    _intro_adjust(deck, 1)


def _snap(card) -> dict:
    return {k: getattr(card, k) for k in _CARD_FIELDS}


def _restore(card, snap: dict) -> None:
    for k, v in snap.items():
        setattr(card, k, v)


def _record(deck: str, term: str, before: dict, after: dict, intro_delta: int) -> None:
    _UNDO.setdefault(deck, []).append(
        {"term": term, "before": before, "after": after, "intro_delta": intro_delta})
    _REDO[deck] = []  # any fresh action invalidates the redo chain


def _payload(deck: str, term: str, stats: dict, extra: dict | None = None) -> dict:
    """Build a next-card-style response body for a given term (used by /next and /undo)."""
    srs = SRS_BY_DECK[deck]
    card = srs.cards[term]
    kind = "new" if not card.due else "review"
    entry = CONTENT[deck].get(term, {"term": term})
    return {"done": False, "kind": kind, "reps": card.reps, **entry, **stats, **(extra or {})}


def _stats(deck: str, new_per_day: int = DEFAULT_NEW_PER_DAY) -> dict:
    srs = SRS_BY_DECK[deck]
    today = date.today()
    reviews = [c for c in srs.cards.values() if c.due and c.is_due(today)]  # due!="" => seen before
    new_pool = [c for c in srs.cards.values() if not c.due]                 # due=="" => never seen
    new_left = max(0, new_per_day - _intro_today(deck))
    return {"deck": deck, "total": len(srs.cards), "due": len(reviews),
            "new": min(len(new_pool), new_left), "new_pool": len(new_pool),
            "learned": len(srs.cards) - len(new_pool)}


@app.get("/api/decks")
def decks():
    return [_stats(d) for d in DECK_FILES if d in SRS_BY_DECK]


@app.get("/api/next")
def next_card(deck: str = "toefl", new_per_day: int = DEFAULT_NEW_PER_DAY):
    if deck not in SRS_BY_DECK:
        return {"error": f"unknown deck '{deck}'", "decks": list(SRS_BY_DECK)}
    srs = SRS_BY_DECK[deck]
    today = date.today()
    reviews = [c for c in srs.cards.values() if c.due and c.is_due(today)]
    stats = _stats(deck, new_per_day)

    card, kind = None, None
    if reviews:
        card, kind = random.choice(reviews), "review"
    elif stats["new"] > 0:
        for term in ORDER[deck]:             # most-frequent un-introduced word first
            c = srs.cards.get(term)
            if c and not c.due:
                card, kind = c, "new"
                break
    if card is None:
        return {"done": True, **stats}

    entry = CONTENT[deck].get(card.term, {"term": card.term})
    return {"done": False, "kind": kind, "reps": card.reps, **entry, **stats}


@app.post("/api/review")
def review(r: Review):
    srs = SRS_BY_DECK.get(r.deck)
    if srs is None or r.term not in srs.cards:
        return {"error": "unknown deck or term"}
    grade = GRADES.get(r.grade.lower())
    if grade is None:
        return {"error": f"bad grade '{r.grade}'; use {list(GRADES)}"}
    card = srs.cards[r.term]
    before = _snap(card)
    was_new = not card.due
    srs.review(r.term, grade)
    if r.grade.lower() == "again":       # "repeat in <1 day": make it due again today
        card.due = date.today().isoformat()
        card.interval = 0
    srs.save()
    if was_new:
        _intro_bump(r.deck)
    _record(r.deck, r.term, before, _snap(card), 1 if was_new else 0)
    return {"term": card.term, "interval_days": card.interval, "due": card.due,
            "ease": round(card.ease, 2), **_stats(r.deck)}


class DeckTerm(BaseModel):
    deck: str
    term: str


@app.post("/api/known")
def known(r: DeckTerm):
    """Graduate a word the user knows cold (Enter before reveal): never show it again."""
    srs = SRS_BY_DECK.get(r.deck)
    if srs is None or r.term not in srs.cards:
        return {"error": "unknown deck or term"}
    card = srs.cards[r.term]
    before = _snap(card)
    was_new = not card.due
    card.reps = max(card.reps, 8)
    card.interval = 36500
    card.ease = max(card.ease, 2.6)
    card.due = GRADUATED_DUE
    srs.save()
    if was_new:
        _intro_bump(r.deck)
    _record(r.deck, r.term, before, _snap(card), 1 if was_new else 0)
    return {"term": card.term, "known": True, **_stats(r.deck)}


class DeckOnly(BaseModel):
    deck: str


@app.post("/api/undo")
def undo(r: DeckOnly):
    """Left arrow: revert the last graded/graduated word to its prior state and re-show it."""
    stack = _UNDO.get(r.deck) or []
    if not stack:
        return {"none": True, **_stats(r.deck)}
    rec = stack.pop()
    srs = SRS_BY_DECK[r.deck]
    _restore(srs.cards[rec["term"]], rec["before"])
    srs.save()
    if rec["intro_delta"]:
        _intro_adjust(r.deck, -rec["intro_delta"])
    _REDO.setdefault(r.deck, []).append(rec)
    return _payload(r.deck, rec["term"], _stats(r.deck), {"undone": True})


@app.post("/api/redo")
def redo(r: DeckOnly):
    """Right arrow: cancel the undo — re-apply the action and move on."""
    stack = _REDO.get(r.deck) or []
    if not stack:
        return {"none": True, **_stats(r.deck)}
    rec = stack.pop()
    srs = SRS_BY_DECK[r.deck]
    _restore(srs.cards[rec["term"]], rec["after"])
    srs.save()
    if rec["intro_delta"]:
        _intro_adjust(r.deck, rec["intro_delta"])
    _UNDO.setdefault(r.deck, []).append(rec)
    return {"ok": True, **_stats(r.deck)}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
