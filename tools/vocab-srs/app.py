"""vocab-srs: local spaced-repetition (SM-2) vocabulary trainer — the "背词小网页".

Exam-agnostic: it just reads word-list JSONs and schedules reviews with prep_core.SRS. TOEFL and
GRE are two decks sharing one engine. Scheduling state persists per deck under data/srs/ (gitignored);
word content (definition/example/pos) stays in the exam folder's wordlist and is joined by term.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8003
Open http://localhost:8003
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import SRS

HERE = Path(__file__).parent
REPO = HERE.parents[1]
DATA_DIR = REPO / "data" / "srs"            # gitignored scheduling state

# deck -> wordlist JSON ([{term, definition, example, pos}]).
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
}

# Anki-style buttons -> SM-2 grade (0-5). Again fails (resets); Hard/Good/Easy pass.
GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}

CONTENT: dict[str, dict[str, dict]] = {}    # deck -> term -> {definition, example, pos}
SRS_BY_DECK: dict[str, SRS] = {}


def _load_deck(deck: str) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    CONTENT[deck] = {w["term"]: w for w in words}
    srs = SRS(DATA_DIR / f"{deck}.json")
    for w in words:                          # idempotent: add new terms, keep existing schedules
        srs.add(w["term"], w.get("definition", ""))
    srs.save()
    SRS_BY_DECK[deck] = srs


for _d in DECK_FILES:
    _load_deck(_d)

app = FastAPI(title="Vocab SRS")


class Review(BaseModel):
    deck: str
    term: str
    grade: str                               # again | hard | good | easy


def _stats(deck: str) -> dict:
    srs = SRS_BY_DECK[deck]
    due = srs.due_cards()
    new = [c for c in srs.cards.values() if not c.due]
    return {"deck": deck, "total": len(srs.cards), "due": len(due), "new": len(new)}


@app.get("/api/decks")
def decks():
    return [_stats(d) for d in DECK_FILES if d in SRS_BY_DECK]


@app.get("/api/next")
def next_card(deck: str = "toefl"):
    if deck not in SRS_BY_DECK:
        return {"error": f"unknown deck '{deck}'", "decks": list(SRS_BY_DECK)}
    srs = SRS_BY_DECK[deck]
    due = srs.due_cards()
    if not due:
        return {"done": True, **_stats(deck)}
    # Prioritize never-seen cards, then a random due one, to vary order.
    fresh = [c for c in due if not c.due]
    card = random.choice(fresh) if fresh else random.choice(due)
    w = CONTENT[deck].get(card.term, {})
    return {"done": False, "term": card.term, "definition": w.get("definition", card.definition),
            "example": w.get("example", ""), "pos": w.get("pos", ""),
            "reps": card.reps, **_stats(deck)}


@app.post("/api/review")
def review(r: Review):
    srs = SRS_BY_DECK.get(r.deck)
    if srs is None or r.term not in srs.cards:
        return {"error": "unknown deck or term"}
    grade = GRADES.get(r.grade.lower())
    if grade is None:
        return {"error": f"bad grade '{r.grade}'; use {list(GRADES)}"}
    card = srs.review(r.term, grade)
    srs.save()
    return {"term": card.term, "interval_days": card.interval, "due": card.due,
            "ease": round(card.ease, 2), **_stats(r.deck)}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
