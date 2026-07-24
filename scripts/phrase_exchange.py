#!/usr/bin/env python3
"""Give verb entries in the scene deck their inflected forms (offline, no LLM).

Two sources, in order:
  1. single words   -> copy ECDICT's `exchange` from the toefl/gre decks, which already carry it
  2. verb phrases   -> conjugate the HEAD verb and keep the rest of the phrase
                       "drop out of school" + drop{p:dropped,i:dropping,3:drops}
                       -> dropped out of school / dropping out of school / drops out of school

ECDICT has no entry for a phrase, so before this the deck claimed 'verb' with no inflections at
all. The forms are real English, not a scoring workaround: they feed the study card and
add_syn_ant's self-exclusion (a synonym list must not just echo the headword's own forms).

Only inflection keys that describe a VERB are rewritten (p/d/i/3); comparative/plural keys are
meaningless for a verb phrase and are dropped.

Usage: .venv/bin/python scripts/phrase_exchange.py [--dry]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCENES = REPO / "toefl" / "vocab" / "scene_vocab.json"
SOURCES = (REPO / "toefl" / "vocab" / "toefl_vocab.json",
           REPO / "gre" / "vocab" / "gre_vocab.json")

VERB_KEYS = ("p", "d", "i", "3")      # past, past participle, -ing, 3rd person singular


def _is_verb(entry: dict) -> bool:
    return any((s.get("pos") or "") == "verb" for s in entry.get("senses") or [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    lex: dict[str, dict] = {}
    for p in SOURCES:
        for w in json.loads(p.read_text(encoding="utf-8")):
            if w.get("exchange"):
                lex.setdefault(w["term"].lower(), w["exchange"])

    words = json.loads(SCENES.read_text(encoding="utf-8"))
    copied = composed = 0
    samples = []
    for w in words:
        if w.get("exchange") or not _is_verb(w):
            continue
        term = w["term"]
        toks = term.split()

        if len(toks) == 1:
            ex = lex.get(term.lower())
            if ex:
                w["exchange"] = ex
                copied += 1
            continue

        head = toks[0].lower()
        ex = lex.get(head)
        if not ex:
            continue
        rest = " ".join(toks[1:])
        out = {}
        for k in VERB_KEYS:
            form = str(ex.get(k) or "").split("/")[0].split(",")[0].strip()
            if form:
                out[k] = f"{form} {rest}"
        if out:
            w["exchange"] = out
            composed += 1
            if len(samples) < 6:
                samples.append((term, out.get("p", ""), out.get("3", "")))

    print(f"[scenes] verb exchange: copied {copied} single words, composed {composed} phrases")
    for t, p, third in samples:
        print(f"    {t:30s} -> {p} | {third}")
    if args.dry:
        return
    SCENES.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
