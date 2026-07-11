#!/usr/bin/env python3
"""Recover the part of speech of senses that ended up in the UI's "—" (unknown POS) row.

ECDICT mixes two definition styles and build_vocab.py only understood one:
  "n. 领土, 领地"        Chinese-dictionary style — POS token ends with a period  ✔ parsed
  "v be composed of"    WordNet style — bare POS token, NO period                 ✘ missed
Everything in the second style fell into a pos:"" sense, so the card showed a "—" row whose
text still carried the stray tag ("v be composed of"). Half the TOEFL deck had one.

This script rewrites the decks in place:
  * bare WordNet tags (n/v/adj/s/adv/r/…) are recognised, stripped, and their definition is
    merged into the matching POS sense — CREATING that sense if the word lacked the POS
    (this alone recovers ~1150 real POS senses, mostly verbs);
  * leftover Chinese-only lines (continuation glosses with no tag) are appended to the word's
    primary sense instead of floating in their own row;
  * emptied pos:"" senses are dropped, so no "—" rows remain.

Senses created here start with no example/collocations — scripts/make_pos_batches.py collects
them for the Opus enrichment pass.

Usage:  source env.sh && python scripts/fix_pos.py [toefl|gre|scenes]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}

# WordNet-style bare tags (same mapping build_vocab.py uses for the dotted form)
BARE_POS = {"n": "noun", "v": "verb", "vt": "verb", "vi": "verb",
            "adj": "adjective", "a": "adjective", "s": "adjective", "j": "adjective",
            "adv": "adverb", "r": "adverb"}
BARE = re.compile(r"^([a-z]{1,4})\s+(?=[a-z(])")
POS_ORDER = ["noun", "verb", "adjective", "adverb", "auxiliary", "pronoun", "preposition",
             "conjunction", "article", "determiner", "numeral", "interjection", "abbreviation"]


def fix_word(w: dict) -> tuple[int, int]:
    """Returns (recovered_defs, created_senses)."""
    senses = w.get("senses") or []
    by_pos = {s["pos"]: s for s in senses if s.get("pos")}
    orphan_zh: list[str] = []
    recovered = created = 0

    for s in [x for x in senses if not x.get("pos")]:
        for line in s.get("def_en", []):
            m = BARE.match(line)
            pos = BARE_POS.get(m.group(1)) if m else None
            if not pos:
                continue                       # unlabelled English line: rare, dropped below
            text = line[m.end():].strip()
            tgt = by_pos.get(pos)
            if tgt is None:
                tgt = {"pos": pos, "def_en": [], "def_zh": [], "examples": [], "collocations": []}
                by_pos[pos] = tgt
                created += 1
            if text and text not in tgt["def_en"]:
                tgt["def_en"].append(text)
            recovered += 1
        orphan_zh += [z for z in s.get("def_zh", []) if z]

    if not by_pos:                             # nothing recoverable: keep the word as-is
        return 0, 0

    ordered = sorted(by_pos.values(),
                     key=lambda s: POS_ORDER.index(s["pos"]) if s["pos"] in POS_ORDER else 99)
    primary = ordered[0]
    for z in orphan_zh:                        # continuation glosses belong to the main sense
        if z not in primary["def_zh"]:
            primary["def_zh"].append(z)
    w["senses"] = ordered
    return recovered, created


def main() -> None:
    decks = sys.argv[1:] or ["toefl", "gre", "scenes"]
    for deck in decks:
        path = DECK_FILES[deck]
        words = json.loads(path.read_text(encoding="utf-8"))
        before_senses = sum(len(w.get("senses") or []) for w in words)
        before_empty = sum(1 for w in words for s in (w.get("senses") or []) if not s.get("pos"))
        rec = cre = touched = 0
        for w in words:
            if any(not s.get("pos") for s in (w.get("senses") or [])):
                r, c = fix_word(w)
                rec += r
                cre += c
                touched += 1
        after_empty = sum(1 for w in words for s in (w.get("senses") or []) if not s.get("pos"))
        need_ex = sum(1 for w in words for s in (w.get("senses") or [])
                      if s.get("pos") and not s.get("examples"))
        path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{deck}] {touched} words fixed | {rec} defs re-tagged | {cre} POS senses created | "
              f'"—" rows {before_empty} -> {after_empty} | senses '
              f"{before_senses} -> {sum(len(w.get('senses') or []) for w in words)} | "
              f"senses now needing an example: {need_ex}")


if __name__ == "__main__":
    main()
