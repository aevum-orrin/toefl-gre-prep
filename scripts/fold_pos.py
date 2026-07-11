#!/usr/bin/env python3
"""Merge the Opus part-of-speech pass back into a deck (see scripts/pos_workflow.js).

Each result row is {term, add?: [{pos, def_en, def_zh, example, collocations}],
                          fill?: [{pos, was, def_zh, example, collocations}]}
  add  -> a part of speech the deck was missing entirely (e.g. `elite` adjective) is appended
          as a new sense;
  fill -> an existing sense that had no example gets one (+ collocations, + a Chinese gloss if
          it had none). `was` says which sense it refers to: the pos string as the batch input
          showed it, so "?" targets the sense the deck could not tag, and the model's `pos`
          field carries the correct label to write back.

Senses stay ordered noun → verb → adjective → adverb → … so the card reads like a dictionary.

Usage:  source env.sh && python scripts/fold_pos.py toefl
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}
POS_ORDER = ["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun",
             "determiner", "numeral", "interjection", "abbreviation", "phrase"]


def main() -> None:
    deck = sys.argv[1] if len(sys.argv) > 1 else "toefl"
    src = CACHE / "pos_out" / deck
    rows: dict[str, dict] = {}
    bad = 0
    for f in sorted(src.glob("batch_*.json")):
        try:
            for r in json.loads(f.read_text(encoding="utf-8")):
                rows[r["term"]] = r
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            bad += 1
    words = json.loads(DECK_FILES[deck].read_text(encoding="utf-8"))

    added = filled = 0
    for w in words:
        r = rows.get(w["term"])
        if not r:
            continue
        senses = w.get("senses") or []
        by_pos = {s.get("pos"): s for s in senses}

        for a in r.get("fill") or []:
            was, pos = a.get("was", a.get("pos")), a.get("pos")
            tgt = by_pos.get(was) or by_pos.get(pos) or by_pos.get("")
            if tgt is None:
                continue
            if pos and not tgt.get("pos"):
                tgt["pos"] = pos                    # the "?" sense finally gets its label
            if a.get("def_en") and not tgt.get("def_en"):
                tgt["def_en"] = [a["def_en"]]
            if a.get("example") and not tgt.get("examples"):
                tgt["examples"] = [a["example"]]
            if a.get("collocations") and not tgt.get("collocations"):
                tgt["collocations"] = a["collocations"][:3]
            if a.get("def_zh") and not tgt.get("def_zh"):
                tgt["def_zh"] = [a["def_zh"]]
            filled += 1

        for a in r.get("add") or []:
            pos = a.get("pos")
            if not pos or pos in by_pos:            # never duplicate an existing POS
                continue
            s = {"pos": pos,
                 "def_en": [a["def_en"]] if a.get("def_en") else [],
                 "def_zh": [a["def_zh"]] if a.get("def_zh") else [],
                 "examples": [a["example"]] if a.get("example") else [],
                 "collocations": (a.get("collocations") or [])[:3]}
            senses.append(s)
            by_pos[pos] = s
            added += 1

        w["senses"] = sorted(senses,
                             key=lambda s: POS_ORDER.index(s["pos"]) if s.get("pos") in POS_ORDER
                             else 99)

    DECK_FILES[deck].write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    n_senses = sum(len(w.get("senses") or []) for w in words)
    no_ex = sum(1 for w in words for s in (w.get("senses") or [])
                if s.get("pos") and not s.get("examples"))
    print(f"[{deck}] {len(rows)} result rows ({bad} unreadable files) -> "
          f"{added} POS senses added, {filled} senses filled")
    print(f"        deck now {len(words)} words / {n_senses} senses; "
          f"named-POS senses still lacking an example: {no_ex}")


if __name__ == "__main__":
    main()
