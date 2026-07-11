#!/usr/bin/env python3
"""Build the "scenes" vocab deck from the Opus-parsed scene/topic word lists.

Inputs ($LANG_PREP_CACHE/rl_gen/scene_vocab/*.json, written by the parse-scene-vocab
workflow): arrays of {term, zh, topic, note} extracted from the user's uploaded real prep
material — listening conversation scenarios, lecture scenarios, academic subject vocab,
and the personal 词组句型 list.

Output: toefl/vocab/scene_vocab.json in the same schema vocab-srs renders. Terms that
exist in the main TOEFL deck borrow its phonetic/senses/gloss (and keep the topic badge);
unknown terms/phrases get a minimal entry from the parsed zh gloss. Dedup by term.

Usage:  source env.sh && python scripts/fold_scene_vocab.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
SRC = CACHE / "rl_gen" / "scene_vocab"
OUT = REPO / "toefl" / "vocab" / "scene_vocab.json"

# study order: conversation scenarios first (every test has them), then lecture/subject
FILES = ["listening_scenes.json", "lecture_scenes.json",
         "subject_scenes.json", "phrases_patterns.json"]


def main() -> None:
    main_deck = {w["term"].lower(): w
                 for w in json.loads((REPO / "toefl/vocab/toefl_vocab.json").read_text())}
    seen: set[str] = set()
    out: list[dict] = []
    for name in FILES:
        p = SRC / name
        if not p.exists():
            print(f"  !! missing {name}, skipped")
            continue
        for it in json.loads(p.read_text(encoding="utf-8")):
            term = (it.get("term") or "").strip()
            key = term.lower()
            if not term or key in seen:
                continue
            seen.add(key)
            zh, note, topic = it.get("zh") or "", it.get("note") or "", it.get("topic") or ""
            base = main_deck.get(key)
            if base:
                e = {k: base[k] for k in ("term", "phonetic", "senses", "collins", "oxford",
                                          "bnc", "frq", "tags", "exchange") if k in base}
                if base.get("gloss_en"):
                    e["gloss_en"] = base["gloss_en"]
                if base.get("tpo_hf"):
                    e["tpo_hf"] = True
            else:
                e = {"term": term, "phonetic": "",
                     "senses": [{"pos": "", "def_en": [], "def_zh": [zh] if zh else [],
                                 "examples": [note] if note else [], "collocations": []}],
                     "tags": ["scene"]}
            e["topic"] = topic
            e["tier"] = 1
            out.append(e)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    topics = Counter(e["topic"] for e in out)
    print(f"scenes deck: {len(out)} entries -> {OUT}")
    print("topics:", dict(topics.most_common(15)))


if __name__ == "__main__":
    main()
