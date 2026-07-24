#!/usr/bin/env python3
"""Enrich a vocab deck with a clean learner definition, one example sentence per
part of speech, and common collocations — using a FREE LLM (Gemini by default),
grounded on ECDICT's authoritative Chinese gloss so the model phrases known
meaning rather than inventing it.

Design (matches the user's "cache" idea): every word's enrichment is cached as
JSON under scratch/lang-prep-cache/enrich/<deck>/<term>.json. Identical input is
never re-sent to the LLM; a re-run resumes where it stopped. The merged deck JSON
in the repo is re-written as a checkpoint every few batches so partial progress
is usable immediately.

Usage:
  python scripts/enrich_vocab.py toefl            # enrich whole deck (resumable)
  python scripts/enrich_vocab.py gre --limit 200  # just the 200 most-frequent unseen
  python scripts/enrich_vocab.py toefl --batch 16 --sleep 0.5
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
    # topical TOEFL listening-scene vocab; ~27% are multi-word phrases, so kaikki/WordNet
    # coverage is naturally lower than the single-word decks
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}

_SYSTEM = (
    "You are an expert lexicographer building a TOEFL/GRE study deck. For each word you are given "
    "its Chinese gloss and its parts of speech. Return, per word:\n"
    "  gloss_en: ONE clear learner's-dictionary definition of the word's MOST COMMON meaning, in "
    "plain English (the kind Oxford/Merriam-Webster learner editions use).\n"
    "  senses: for EACH given part of speech, one natural example sentence at CEFR B2-C1 level that "
    "unambiguously shows that meaning, plus 2-3 common collocations or fixed phrases for it.\n"
    "Use exactly the part-of-speech labels provided. Keep sentences natural, exam-appropriate, and "
    "self-explanatory. Do not add parts of speech that were not requested."
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
                    "gloss_en": {"type": "string"},
                    "senses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pos": {"type": "string"},
                                "example": {"type": "string"},
                                "collocations": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["pos", "example", "collocations"],
                        },
                    },
                },
                "required": ["term", "gloss_en", "senses"],
            },
        }
    },
    "required": ["words"],
}


def _cache_dir(deck: str) -> Path:
    d = CACHE / "enrich" / deck
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pos_list(entry: dict) -> list[str]:
    seen: list[str] = []
    for s in entry.get("senses", []):
        p = (s.get("pos") or "").strip()
        if p and p not in seen:
            seen.append(p)
    return seen or ["general"]


def _zh(entry: dict) -> str:
    for s in entry.get("senses", []):
        if s.get("def_zh"):
            return "；".join(s["def_zh"][:3])
    return ""


def _apply(entry: dict, enr: dict) -> None:
    """Merge one cached enrichment record into a deck entry (in place)."""
    if enr.get("gloss_en"):
        entry["gloss_en"] = enr["gloss_en"]
    by_pos = {s.get("pos", "").strip().lower(): s for s in enr.get("senses", [])}
    for sense in entry.get("senses", []):
        hit = by_pos.get((sense.get("pos") or "").strip().lower()) \
            or (by_pos.get("general") if len(entry["senses"]) == 1 else None)
        if not hit:
            continue
        if hit.get("example"):
            sense["examples"] = [hit["example"]]
        if hit.get("collocations"):
            sense["collocations"] = hit["collocations"][:4]


def enrich(deck: str, limit: int | None, batch: int, sleep: float,
           provider: str | None = None, max_fails: int = 0) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8"))
    cdir = _cache_dir(deck)

    # apply everything already cached, and collect the still-missing (most-frequent first)
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
    print(f"[{deck}] {len(words)} words, {len(todo)} to enrich via {prov.name}/{prov.model}, batch={batch}")

    done = 0
    fails = 0
    for bi in range(0, len(todo), batch):
        chunk = todo[bi:bi + batch]
        payload = [{"term": e["term"], "zh": _zh(e), "pos": _pos_list(e)} for e in chunk]
        user = "Enrich these words. Return JSON per the schema.\n" + json.dumps(payload, ensure_ascii=False)
        try:
            out = prov.complete_json(_SYSTEM, user, _SCHEMA)
        except Exception as ex:  # transient overload / parse error -> skip, retry next run
            fails += 1
            print(f"  batch {bi//batch}: FAILED ({type(ex).__name__}: {str(ex)[:80]})")
            if max_fails and fails >= max_fails:  # daily quota likely reached -> stop cleanly
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
        if (bi // batch) % 20 == 0:  # checkpoint the merged deck periodically
            path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  …{done}/{len(todo)} enriched (checkpoint written)")
        time.sleep(sleep)

    path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{deck}] done: {done} newly enriched, deck written to {path.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECK_FILES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--provider", default=None,
                    help="gemini|groq|anthropic (default: auto, free-first). "
                         "Use groq to dodge Gemini's low free daily cap.")
    ap.add_argument("--max-fails", type=int, default=0,
                    help="stop after this many consecutive batch failures (0 = never). "
                         "Set >0 in scheduled runs so a hit daily quota exits cleanly instead of grinding.")
    args = ap.parse_args()
    load_env(REPO / ".env")
    enrich(args.deck, args.limit, args.batch, args.sleep, args.provider, args.max_fails)


if __name__ == "__main__":
    main()
