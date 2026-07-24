#!/usr/bin/env python3
"""Compose IPA for multi-word entries out of their constituent words (offline, no LLM).

The scene deck is ~27% phrases ("financial aid", "drop out of school"). Neither ipa-dict nor
kaikki lists phrases, so 408 of the 446 entries with no phonetic are phrases — a gap no
dictionary lookup can close. But every constituent word IS in ipa-dict, and a phrase's
pronunciation is just its words in sequence, so the transcription can be built rather than
looked up.

Deliberately conservative: a phrase is only written when EVERY constituent resolves. A partial
transcription would be worse than none — it would look authoritative while being wrong.

Usage: .venv/bin/python scripts/phrase_ipa.py scenes [--dry]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
IPA_DIR = CACHE / "ipa-dict"
DECK_FILES = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
              "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
              "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json"}

# "full-time/part-time student" and "e-mail" are single tokens for pronunciation purposes;
# split on whitespace and slashes, keep hyphenated compounds together for lookup first.
SPLIT = re.compile(r"[\s/]+")


def _load_ipa(name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    p = IPA_DIR / name
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        word, ipa = line.split("\t", 1)
        # a word can list several variants: "/ˈɛkənɑmɪks/, /ˌikəˈnɑmɪks/" — take the first
        first = ipa.split(",")[0].strip().strip("/")
        if first:
            out.setdefault(word.strip().lower(), first)
    return out


def _lookup(tok: str, table: dict[str, str]) -> str | None:
    tok = tok.strip().lower().strip(".,;:!?()")
    if not tok:
        return None
    if tok in table:
        return table[tok]
    if "-" in tok:                       # "full-time" -> full + time
        parts = [_lookup(p, table) for p in tok.split("-")]
        if all(parts):
            return " ".join(p for p in parts if p)
    return None


def compose(term: str, table: dict[str, str]) -> str | None:
    toks = [t for t in SPLIT.split(term) if t]
    if len(toks) < 2:                    # single words are ipa-dict's job, not ours
        return None
    out = []
    for t in toks:
        ipa = _lookup(t, table)
        if not ipa:
            return None                  # all-or-nothing: never emit a partial transcription
        out.append(ipa)
    return " ".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    us, uk = _load_ipa("en_US.txt"), _load_ipa("en_UK.txt")
    if not us:
        raise SystemExit(f"no ipa-dict data in {IPA_DIR}")
    path = DECK_FILES[args.deck]
    words = json.loads(path.read_text(encoding="utf-8"))

    n_us = n_uk = 0
    for w in words:
        if not w.get("ipa_us"):
            c = compose(w["term"], us)
            if c:
                w["ipa_us"] = c
                n_us += 1
        if not w.get("ipa_uk"):
            c = compose(w["term"], uk)
            if c:
                w["ipa_uk"] = c
                n_uk += 1
    phrases = sum(1 for w in words if len([t for t in SPLIT.split(w["term"]) if t]) > 1)
    print(f"[{args.deck}] {phrases} multi-word entries | composed ipa_us +{n_us}  ipa_uk +{n_uk}")
    if args.dry:
        for w in words:
            if w.get("ipa_us") and len([t for t in SPLIT.split(w['term']) if t]) > 1:
                print(f"    {w['term']:32s} /{w['ipa_us']}/")
        return
    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
