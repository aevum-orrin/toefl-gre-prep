#!/usr/bin/env python3
"""Add English synonyms/antonyms to a vocab deck from WordNet (offline, no LLM).

Writes word-level `synonyms` / `antonyms` lists (single English words only, per the user's
"只要英文的单词就行"): each is a deduped, self-excluded list of WordNet lemmas that are a single
token (no spaces). Antonyms come from lemma.antonyms() across the word's synsets. Empty lists are
omitted to keep the deck slim. Idempotent; overwrites the two fields on each run.

WordNet data lives on scratch: $NLTK_DATA (default $LANG_PREP_CACHE/nltk_data). Install once:
  .venv/bin/pip install nltk
  NLTK_DATA=$LANG_PREP_CACHE/nltk_data .venv/bin/python -c "import nltk;nltk.download('wordnet',download_dir='$NLTK_DATA')"

Usage: NLTK_DATA=$LANG_PREP_CACHE/nltk_data .venv/bin/python scripts/add_syn_ant.py toefl [--dry]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
os.environ.setdefault("NLTK_DATA", str(CACHE / "nltk_data"))
DECK_FILES = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
              "gre": REPO / "gre" / "vocab" / "gre_vocab.json"}

MAX_SYN = 12
MAX_ANT = 10


def _inflections(entry: dict) -> set[str]:
    """The word's own forms (so a synonym list never just echoes the headword)."""
    forms = {entry["term"].lower()}
    exch = entry.get("exchange") or {}
    # ECDICT exchange is a dict {code: form(s)} e.g. {"s":"locomotives","p":"ran","3":"runs"}
    if isinstance(exch, dict):
        for v in exch.values():
            for form in str(v).replace(",", "/").split("/"):
                if form.strip():
                    forms.add(form.strip().lower())
    return {f for f in forms if f}


def relations(term: str, own: set[str], wn):
    syn: list[str] = []
    ant: list[str] = []
    seen_s, seen_a = set(), set()
    for s in wn.synsets(term):
        for lem in s.lemmas():
            name = lem.name()
            if "_" in name or " " in name:      # single words only ("单词")
                pass
            else:
                low = name.lower()
                if low not in own and low not in seen_s:
                    seen_s.add(low); syn.append(name)
            for a in lem.antonyms():
                an = a.name()
                if "_" in an or " " in an:
                    continue
                al = an.lower()
                if al not in own and al not in seen_a:
                    seen_a.add(al); ant.append(an)
    return syn[:MAX_SYN], ant[:MAX_ANT]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--dry", action="store_true", help="report coverage, do not write the deck")
    args = ap.parse_args()

    from nltk.corpus import wordnet as wn
    wn.ensure_loaded()

    path = DECK_FILES[args.deck]
    deck = json.loads(path.read_text(encoding="utf-8"))
    n = len(deck)
    got_syn = got_ant = wn_syn = wn_ant = 0
    for w in deck:
        own = _inflections(w)
        syn, ant = relations(w["term"], own, wn)
        if syn:
            wn_syn += 1
        if ant:
            wn_ant += 1
        if not args.dry:
            if syn:
                w["synonyms"] = syn
            else:
                w.pop("synonyms", None)
            if ant:
                w["antonyms"] = ant
            else:
                w.pop("antonyms", None)
        got_syn += 1 if syn else 0
        got_ant += 1 if ant else 0

    if not args.dry:
        path.write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{args.deck}] {n} words | WordNet gives synonyms for {wn_syn} ({100*wn_syn//n}%), "
          f"antonyms for {wn_ant} ({100*wn_ant//n}%)"
          + ("" if args.dry else "  -> written to deck"))


if __name__ == "__main__":
    main()
