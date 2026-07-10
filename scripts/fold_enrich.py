#!/usr/bin/env python3
"""Fold subagent enrichment outputs back into the deck.

Subagents write one file per batch to $LANG_PREP_CACHE/enrich_out/<deck>/batch_NNN.json,
each a JSON list of records {term, gloss_en, senses:[{pos, example, collocations[]}]}. This
distributes them to the per-word cache ($LANG_PREP_CACHE/enrich/<deck>/<term>.json) that
enrich_vocab.py reads, then merges the whole cache into the deck (no LLM calls).

Usage:  python scripts/fold_enrich.py toefl
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")


def main() -> None:
    deck = sys.argv[1] if len(sys.argv) > 1 else "toefl"
    outdir = CACHE / "enrich_out" / deck
    cdir = CACHE / "enrich" / deck
    cdir.mkdir(parents=True, exist_ok=True)

    cached = bad = 0
    for f in sorted(outdir.glob("batch_*.json")):
        try:
            recs = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            bad += 1
            continue
        if not isinstance(recs, list):
            bad += 1
            continue
        for r in recs:
            if not isinstance(r, dict) or not r.get("term") or not r.get("gloss_en"):
                continue
            senses = [s for s in r.get("senses", [])
                      if isinstance(s, dict) and s.get("pos") and s.get("example")]
            rec = {"term": r["term"], "gloss_en": r["gloss_en"].strip(), "senses": senses}
            (cdir / f"{r['term']}.json").write_text(json.dumps(rec, ensure_ascii=False),
                                                    encoding="utf-8")
            cached += 1
    print(f"[{deck}] wrote {cached} cache records ({bad} unreadable batch files)")
    print(f"  now run:  python scripts/enrich_vocab.py {deck} --limit 0   # merge cache -> deck")


if __name__ == "__main__":
    main()
