#!/usr/bin/env python3
"""Merge US/UK IPA into the vocab decks from open-dict-data/ipa-dict.

Source files (downloaded once to scratch, see docs/STORAGE.md):
  $LANG_PREP_CACHE/ipa-dict/en_US.txt  (~126k words, Wiktionary-derived)
  $LANG_PREP_CACHE/ipa-dict/en_UK.txt  (~65k words)

Adds `ipa_us` / `ipa_uk` to every deck entry it can resolve (first variant when
the dict lists several). Missing words keep only the legacy ECDICT `phonetic`.
Idempotent — safe to re-run after decks grow.

Usage: .venv/bin/python scripts/add_ipa.py [toefl gre scenes]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
IPA_DIR = CACHE / "ipa-dict"

DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}


def _load_ipa(name: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in (IPA_DIR / name).read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        word, ipa = line.split("\t", 1)
        table[word.lower()] = ipa.split(",")[0].strip().strip("/")
    return table


def main() -> None:
    us, uk = _load_ipa("en_US.txt"), _load_ipa("en_UK.txt")
    for deck in (sys.argv[1:] or DECK_FILES):
        path = DECK_FILES[deck]
        if not path.exists():
            continue
        words = json.loads(path.read_text(encoding="utf-8"))
        hit_us = hit_uk = 0
        for w in words:
            key = w["term"].lower()
            if key in us:
                w["ipa_us"] = us[key]
                hit_us += 1
            if key in uk:
                w["ipa_uk"] = uk[key]
                hit_uk += 1
        path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
        n = len(words)
        print(f"[{deck}] {n} words: ipa_us {hit_us} ({hit_us/n:.0%}), ipa_uk {hit_uk} ({hit_uk/n:.0%})")


if __name__ == "__main__":
    main()
