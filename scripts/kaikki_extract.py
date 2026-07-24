#!/usr/bin/env python3
"""Join the kaikki.org English Wiktionary extract onto our decks — ONE pass over the 3.2 GB
JSONL, keeping only the words we actually have. Produces a compact per-deck file the vocab
loop can read cheaply instead of re-scanning 3 GB each iteration.

Source (downloaded to scratch, ~3.2 GB, English only, JSONL — one word-pos entry per line):
  $LANG_PREP_CACHE/kaikki/English.jsonl        (kaikki.org, wiktextract; no LLM quota)
Per line, the fields we use:
  word, lang_code(=="en"), pos, etymology_text,
  sounds[].ipa (+ .tags for US/UK), senses[].glosses, senses[].examples[].text

Output (scratch): $LANG_PREP_CACHE/kaikki/<deck>_kaikki.json — {term: {
  etymology_text, ipa_us, ipa_uk, by_pos:{pos:{glosses:[...], examples:[...]}}}}
This feeds:
  D3 词源  — etymology_text is the authoritative FACT; the loop reformats it into the
             Chinese-glossed {breakdown,story,origin} the UI wants (model's job).
  D1 发音  — ipa_us/ipa_uk for the ~4%/7% tail add_ipa.py couldn't cover.
  D2 释义  — glosses = English learner definitions for senses that only had a Chinese gloss.

Usage:  .venv/bin/python scripts/kaikki_extract.py            # both decks, one pass
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
SRC = CACHE / "kaikki" / "English.jsonl"
DECKS = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
         "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
         "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json"}

US_TAGS = {"US", "GA", "General-American", "GenAm", "American"}
UK_TAGS = {"UK", "RP", "Received-Pronunciation", "British", "England"}


def _pick_ipa(sounds: list) -> tuple[str | None, str | None]:
    us = uk = any_ = None
    for s in sounds or []:
        ipa = (s.get("ipa") or "").strip().strip("/").strip("[]")
        if not ipa:
            continue
        tags = set(s.get("tags") or [])
        if not any_:
            any_ = ipa
        if tags & US_TAGS and not us:
            us = ipa
        if tags & UK_TAGS and not uk:
            uk = ipa
    return us or any_, uk or any_          # fall back to the untagged first pronunciation


def extract() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} — download it first (see docs/vocab-loop.md)")
    want: dict[str, set[str]] = {}
    for deck, path in DECKS.items():
        terms = {w["term"].lower() for w in json.loads(path.read_text(encoding="utf-8"))}
        want[deck] = terms
    all_terms = set().union(*want.values())
    out: dict[str, dict] = {t: {} for t in all_terms}

    lines = kept = 0
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            lines += 1
            # cheap pre-filter before the JSON parse (3.2 GB — parsing every line is the cost)
            if '"lang_code": "en"' not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            w = (d.get("word") or "").lower()
            if w not in out:
                continue
            rec = out[w]
            kept += 1
            if d.get("etymology_text") and len(d["etymology_text"]) > len(rec.get("etymology_text", "")):
                rec["etymology_text"] = d["etymology_text"]
            us, uk = _pick_ipa(d.get("sounds"))
            if us and not rec.get("ipa_us"):
                rec["ipa_us"] = us
            if uk and not rec.get("ipa_uk"):
                rec["ipa_uk"] = uk
            pos = d.get("pos") or "?"
            bp = rec.setdefault("by_pos", {}).setdefault(pos, {"glosses": [], "examples": []})
            for se in d.get("senses") or []:
                for g in se.get("glosses") or []:
                    if g and g not in bp["glosses"]:
                        bp["glosses"].append(g)
                for ex in se.get("examples") or []:
                    t = ex.get("text")
                    if t and t not in bp["examples"]:
                        bp["examples"].append(t)
            if lines % 2_000_000 == 0:
                print(f"  scanned {lines//1_000_000}M lines, kept {kept} entries…")

    for deck, terms in want.items():
        deck_out = {t: out[t] for t in terms if out.get(t)}
        dst = CACHE / "kaikki" / f"{deck}_kaikki.json"
        dst.write_text(json.dumps(deck_out, ensure_ascii=False), encoding="utf-8")
        n = len(terms)
        cov = sum(1 for t in terms if out.get(t))
        et = sum(1 for t in terms if out.get(t, {}).get("etymology_text"))
        ipa = sum(1 for t in terms if out.get(t, {}).get("ipa_us") or out.get(t, {}).get("ipa_uk"))
        gl = sum(1 for t in terms if out.get(t, {}).get("by_pos"))
        print(f"[{deck}] {cov}/{n} matched · etymology {et} · ipa {ipa} · glosses {gl}  -> {dst.name}")


if __name__ == "__main__":
    extract()
