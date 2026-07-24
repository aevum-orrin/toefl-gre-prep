#!/usr/bin/env python3
"""Fold the scene pos/def_en agent outputs into the deck (no LLM calls).

  .venv/bin/python scripts/fold_scene_out.py pending   # batch indices with no out-file yet
  .venv/bin/python scripts/fold_scene_out.py fold      # validate + apply to the deck

Only fills EMPTY fields, so re-running is safe and an agent can never overwrite a value that
was already correct.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK = REPO / "toefl" / "vocab" / "scene_vocab.json"
INDIR = CACHE / "enrich_batches" / "scenes"
OUTDIR = CACHE / "enrich_out" / "scenes"

VALID_POS = {"noun", "verb", "adjective", "adverb", "phrase",
             "preposition", "conjunction", "pronoun", "interjection"}


def pending() -> list[int]:
    total = len(list(INDIR.glob("batch_*.json")))
    done = {int(f.name.split("_")[1].split(".")[0]) for f in OUTDIR.glob("batch_*.out.json")}
    return [i for i in range(total) if i not in done]


def fold() -> None:
    words = json.loads(DECK.read_text(encoding="utf-8"))
    by_term = {w["term"]: w for w in words}

    recs, bad = [], 0
    for f in sorted(OUTDIR.glob("batch_*.out.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  !! bad out-file {f.name}: {str(e)[:60]}")
            bad += 1
            continue
        if isinstance(data, list):
            recs.extend(data)

    n_pos = n_def = skipped = 0
    for r in recs:
        if not isinstance(r, dict):
            continue
        w = by_term.get(r.get("term"))
        if not w:
            skipped += 1
            continue
        senses = w.get("senses") or []
        i = r.get("sense_index")
        if not isinstance(i, int) or not (0 <= i < len(senses)):
            skipped += 1
            continue
        s = senses[i]
        pos = (r.get("pos") or "").strip().lower()
        if pos in VALID_POS and not s.get("pos"):
            s["pos"] = pos
            n_pos += 1
        de = (r.get("def_en") or "").strip()
        if de and not s.get("def_en"):
            s["def_en"] = [de] if not isinstance(de, list) else de
            n_def += 1

    DECK.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[scenes] {len(recs)} records from {len(list(OUTDIR.glob('batch_*.out.json')))} files"
          f" (bad {bad}) -> pos +{n_pos}, def_en +{n_def}, skipped {skipped}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if cmd == "pending":
        print(json.dumps(pending()))
    elif cmd == "fold":
        fold()
    else:
        raise SystemExit("usage: fold_scene_out.py [pending|fold]")
