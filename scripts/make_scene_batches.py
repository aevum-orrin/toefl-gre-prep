#!/usr/bin/env python3
"""Batch the scene-deck senses that still lack `pos` or `def_en`.

The existing enrich pipeline cannot close this gap: its prompt takes the word's POS list as
INPUT and only produces example/collocations. Here the POS itself is missing, and 62% of the
cases are multi-word phrases ("drop out of school"), which no dictionary join covers.

Each batch item carries the Chinese gloss and an existing example, so the model is naming the
part of speech of a MEANING THAT IS ALREADY FIXED rather than inventing one.

Usage: .venv/bin/python scripts/make_scene_batches.py [--size 40]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK = REPO / "toefl" / "vocab" / "scene_vocab.json"
OUTDIR = CACHE / "enrich_batches" / "scenes"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=40)
    args = ap.parse_args()

    words = json.loads(DECK.read_text(encoding="utf-8"))
    todo = []
    for w in words:
        for i, s in enumerate(w.get("senses") or []):
            need_pos = not s.get("pos")
            need_def = not s.get("def_en")
            if not (need_pos or need_def):
                continue
            todo.append({
                "term": w["term"],
                "sense_index": i,
                "zh": (s.get("def_zh") or [""])[0],
                "example": (s.get("examples") or [""])[0],
                "have_pos": s.get("pos") or "",
                "need": [k for k, v in (("pos", need_pos), ("def_en", need_def)) if v],
            })

    if OUTDIR.exists():
        shutil.rmtree(OUTDIR)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in range(0, len(todo), args.size):
        (OUTDIR / f"batch_{i // args.size:04d}.json").write_text(
            json.dumps(todo[i:i + args.size], ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    phrases = sum(1 for t in todo if " " in t["term"])
    print(f"[scenes] {len(todo)} senses need work ({phrases} phrases) -> {n} batches in {OUTDIR}")


if __name__ == "__main__":
    main()
