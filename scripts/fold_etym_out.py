#!/usr/bin/env python3
"""Fold Workflow agent out-files -> per-term etym cache -> deck (D3 fixer, docs/vocab-loop.md).

Each Workflow agent reformats one input batch and writes
    $LANG_PREP_CACHE/enrich_out/etym/<deck>/batch_XXXX.out.json
        = [{term, useful, breakdown, story, origin}, ...]
This step distributes those records into the per-term cache that enrich_etym.py reads
    $LANG_PREP_CACHE/enrich_etym/<deck>/<term>.json
then folds the useful ones into the deck by delegating to enrich_etym.py (apply-cache-only).

Subcommands:
  pending  <deck>  -> print JSON list of batch indices with NO out-file yet (for the workflow args)
  fold     <deck>  -> distribute out-files to cache, then run enrich_etym.py <deck> (cache-only)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK_FILES = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
              "gre": REPO / "gre" / "vocab" / "gre_vocab.json"}


def _dirs(deck: str):
    inp = CACHE / "enrich_batches" / "etym" / deck
    out = CACHE / "enrich_out" / "etym" / deck
    cache = CACHE / "enrich_etym" / deck
    return inp, out, cache


def cmd_pending(deck: str) -> None:
    inp, out, _ = _dirs(deck)
    batches = sorted(inp.glob("batch_*.json"))
    pending = [int(b.stem.split("_")[1]) for b in batches
               if not (out / f"{b.stem}.out.json").exists()]
    print(json.dumps(pending))


def cmd_fold(deck: str) -> None:
    inp, out, cache = _dirs(deck)
    cache.mkdir(parents=True, exist_ok=True)
    valid = {"term", "useful", "breakdown", "story", "origin"}
    written = skipped = 0
    for of in sorted(out.glob("batch_*.out.json")):
        try:
            recs = json.loads(of.read_text(encoding="utf-8"))
        except Exception as ex:
            print(f"  !! bad out-file {of.name}: {ex}")
            continue
        if isinstance(recs, dict):
            recs = recs.get("words") or recs.get("records") or []
        for r in recs:
            t = (r.get("term") or "").strip()
            if not t or "useful" not in r:
                skipped += 1
                continue
            rec = {k: r[k] for k in valid if k in r}
            (cache / f"{t}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            written += 1
    print(f"[{deck}] cache records written: {written}  (skipped malformed: {skipped})")

    # apply cache -> deck DIRECTLY (never invoke the LLM; .env keys would make
    # enrich_etym.py start a real enrichment run). useful:true -> set etymology; else clear.
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8"))
    applied = 0
    for e in words:
        cf = cache / f"{e['term']}.json"
        if not cf.exists():
            continue
        try:
            rec = json.loads(cf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if rec.get("useful"):
            et = {k: rec[k] for k in ("breakdown", "story", "origin") if rec.get(k)}
            if et:
                e["etymology"] = et
                applied += 1
        else:
            e.pop("etymology", None)
    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    have = sum(1 for w in words if w.get("etymology"))
    print(f"[{deck}] applied {applied} etymologies; deck now has {have} with etymology")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("pending", "fold"):
        print(__doc__)
        sys.exit(1)
    (cmd_pending if sys.argv[1] == "pending" else cmd_fold)(sys.argv[2])


if __name__ == "__main__":
    main()
