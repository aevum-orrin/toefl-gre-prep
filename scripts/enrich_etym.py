#!/usr/bin/env python3
"""Add 词根词缀·词源 (roots/affixes + etymology) to a vocab deck via a FREE LLM.

Companion to enrich_vocab.py, same design: per-word cache on scratch
($LANG_PREP_CACHE/enrich_etym/<deck>/<term>.json), fully resumable, deck JSON
checkpointed every few batches. Only CLASSIC, genuinely-helpful analyses are kept:
the model may answer useful=false (cached too, so it is never re-asked) and the
word then simply shows no etymology block in the UI.

Deck field written:  entry["etymology"] = {breakdown, story, origin}
  breakdown: "sub-(在下/在后) + sequ(跟随, 同 sequence) + -ent(形容词后缀)"
  story:     "跟在一个序列后面 → 随后的、后来的"
  origin:    "来自拉丁语 subsequī; 同根词: sequence, consequence" / 舶来词标注

Usage:
  .venv/bin/python scripts/enrich_etym.py toefl --limit 500
  .venv/bin/python scripts/enrich_etym.py gre --provider groq --max-fails 8
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "prep-core" / "src"))

from prep_core import load_env, make_provider  # noqa: E402

CACHE = Path("/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
}

_SYSTEM = (
    "You are an etymology teacher for Chinese students preparing for TOEFL/GRE, teaching the "
    "词根词缀+词源 method. For each English word decide whether a roots/affixes/origin analysis "
    "GENUINELY helps a Chinese learner remember it (classic Latin/Greek roots, transparent "
    "prefix/suffix logic, or an interesting loanword story). If not, return useful=false.\n"
    "When useful, return (mixed Chinese-English, concise):\n"
    "  breakdown: the word split into morphemes, each glossed in Chinese, joined with ' + ', e.g. "
    "for subsequent: \"sub-(在下/在后) + sequ(跟随, 同 sequence 序列) + -ent(形容词后缀)\".\n"
    "  story: one short line deriving the meaning from the parts, e.g. \"跟在一个序列后面 → 随后的、"
    "后来的\".\n"
    "  origin: source language + cognates, e.g. \"来自拉丁语 subsequī; 同根词: sequence, consequence, "
    "pursue\". If the word is a loanword into English (舶来词, e.g. ballet, tsunami, kindergarten), "
    "say so here: \"舶来词: 来自法语 ballet\".\n"
    "Only give CORRECT, standard etymologies; if unsure, prefer useful=false over invention."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "words": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "useful": {"type": "boolean"},
                    "breakdown": {"type": "string"},
                    "story": {"type": "string"},
                    "origin": {"type": "string"},
                },
                "required": ["term", "useful"],
            },
        }
    },
    "required": ["words"],
}


def _apply(entry: dict, rec: dict) -> None:
    if not rec.get("useful"):
        entry.pop("etymology", None)
        return
    et = {k: rec[k] for k in ("breakdown", "story", "origin") if rec.get(k)}
    if et:
        entry["etymology"] = et


def enrich(deck: str, limit: int | None, batch: int, sleep: float,
           provider: str | None = None, max_fails: int = 0) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8"))
    cdir = CACHE / "enrich_etym" / deck
    cdir.mkdir(parents=True, exist_ok=True)

    todo = []
    for e in words:
        cf = cdir / f"{e['term']}.json"
        if cf.exists():
            try:
                _apply(e, json.loads(cf.read_text(encoding="utf-8")))
                continue
            except json.JSONDecodeError:
                pass
        todo.append(e)
    if limit is not None:
        todo = todo[:limit]

    prov = make_provider(provider)
    if prov is None:
        print("No LLM provider (set GEMINI_API_KEY / GROQ_API_KEY in .env). Merged cache only.")
        path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
        return
    print(f"[{deck}] {len(words)} words, {len(todo)} need etymology via {prov.name}/{prov.model}")

    done = fails = 0
    for bi in range(0, len(todo), batch):
        chunk = todo[bi:bi + batch]
        user = ("Analyze these words. Return JSON per the schema.\n"
                + json.dumps([e["term"] for e in chunk], ensure_ascii=False))
        try:
            out = prov.complete_json(_SYSTEM, user, _SCHEMA)
        except Exception as ex:
            fails += 1
            print(f"  batch {bi//batch}: FAILED ({type(ex).__name__}: {str(ex)[:80]})")
            if max_fails and fails >= max_fails:
                print(f"  stopping early after {fails} consecutive failures (quota reached?)")
                break
            time.sleep(sleep)
            continue
        fails = 0
        by_term = {w.get("term", "").lower(): w for w in out.get("words", [])}
        for e in chunk:
            rec = by_term.get(e["term"].lower())
            if not rec:
                continue
            (cdir / f"{e['term']}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            _apply(e, rec)
            done += 1
        if (bi // batch) % 20 == 0:
            path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  …{done}/{len(todo)} done (checkpoint written)")
        time.sleep(sleep)

    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    with_et = sum(1 for w in words if w.get("etymology"))
    print(f"[{deck}] done: {done} newly analyzed, {with_et}/{len(words)} have etymology")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--provider", default=None, help="gemini|groq|anthropic (default: auto, free-first)")
    ap.add_argument("--max-fails", type=int, default=0,
                    help="stop after this many consecutive batch failures (0 = never)")
    args = ap.parse_args()
    load_env(REPO / ".env")
    enrich(args.deck, args.limit, args.batch, args.sleep, args.provider, args.max_fails)


if __name__ == "__main__":
    main()
