#!/usr/bin/env python3
"""One-shot (re-runnable) migration: local deck JSON + scratch study records -> Postgres.

Reads DATABASE_URL from the environment or from .env.vercel.local (gitignored).

  .venv/bin/python scripts/migrate_to_postgres.py            # everything
  .venv/bin/python scripts/migrate_to_postgres.py --decks-only
  .venv/bin/python scripts/migrate_to_postgres.py --progress-only

Everything upserts, so it is safe to re-run after studying more locally: deck content is
refreshed and study progress is overwritten with the newer local state. A card row is created
for EVERY word in the deck (defaults = never seen) so the counters in /api/decks are correct.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _load_dotenv() -> None:
    """DATABASE_URL is a credential; keep it in a gitignored file rather than the shell history."""
    f = REPO / ".env.vercel.local"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

from vocab_web.db import USER_ID, conn, init_schema  # noqa: E402

DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}
DATA = Path(os.environ.get("PREP_DATA_DIR") or REPO / "data")
CHUNK = 500


def _gloss(w: dict) -> str:
    senses = w.get("senses") or [{}]
    zh = senses[0].get("def_zh") or []
    en = senses[0].get("def_en") or []
    return (zh[0] if zh else (en[0] if en else "")) or ""


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def migrate_decks() -> None:
    for deck, path in DECK_FILES.items():
        if not path.exists():
            print(f"  [{deck}] SKIP (missing {path.name})")
            continue
        words = json.loads(path.read_text(encoding="utf-8"))
        rows = [(deck, w["term"], i, w.get("tier"), json.dumps(w, ensure_ascii=False))
                for i, w in enumerate(words)]
        with conn() as c:
            for batch in _chunks(rows, CHUNK):
                c.cursor().executemany(
                    """INSERT INTO words (deck, term, ord, tier, entry)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (deck, term) DO UPDATE SET
                         ord=EXCLUDED.ord, tier=EXCLUDED.tier, entry=EXCLUDED.entry""",
                    batch)
            # every word needs a card row so /api/decks counters are right
            for batch in _chunks([(USER_ID, deck, w["term"], _gloss(w)) for w in words], CHUNK):
                c.cursor().executemany(
                    """INSERT INTO srs_cards (user_id, deck, term, definition)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (user_id, deck, term) DO UPDATE SET
                         definition=EXCLUDED.definition""",
                    batch)
        print(f"  [{deck}] {len(words)} words -> words + srs_cards")


def migrate_progress() -> None:
    for deck in DECK_FILES:
        srs_path = DATA / "srs" / f"{deck}.json"
        if not srs_path.exists():
            print(f"  [{deck}] SKIP (no {srs_path.name})")
            continue
        cards = json.loads(srs_path.read_text(encoding="utf-8"))
        flags_path = DATA / "srs" / f"{deck}.flags.json"
        flags = json.loads(flags_path.read_text(encoding="utf-8")) if flags_path.exists() else {}
        rows = [(USER_ID, deck, c["term"], c.get("definition", ""), c.get("ease", 2.5),
                 c.get("interval", 0), c.get("reps", 0), c.get("due", ""), c.get("prof", 0.5),
                 json.dumps(flags.get(c["term"]) or {}))
                for c in cards]
        with conn() as c:
            for batch in _chunks(rows, CHUNK):
                c.cursor().executemany(
                    """INSERT INTO srs_cards (user_id, deck, term, definition, ease, interval,
                                              reps, due, prof, flags)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (user_id, deck, term) DO UPDATE SET
                         definition=EXCLUDED.definition, ease=EXCLUDED.ease,
                         interval=EXCLUDED.interval, reps=EXCLUDED.reps, due=EXCLUDED.due,
                         prof=EXCLUDED.prof, flags=EXCLUDED.flags""",
                    batch)
        seen = sum(1 for c in cards if c.get("due"))
        print(f"  [{deck}] {len(rows)} cards ({seen} already studied), {len(flags)} flagged")

        intro_path = DATA / "srs" / f"{deck}.intro.json"
        if intro_path.exists():
            intro = json.loads(intro_path.read_text(encoding="utf-8"))
            with conn() as c:
                c.cursor().executemany(
                    """INSERT INTO intro_counts (user_id, deck, day, n) VALUES (%s,%s,%s,%s)
                       ON CONFLICT (user_id, deck, day) DO UPDATE SET n=EXCLUDED.n""",
                    [(USER_ID, deck, date.fromisoformat(d), n) for d, n in intro.items()])
            print(f"  [{deck}] {len(intro)} intro-count days")


def migrate_notes() -> None:
    p = DATA / "notes" / "vocab_notes.json"
    if not p.exists():
        print("  (no vocab_notes.json)")
        return
    notes = json.loads(p.read_text(encoding="utf-8"))
    rows = []
    for term, rec in notes.items():
        md = rec.get("md", "") if isinstance(rec, dict) else str(rec)
        upd = (rec.get("updated") or None) if isinstance(rec, dict) else None
        rows.append((USER_ID, term, md, date.fromisoformat(upd) if upd else None))
    if rows:
        with conn() as c:
            c.cursor().executemany(
                """INSERT INTO notes (user_id, term, md, updated) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (user_id, term)
                   DO UPDATE SET md=EXCLUDED.md, updated=EXCLUDED.updated""",
                rows)
    print(f"  {len(rows)} notes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks-only", action="store_true")
    ap.add_argument("--progress-only", action="store_true")
    args = ap.parse_args()

    print("schema...")
    init_schema()
    if not args.progress_only:
        print("decks...")
        migrate_decks()
    if not args.decks_only:
        print("progress...")
        migrate_progress()
        print("notes...")
        migrate_notes()
    with conn() as c:
        for t in ("words", "srs_cards", "notes", "intro_counts"):
            n = c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]
            print(f"  {t:14s} {n:>7d} rows")
    print("done.")


if __name__ == "__main__":
    main()
