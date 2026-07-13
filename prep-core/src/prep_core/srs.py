"""Spaced-repetition (SM-2 + proficiency) vocabulary trainer. Exam-agnostic: TOEFL and GRE
just feed it different word lists. State persists as JSON so any front-end can drive it.

On top of classic SM-2, every card carries `prof` — a 0..1 proficiency estimate updated as a
reward-EMA over the card's WHOLE grade history (the "reinforcement" signal the user asked
for: every encounter's grade is a reward; recent evidence dominates but old lapses linger).
`prof` then modulates how fast SM-2 intervals grow, so a word that keeps earning "good"
after an early "again" still climbs slower than one that was always easy."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path

# reward per SM-2 grade: fails pull hard toward 0, passes push up by their strength
PROF_REWARD = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.45, 4: 0.8, 5: 1.0}
PROF_ALPHA = 0.4               # EMA step: prof' = (1-α)·prof + α·reward


@dataclass
class Card:
    term: str
    definition: str
    ease: float = 2.5          # SM-2 easiness factor
    interval: int = 0          # days until next review
    reps: int = 0
    due: str = ""              # ISO date; "" means due now (never reviewed)
    prof: float = 0.5          # proficiency 0..1 (reward-EMA); 0.5 = neutral prior

    def is_due(self, today: date) -> bool:
        return not self.due or date.fromisoformat(self.due) <= today


class SRS:
    """SM-2. grade: 0-5 (0-2 = fail/again, 3-5 = pass with increasing ease)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.cards: dict[str, Card] = {}
        if self.path.exists():
            for d in json.loads(self.path.read_text(encoding="utf-8")):
                self.cards[d["term"]] = Card(**d)

    def add(self, term: str, definition: str) -> Card:
        card = self.cards.get(term) or Card(term=term, definition=definition)
        card.definition = definition
        self.cards[term] = card
        return card

    def due_cards(self, today: date | None = None) -> list[Card]:
        today = today or date.today()
        return [c for c in self.cards.values() if c.is_due(today)]

    def review(self, term: str, grade: int, today: date | None = None) -> Card:
        today = today or date.today()
        card = self.cards[term]
        card.prof = round((1 - PROF_ALPHA) * card.prof + PROF_ALPHA * PROF_REWARD.get(grade, 0.5), 4)
        if grade < 3:
            card.reps = 0
            card.interval = 1
            card.ease = max(1.3, card.ease - 0.2)          # failing also dents ease (Anki-style)
        else:
            card.reps += 1
            if card.reps == 1:
                card.interval = 1
            elif card.reps == 2:
                card.interval = 6
            else:
                # proficiency scales the growth: prof=0.5 → plain SM-2, prof→1 up to 1.5×,
                # prof→0 down to 0.5× (a historically shaky word returns noticeably sooner)
                card.interval = max(1, round(card.interval * card.ease * (0.5 + card.prof)))
            card.ease = max(1.3, card.ease + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
        card.due = (today + timedelta(days=card.interval)).isoformat()
        return card

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(c) for c in self.cards.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
