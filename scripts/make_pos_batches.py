#!/usr/bin/env python3
"""Build the Opus batch inputs for the part-of-speech expansion pass.

Two jobs per word, in one sweep (see scripts/pos_workflow.js):
  ADD  — parts of speech a learner's dictionary lists but our ECDICT-derived deck lacks
         (e.g. `elite` had only the noun; the adjective in "elite athletes" was missing);
  FILL — POS senses that exist but carry no example/collocations, i.e. the ones
         scripts/fix_pos.py recovered from WordNet-style lines, plus words with no POS at all.

Each batch line: {term, have: [{pos, en, zh}], fill: [pos, …]}  — compact on purpose, the
bulk of the tokens should be the model's output, not ours.

Usage:  source env.sh && python scripts/make_pos_batches.py toefl [--size 200]
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
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--size", type=int, default=200)
    args = ap.parse_args()

    words = json.loads(DECK_FILES[args.deck].read_text(encoding="utf-8"))
    rows = []
    for w in words:
        have, fill = [], []
        for s in w.get("senses") or []:
            pos = s.get("pos") or ""
            entry = {"pos": pos or "?",
                     "en": (s.get("def_en") or [""])[0][:90],
                     "zh": (s.get("def_zh") or [""])[0][:40]}
            have.append(entry)
            if not s.get("examples"):
                fill.append(pos or "?")
        rows.append({"term": w["term"], "have": have, **({"fill": fill} if fill else {})})

    out = CACHE / "pos_batches" / args.deck
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("batch_*.json"):
        old.unlink()
    n = 0
    for i in range(0, len(rows), args.size):
        (out / f"batch_{i // args.size:03d}.json").write_text(
            json.dumps(rows[i:i + args.size], ensure_ascii=False), encoding="utf-8")
        n += 1
    need_fill = sum(1 for r in rows if r.get("fill"))
    print(f"[{args.deck}] {len(rows)} words -> {n} batches of {args.size} in {out}")
    print(f"          {need_fill} words have a POS sense still missing an example")


if __name__ == "__main__":
    main()
