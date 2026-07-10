#!/usr/bin/env python3
"""Re-order a vocab deck into a study-priority sequence and tag each word with a `tier`.

The learner wants three study tiers, in this order:
  Tier 1  高频词  — frequent, exam-relevant words that are worth studying FIRST
  Tier 2  刁钻词  — rarer / obscure / harder words, studied AFTER the high-frequency core
  Tier 3  简单词  — trivially common basics you almost certainly already know, studied LAST

Difficulty signals come straight from ECDICT (the standard approach: corpus frequency +
CEFR-style basic-word lists — Collins star rating and Oxford 3000). Higher Collins star and
Oxford-3000 membership mark basic words; a low frequency rank (BNC/COCA) marks common words.

  freq  = best (smallest) available frequency rank (frq preferred, else bnc; missing = very rare)
  tier3 (simple)   : Collins>=5, OR top-2000 by frequency, OR Oxford-3000 within the top 3000
  tier1 (high-freq): otherwise, frequency rank within the top ~14000  (frequent enough to prioritise)
  tier2 (rare)     : otherwise (rare / no frequency data)

Within every tier, words stay ordered most-frequent-first. Enrichment is preserved (this only
re-orders and adds a `tier` field). vocab-srs introduces new cards in exactly this file order.

Usage:  python scripts/order_vocab.py            # both decks
        python scripts/order_vocab.py toefl      # one deck
"""
from __future__ import annotations

import json
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
    # sort key: tier ascending (1 first, 3 last); within a tier, most-frequent first
    words.sort(key=lambda w: (w["tier"], _freq(w)))
    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    n1 = sum(1 for w in words if w["tier"] == 1)
    n2 = sum(1 for w in words if w["tier"] == 2)
    n3 = sum(1 for w in words if w["tier"] == 3)
    print(f"[{deck}] {len(words)} words re-ordered  ->  T1 high-freq {n1} · T2 rare {n2} · T3 simple {n3}")
    print(f"        first 8: {[w['term'] for w in words[:8]]}")
    print(f"        last  8: {[w['term'] for w in words[-8:]]}")


def main() -> None:
    decks = [sys.argv[1]] if len(sys.argv) > 1 else list(DECK_FILES)
    for d in decks:
        order_deck(d)


if __name__ == "__main__":
    main()
