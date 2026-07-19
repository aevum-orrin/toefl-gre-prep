#!/usr/bin/env python3
"""Prep batches for the D3 词源 fixer (docs/vocab-loop.md).

For every deck word that is NOT yet resolved (no `etymology` in the deck AND no cache
record in $LANG_PREP_CACHE/enrich_etym/<deck>/<term>.json), pull its authoritative
Wiktionary `etymology_text` (+ a couple glosses) from the pre-joined kaikki extract and
write priority-ordered batch files to scratch:
    $LANG_PREP_CACHE/enrich_batches/etym/<deck>/batch_XXXX.json
Each batch = [{term, etymology_text, gloss_en, glosses}].  A Workflow fan-out then has one
Opus agent reformat each batch's etymology_text into the Chinese-glossed
{breakdown, story, origin} and write per-term cache files (schema of enrich_etym.py).

Priority (study order): tpo_hf first, then tier1, tier2, tier3.  Words with no usable
etymology_text in kaikki are still emitted (the agent will mark useful=false), so the
loop can *resolve* them (cache useful:false) rather than leave them forever unscored.

Usage: .venv/bin/python scripts/make_etym_batches.py toefl [--batch 30] [--limit N]
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


def priority(w: dict) -> tuple:
    # tpo_hf first (study order), then tier asc (1 high-freq before 3 basics)
    return (0 if w.get("tpo_hf") else 1, w.get("tier") or 9)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--batch", type=int, default=30)
    ap.add_argument("--limit", type=int, default=None, help="cap total words emitted")
    args = ap.parse_args()

    deck = json.loads(DECK_FILES[args.deck].read_text(encoding="utf-8"))
    kaikki = json.loads((CACHE / "kaikki" / f"{args.deck}_kaikki.json").read_text(encoding="utf-8"))
    cdir = CACHE / "enrich_etym" / args.deck

    todo = []
    for w in deck:
        t = w["term"]
        if w.get("etymology"):
            continue
        if (cdir / f"{t}.json").exists():
            continue
        todo.append(w)
    todo.sort(key=priority)
    if args.limit:
        todo = todo[:args.limit]

    outdir = CACHE / "enrich_batches" / "etym" / args.deck
    # clear old batch files so a re-run reflects current cache state
    if outdir.exists():
        for f in outdir.glob("batch_*.json"):
            f.unlink()
    outdir.mkdir(parents=True, exist_ok=True)

    n_batches = 0
    have_et = 0
    for bi in range(0, len(todo), args.batch):
        chunk = todo[bi:bi + args.batch]
        rows = []
        for w in chunk:
            t = w["term"]
            k = kaikki.get(t) or {}
            et = (k.get("etymology_text") or "").strip()
            if et:
                have_et += 1
            glosses = []
            for pos, d in (k.get("by_pos") or {}).items():
                for g in (d.get("glosses") or [])[:2]:
                    glosses.append(f"({pos}) {g}")
            rows.append({"term": t, "etymology_text": et,
                         "gloss_en": w.get("gloss_en") or "",
                         "glosses": glosses[:4]})
        (outdir / f"batch_{n_batches:04d}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        n_batches += 1

    print(f"[{args.deck}] {len(todo)} uncovered words -> {n_batches} batches in {outdir}")
    print(f"  {have_et}/{len(todo)} have kaikki etymology_text; rest -> agent judges useful=false")


if __name__ == "__main__":
    main()
