#!/usr/bin/env python3
"""Prepare enrichment batches for Opus subagents (NOT a paid-API call — the subagents run on
the Claude Code subscription). Selects the words that still need enrichment, most-important
first, and writes small input batches the subagents read.

Selection: tiers 1 (high-freq) + 2 (rare/tricky) by default — everything except the trivially
simple tier 3 — skipping words already enriched (a per-word cache file exists, or the deck
entry already has gloss_en). Most-frequent first, so early batches are the highest-value words.

Output: $LANG_PREP_CACHE/enrich_batches/<deck>/batch_000.json ... each a JSON list of
  {term, zh, def_en, pos:[...]}  — the grounding a subagent needs to write a faithful entry.

Usage:  python scripts/make_enrich_batches.py toefl --tiers 1,2 --size 100
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
}


def _freq(w: dict) -> int:
    cands = [x for x in (w.get("frq") or 0, w.get("bnc") or 0) if x]
    return min(cands) if cands else 10 ** 9


def _zh(entry: dict) -> str:
    for s in entry.get("senses", []):
        if s.get("def_zh"):
            return "；".join(s["def_zh"][:3])
    return ""


def _def_en(entry: dict) -> str:
    for s in entry.get("senses", []):
        if s.get("def_en"):
            return s["def_en"][0]
    return ""


def _pos_list(entry: dict) -> list[str]:
    seen: list[str] = []
    for s in entry.get("senses", []):
        p = (s.get("pos") or "").strip()
        if p and p not in seen:
            seen.append(p)
    return seen or ["general"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--tiers", default="1,2", help="comma-separated tiers to include (default 1,2)")
    ap.add_argument("--size", type=int, default=100, help="words per batch")
    args = ap.parse_args()
    tiers = {int(t) for t in args.tiers.split(",")}

    words = json.loads(DECK_FILES[args.deck].read_text(encoding="utf-8"))
    cdir = CACHE / "enrich" / args.deck
    todo = [w for w in words
            if w.get("tier") in tiers
            and not w.get("gloss_en")
            and not (cdir / f"{w['term']}.json").exists()]
    todo.sort(key=_freq)  # most-frequent (most valuable) first

    outdir = CACHE / "enrich_batches" / args.deck
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("batch_*.json"):
        f.unlink()  # fresh run

    n = 0
    for i in range(0, len(todo), args.size):
        chunk = todo[i:i + args.size]
        payload = [{"term": e["term"], "zh": _zh(e), "def_en": _def_en(e), "pos": _pos_list(e)}
                   for e in chunk]
        (outdir / f"batch_{n:03d}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1

    already = sum(1 for w in words if w.get("tier") in tiers and (w.get("gloss_en") or (cdir / f"{w['term']}.json").exists()))
    intier = sum(1 for w in words if w.get("tier") in tiers)
    print(f"[{args.deck}] tiers {sorted(tiers)}: {intier} words, {already} already enriched, "
          f"{len(todo)} to do -> {n} batches of {args.size} in {outdir}")


if __name__ == "__main__":
    main()
