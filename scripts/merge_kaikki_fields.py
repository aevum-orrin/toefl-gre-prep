#!/usr/bin/env python3
"""Deterministic D1/D2 fill from the kaikki extract (docs/vocab-loop.md fixer, no LLM).

Fills ONLY EMPTY fields — never overwrites existing open-dict-data IPA or ECDICT glosses:
  D1 发音 : entry.ipa_us / entry.ipa_uk  <- kaikki ipa_us / ipa_uk
  D2 释义 : sense.def_en                 <- kaikki by_pos[pos].glosses[0]  (matched by pos)
            (falls back to any available pos gloss if the sense's exact pos is absent)

Reports how many holes were filled per field.  Idempotent.

Usage: .venv/bin/python scripts/merge_kaikki_fields.py toefl
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK_FILES = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
              "gre": REPO / "gre" / "vocab" / "gre_vocab.json"}

# map deck sense.pos values -> kaikki by_pos keys (kaikki uses full names)
POS_ALIAS = {
    "n": "noun", "noun": "noun",
    "v": "verb", "verb": "verb", "vt": "verb", "vi": "verb",
    "adj": "adj", "a": "adj", "adjective": "adj",
    "adv": "adv", "r": "adv", "adverb": "adv",
    "prep": "prep", "preposition": "prep",
    "conj": "conj", "conjunction": "conj",
    "pron": "pron", "pronoun": "pron",
    "int": "intj", "interj": "intj", "interjection": "intj",
    "num": "num", "numeral": "num", "det": "det", "determiner": "det",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    args = ap.parse_args()

    path = DECK_FILES[args.deck]
    deck = json.loads(path.read_text(encoding="utf-8"))
    kaikki = json.loads((CACHE / "kaikki" / f"{args.deck}_kaikki.json").read_text(encoding="utf-8"))

    fill_us = fill_uk = fill_def = 0
    for w in deck:
        k = kaikki.get(w["term"])
        if not k:
            continue
        if not w.get("ipa_us") and k.get("ipa_us"):
            w["ipa_us"] = k["ipa_us"]; fill_us += 1
        if not w.get("ipa_uk") and k.get("ipa_uk"):
            w["ipa_uk"] = k["ipa_uk"]; fill_uk += 1
        by_pos = k.get("by_pos") or {}
        # a flat pool of glosses for fallback when exact pos is missing
        any_glosses = [g for d in by_pos.values() for g in (d.get("glosses") or [])]
        for s in (w.get("senses") or []):
            if s.get("def_en"):
                continue
            kpos = POS_ALIAS.get((s.get("pos") or "").strip().lower())
            glosses = (by_pos.get(kpos) or {}).get("glosses") if kpos else None
            g = (glosses or any_glosses)
            if g:
                # deck convention: def_en is a list of gloss strings (keep up to 2)
                s["def_en"] = list(g[:2])
                fill_def += 1

    path.write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{args.deck}] filled  ipa_us +{fill_us}  ipa_uk +{fill_uk}  def_en +{fill_def}")


if __name__ == "__main__":
    main()
