"""Data access. Every function here replaces something the local app did with a file or a
process-global dict. Queries are written so a single request touches one connection and a
handful of indexed rows — never the whole 22k-row deck.
"""
from __future__ import annotations

import json
import random
from datetime import date

from .db import USER_ID, conn
from . import sm2

DEFAULT_NEW_PER_DAY = 100000        # effectively unlimited, same as the local app


# ---------------------------------------------------------------- deck content

def decks() -> list[str]:
    with conn() as c:
        rows = c.execute("SELECT DISTINCT deck FROM words ORDER BY deck").fetchall()
    return [r["deck"] for r in rows]


def all_stats(new_per_day: int = DEFAULT_NEW_PER_DAY) -> list[dict]:
    """Counters for every deck in ONE round trip — this is the page-load call, and doing it
    per deck meant three separate queries."""
    today = date.today().isoformat()
    with conn() as c:
        rows = c.execute(
            """SELECT s.deck,
                      count(*) AS total,
                      count(*) FILTER (WHERE s.due <> '' AND s.due <= %s) AS due,
                      count(*) FILTER (WHERE s.due = '')                 AS new_pool,
                      COALESCE(max(i.n), 0) AS intro
                 FROM srs_cards s
                 LEFT JOIN intro_counts i
                        ON i.user_id=s.user_id AND i.deck=s.deck AND i.day=%s
                WHERE s.user_id=%s
             GROUP BY s.deck ORDER BY s.deck""",
            (today, date.today(), USER_ID)).fetchall()
    out = []
    for r in rows:
        new_left = max(0, new_per_day - r["intro"])
        out.append({"deck": r["deck"], "total": r["total"], "due": r["due"],
                    "new": min(r["new_pool"], new_left), "new_pool": r["new_pool"],
                    "learned": r["total"] - r["new_pool"]})
    return out


def entry(deck: str, term: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT entry FROM words WHERE deck=%s AND term=%s",
                        (deck, term)).fetchone()
    return row["entry"] if row else None


def search(deck: str, q: str, limit: int = 60) -> dict:
    """Contiguous-substring lookup over one deck. Prefix matches first, then deck (`ord`)
    order — the same ordering the local app produced by scanning ORDER[deck]."""
    q = q.strip().lower()
    if len(q) < 2:
        return {"q": q, "hits": [], "total": 0}
    with conn() as c:
        # LIMIT in SQL, with count(*) OVER () carrying the full total — the old version pulled
        # every match back just to slice it in Python and count the list.
        rows = c.execute(
            """SELECT term, tier,
                      entry->'senses'->0->'def_zh'->>0 AS zh,
                      (lower(term) LIKE %s) AS starts,
                      count(*) OVER () AS total
                 FROM words
                WHERE deck=%s AND lower(term) LIKE %s
             ORDER BY starts DESC, ord
                LIMIT %s""",
            (f"{q}%", deck, f"%{q}%", limit)).fetchall()
    hits = [{"term": r["term"], "zh": r["zh"] or "", "tier": r["tier"],
             "starts": r["starts"]} for r in rows]
    return {"q": q, "hits": hits, "total": rows[0]["total"] if rows else 0}


# ---------------------------------------------------------------- cards

def get_card(deck: str, term: str) -> dict | None:
    with conn() as c:
        row = c.execute(
            """SELECT term, definition, ease, interval, reps, due, prof, flags
                 FROM srs_cards WHERE user_id=%s AND deck=%s AND term=%s""",
            (USER_ID, deck, term)).fetchone()
    return dict(row) if row else None


def card_with_entry(c, deck: str, term: str) -> dict | None:
    """Schedule + deck content in one round trip — the pair every card render needs."""
    row = c.execute(
        """SELECT s.term, s.definition, s.ease, s.interval, s.reps, s.due, s.prof, s.flags,
                  w.entry
             FROM srs_cards s LEFT JOIN words w ON w.deck=s.deck AND w.term=s.term
            WHERE s.user_id=%s AND s.deck=%s AND s.term=%s""",
        (USER_ID, deck, term)).fetchone()
    return dict(row) if row else None


def save_card(deck: str, card: dict, flags: dict | None) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO srs_cards (user_id, deck, term, definition, ease, interval,
                                      reps, due, prof, flags)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, deck, term) DO UPDATE SET
                 ease=EXCLUDED.ease, interval=EXCLUDED.interval, reps=EXCLUDED.reps,
                 due=EXCLUDED.due, prof=EXCLUDED.prof, flags=EXCLUDED.flags""",
            (USER_ID, deck, card["term"], card.get("definition", ""), card["ease"],
             card["interval"], card["reps"], card["due"], card["prof"],
             json.dumps(flags or {})))


# ---------------------------------------------------------------- daily new-word counter

def intro_today(deck: str) -> int:
    with conn() as c:
        row = c.execute("SELECT n FROM intro_counts WHERE user_id=%s AND deck=%s AND day=%s",
                        (USER_ID, deck, date.today())).fetchone()
    return row["n"] if row else 0


def intro_adjust(deck: str, delta: int) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO intro_counts (user_id, deck, day, n) VALUES (%s,%s,%s,GREATEST(0,%s))
               ON CONFLICT (user_id, deck, day)
               DO UPDATE SET n = GREATEST(0, intro_counts.n + %s)""",
            (USER_ID, deck, date.today(), delta, delta))


# ---------------------------------------------------------------- stats & scheduling

def stats(deck: str, new_per_day: int = DEFAULT_NEW_PER_DAY) -> dict:
    """Counters + today's new-word allowance in ONE round trip (this runs on every request,
    so the intro count is folded in as a subquery rather than a second query)."""
    today = date.today().isoformat()
    with conn() as c:
        row = c.execute(
            """SELECT count(*) AS total,
                      count(*) FILTER (WHERE due <> '' AND due <= %s) AS due,
                      count(*) FILTER (WHERE due = '')                AS new_pool,
                      COALESCE((SELECT n FROM intro_counts
                                 WHERE user_id=%s AND deck=%s AND day=%s), 0) AS intro
                 FROM srs_cards WHERE user_id=%s AND deck=%s""",
            (today, USER_ID, deck, date.today(), USER_ID, deck)).fetchone()
    new_left = max(0, new_per_day - row["intro"])
    return {"deck": deck, "total": row["total"], "due": row["due"],
            "new": min(row["new_pool"], new_left), "new_pool": row["new_pool"],
            "learned": row["total"] - row["new_pool"]}


def pick_next(deck: str, new_per_day: int, exclude: list[str]) -> tuple[dict | None, str, dict]:
    """Priority, identical to the local app:
      1. today's 'Again' lapses (interval=0) whose spacing gap has elapsed
      2. brand-new words in deck order (`ord`), while the daily cap allows
      3. ordinary due reviews
      4. if only recently-shown cards remain, show one anyway rather than stalling
    `exclude` is the client's recently-shown buffer — the local app kept this in process
    memory (`_RECENT`), which cannot survive a stateless function.
    """
    today = date.today().isoformat()
    ex = exclude or [""]
    st = stats(deck, new_per_day)
    with conn() as c:
        # ORDER BY random() LIMIT 1 keeps the pick in the database instead of shipping every
        # due term back just to choose one (the old code fetched all ~76 rows per keypress).
        lapsed = c.execute(
            """SELECT term FROM srs_cards
                WHERE user_id=%s AND deck=%s AND due <> '' AND due <= %s
                  AND interval = 0 AND NOT (term = ANY(%s))
             ORDER BY random() LIMIT 1""",
            (USER_ID, deck, today, ex)).fetchone()
        if lapsed:
            return card_with_entry(c, deck, lapsed["term"]), "review", st

        if st["new"] > 0:
            row = c.execute(
                """SELECT s.term FROM srs_cards s JOIN words w ON w.deck=s.deck AND w.term=s.term
                    WHERE s.user_id=%s AND s.deck=%s AND s.due=''
                 ORDER BY w.ord LIMIT 1""",
                (USER_ID, deck)).fetchone()
            if row:
                return card_with_entry(c, deck, row["term"]), "new", st

        review = c.execute(
            """SELECT term FROM srs_cards
                WHERE user_id=%s AND deck=%s AND due <> '' AND due <= %s
                  AND NOT (term = ANY(%s))
             ORDER BY random() LIMIT 1""",
            (USER_ID, deck, today, ex)).fetchone()
        if review:
            return card_with_entry(c, deck, review["term"]), "review", st

        any_due = c.execute(
            """SELECT term FROM srs_cards
                WHERE user_id=%s AND deck=%s AND due <> '' AND due <= %s LIMIT 1""",
            (USER_ID, deck, today)).fetchone()
        if any_due:
            return card_with_entry(c, deck, any_due["term"]), "review", st
    return None, "", st


# ---------------------------------------------------------------- undo / redo stacks

def _stacks(deck: str) -> dict:
    with conn() as c:
        row = c.execute("SELECT undo, redo FROM action_stacks WHERE user_id=%s AND deck=%s",
                        (USER_ID, deck)).fetchone()
    return {"undo": row["undo"], "redo": row["redo"]} if row else {"undo": [], "redo": []}


def _save_stacks(deck: str, undo: list, redo: list) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO action_stacks (user_id, deck, undo, redo) VALUES (%s,%s,%s,%s)
               ON CONFLICT (user_id, deck) DO UPDATE SET undo=EXCLUDED.undo, redo=EXCLUDED.redo""",
            (USER_ID, deck, json.dumps(undo), json.dumps(redo)))


MAX_STACK = 200          # bounded so the row cannot grow without limit


def push_action(deck: str, rec: dict) -> None:
    s = _stacks(deck)
    undo = (s["undo"] + [rec])[-MAX_STACK:]
    _save_stacks(deck, undo, [])          # a fresh action invalidates the redo chain


def pop_undo(deck: str) -> dict | None:
    s = _stacks(deck)
    if not s["undo"]:
        return None
    rec = s["undo"][-1]
    _save_stacks(deck, s["undo"][:-1], (s["redo"] + [rec])[-MAX_STACK:])
    return rec


def pop_redo(deck: str) -> dict | None:
    s = _stacks(deck)
    if not s["redo"]:
        return None
    rec = s["redo"][-1]
    _save_stacks(deck, (s["undo"] + [rec])[-MAX_STACK:], s["redo"][:-1])
    return rec


# ---------------------------------------------------------------- notes

def get_note(term: str) -> dict:
    with conn() as c:
        row = c.execute("SELECT md, updated FROM notes WHERE user_id=%s AND term=%s",
                        (USER_ID, term)).fetchone()
    if not row:
        return {"term": term, "md": "", "updated": ""}
    return {"term": term, "md": row["md"], "updated": str(row["updated"] or "")}


def set_note(term: str, md: str) -> None:
    """Emptying the box deletes the note, same as the local app."""
    with conn() as c:
        if md.strip():
            c.execute(
                """INSERT INTO notes (user_id, term, md, updated) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (user_id, term)
                   DO UPDATE SET md=EXCLUDED.md, updated=EXCLUDED.updated""",
                (USER_ID, term, md, date.today()))
        else:
            c.execute("DELETE FROM notes WHERE user_id=%s AND term=%s", (USER_ID, term))
