"""Postgres access for the Vercel deployment of vocab-srs.

Everything the local app kept on disk or in process memory lives here instead, because Vercel
functions have no persistent disk and no shared memory between invocations:

  words         the deck content (was a 14 MB JSON parsed at startup)
  srs_cards     per-word schedule + the sticky-Again / Enter-confirmation flags (was srs/<deck>.json)
  notes         personal markdown notes (was notes/vocab_notes.json)
  intro_counts  how many new words were introduced on a given day (was <deck>.intro.json)
  action_stacks the undo/redo stacks (were in-process lists, so ←/→ broke across invocations)

`user_id` is a constant today (single user) but is part of every primary key, so turning this
into a multi-user app later needs no migration.
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

USER_ID = os.environ.get("PREP_USER_ID", "me")

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    deck  text NOT NULL,
    term  text NOT NULL,
    ord   int  NOT NULL,          -- index in the deck array: preserves the seeded study order
    tier  int,
    entry jsonb NOT NULL,         -- the whole word object (senses, ipa, etymology, syn/ant, …)
    PRIMARY KEY (deck, term)
);
CREATE INDEX IF NOT EXISTS words_deck_ord ON words (deck, ord);
CREATE INDEX IF NOT EXISTS words_term_lower ON words (deck, lower(term) text_pattern_ops);

CREATE TABLE IF NOT EXISTS srs_cards (
    user_id    text NOT NULL,
    deck       text NOT NULL,
    term       text NOT NULL,
    definition text  NOT NULL DEFAULT '',
    ease       real  NOT NULL DEFAULT 2.5,
    interval   int   NOT NULL DEFAULT 0,
    reps       int   NOT NULL DEFAULT 0,
    due        text  NOT NULL DEFAULT '',   -- ISO date; '' = never seen (matches Card.due)
    prof       real  NOT NULL DEFAULT 0.5,
    flags      jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (user_id, deck, term)
);
CREATE INDEX IF NOT EXISTS srs_due ON srs_cards (user_id, deck, due);

CREATE TABLE IF NOT EXISTS notes (
    user_id text NOT NULL,
    term    text NOT NULL,
    md      text NOT NULL DEFAULT '',
    updated date,
    PRIMARY KEY (user_id, term)
);

CREATE TABLE IF NOT EXISTS intro_counts (
    user_id text NOT NULL,
    deck    text NOT NULL,
    day     date NOT NULL,
    n       int  NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, deck, day)
);

CREATE TABLE IF NOT EXISTS action_stacks (
    user_id text  NOT NULL,
    deck    text  NOT NULL,
    undo    jsonb NOT NULL DEFAULT '[]'::jsonb,
    redo    jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (user_id, deck)
);
"""


def dsn() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see docs/DEPLOY-VERCEL.md)")
    return url


_CONN: psycopg.Connection | None = None
_LOCK = threading.Lock()


def _live(c: psycopg.Connection | None) -> bool:
    return c is not None and not c.closed


@contextmanager
def conn():
    """Reuse ONE connection per warm container.

    Opening a connection per call was costing a full TCP+TLS handshake to Neon *seven times*
    for a single /api/next — invisible on localhost, ~300 ms of dead time from a Vercel
    function. A serverless container handles requests one after another and is reused while
    warm, so a module-level connection amortises the handshake to zero on every request after
    the first. psycopg serialises concurrent use internally, and the lock keeps two threads
    from racing to reconnect.

    DATABASE_URL must point at the provider's POOLED endpoint (Neon's `-pooler` host,
    Supabase's transaction pooler on :6543) so idle containers don't hold real backends open.
    """
    global _CONN
    with _LOCK:
        if not _live(_CONN):
            _CONN = psycopg.connect(dsn(), row_factory=dict_row, autocommit=True)
        c = _CONN
    try:
        yield c
    except psycopg.OperationalError:
        # the container slept and the server dropped us: drop it so the next call reconnects
        with _LOCK:
            if _CONN is c:
                try:
                    c.close()
                finally:
                    _CONN = None
        raise


def init_schema() -> None:
    with conn() as c:
        c.execute(SCHEMA)
