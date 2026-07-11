#!/usr/bin/env python3
"""Re-order a vocab deck into a study sequence and tag each word with a `tier`.

Difficulty signals come straight from ECDICT (corpus frequency + CEFR-style basic-word lists —
Collins star rating and Oxford 3000). Higher Collins star and Oxford-3000 membership mark basic
words; a low frequency rank (BNC/COCA) marks common words.

  freq  = best (smallest) available frequency rank (frq preferred, else bnc; missing = very rare)
  tier3 (simple)   : Collins>=5, OR top-2000 by frequency, OR Oxford-3000 within the top 3000
  tier1 (high-freq): otherwise, frequency rank within the top ~14000
  tier2 (rare)     : otherwise (rare / no frequency data)

STUDY ORDER (user's call, 2026-07-11): tier 1 and tier 2 are NOT studied in separate blocks —
grinding thousands of high-frequency words before ever meeting an obscure one is dull and
back-loads the hard material. They are SHUFFLED into one mixed block; only tier 3, the basics
you already know, is strictly last. TPO-attested words (`tpo_hf`) still come first inside the
mixed block — but frequent and rare ones are interleaved there too. The shuffle is seeded so
the order is stable across rebuilds (vocab-srs introduces new cards in file order; a reshuffle
would scramble the part of the deck you have not reached yet).

Usage:  python scripts/order_vocab.py            # both decks
        python scripts/order_vocab.py toefl      # one deck
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
}

HIGH_FREQ_CUT = 14000   # frequency rank below which a non-basic word is "high-frequency"
SIMPLE_FREQ_CUT = 2000  # top-N most-frequent words are treated as already-known basics


def _freq(w: dict) -> int:
    cands = [x for x in (w.get("frq") or 0, w.get("bnc") or 0) if x]
    return min(cands) if cands else 10 ** 9


def _tier(w: dict) -> int:
    collins = w.get("collins") or 0
    oxford = w.get("oxford") or 0
    f = _freq(w)
    if collins >= 5 or f <= SIMPLE_FREQ_CUT or (oxford == 1 and f <= 3000):
        return 3  # simple / known -> last
    if f <= HIGH_FREQ_CUT:
        return 1  # high-frequency -> first
    return 2      # rare / tricky -> middle


def order_deck(deck: str) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8"))
    for w in words:
        w["tier"] = _tier(w)
    # Study order (user's call): ONE big block of tier1+tier2 SHUFFLED together — a session
    # mixes frequent and obscure words instead of grinding 5000 easy-ish high-freq words
    # before ever meeting a hard one — and the tier-3 basics strictly LAST, since they are
    # words you almost certainly already know. Shuffle is seeded so the order is stable across
    # rebuilds (vocab-srs introduces new cards in file order; a reshuffle would scramble what
    # you have not reached yet). TPO-attested words keep a mild head start inside the block.
    main = [w for w in words if w["tier"] in (1, 2)]
    simple = [w for w in words if w["tier"] == 3]
    rng = random.Random(20260711)
    rng.shuffle(main)
    main.sort(key=lambda w: not w.get("tpo_hf"))     # stable: real-exam words first, still mixed
    simple.sort(key=_freq)
    words = main + simple
    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    n1 = sum(1 for w in words if w["tier"] == 1)
    n2 = sum(1 for w in words if w["tier"] == 2)
    n3 = sum(1 for w in words if w["tier"] == 3)
    hf = sum(1 for w in main if w.get("tpo_hf"))
    print(f"[{deck}] {len(words)} words re-ordered  ->  mixed block {len(main)} "
          f"(T1 {n1} + T2 {n2}; {hf} TPO-attested first) · simple T3 last {n3}")
    print(f"        first 8: {[w['term'] for w in words[:8]]}")
    print(f"        at #{len(main)}: {[w['term'] for w in words[len(main):len(main)+5]]} (simple block starts)")


def main() -> None:
    decks = [sys.argv[1]] if len(sys.argv) > 1 else list(DECK_FILES)
    for d in decks:
        order_deck(d)


if __name__ == "__main__":
    main()
