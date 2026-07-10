#!/usr/bin/env python3
"""Merge the generated Reading/Listening items (in scratch) with whatever already
lives in toefl/reading and toefl/listening, then write ONE canonical file per task
type and drop the old combined files. Idempotent and re-runnable.

Every item is validated (id, kind, questions -> q/options/answer in range); invalid
items are dropped with a warning. Item ids must be unique within a section.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = Path("/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/rl_gen")

# kind -> canonical filename (per section)
KIND_FILE = {
    "reading": {
        "academic_passage": "academic.json",
        "daily_life": "daily_life.json",
        "complete_words": "complete_words.json",
    },
    "listening": {
        "academic_talk": "academic_talk.json",
        "conversation": "conversation.json",
        "announcement": "announcement.json",
        "choose_response": "choose_response.json",
    },
}
# generated scratch file -> (section, expected kind)
GEN_FILES = {
    "reading_academic.json": ("reading", "academic_passage"),
    "reading_daily.json": ("reading", "daily_life"),
    "reading_complete.json": ("reading", "complete_words"),
    "listening_talk.json": ("listening", "academic_talk"),
    "listening_conversation.json": ("listening", "conversation"),
    "listening_announcement.json": ("listening", "announcement"),
    "listening_response.json": ("listening", "choose_response"),
}
CANONICAL = {s: set(KIND_FILE[s].values()) for s in KIND_FILE}


def _valid(it: dict) -> bool:
    if not isinstance(it, dict) or not it.get("id") or not it.get("kind"):
        return False
    qs = it.get("questions")
    if not isinstance(qs, list) or not qs:
        return False
    for q in qs:
        opts = q.get("options")
        if not q.get("q") or not isinstance(opts, list) or len(opts) < 2:
            return False
        if not isinstance(q.get("answer"), int) or not (0 <= q["answer"] < len(opts)):
            return False
    # reading needs a passage; listening needs a transcript
    if it["kind"] in KIND_FILE["reading"] and not it.get("passage"):
        return False
    if it["kind"] in KIND_FILE["listening"] and not it.get("transcript"):
        return False
    return True


def _read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError, OSError):
        return []


def merge_section(section: str) -> None:
    sdir = REPO / "toefl" / section
    by_kind: dict[str, dict[str, dict]] = {k: {} for k in KIND_FILE[section]}
    dropped = 0

    def ingest(items: list[dict]) -> None:
        nonlocal dropped
        for it in items:
            if not _valid(it):
                dropped += 1
                continue
            kind = it["kind"]
            if kind in by_kind:
                by_kind[kind].setdefault(it["id"], it)

    # 1) everything already in the section dir (old combined + any canonical files)
    for f in sorted(sdir.glob("*.json")):
        ingest(_read(f))
    # 2) freshly generated items from scratch
    for fname, (sec, _kind) in GEN_FILES.items():
        if sec == section:
            ingest(_read(GEN / fname))

    # global id-uniqueness across kinds within the section
    seen: set[str] = set()
    for kind, items in by_kind.items():
        for iid in list(items):
            if iid in seen:
                new = f"{iid}_{kind}"
                items[new] = items.pop(iid)
                iid = new
            seen.add(iid)

    # remove old non-canonical files (e.g. passages.json, talks.json)
    for f in sorted(sdir.glob("*.json")):
        if f.name not in CANONICAL[section]:
            f.unlink()

    total = 0
    for kind, fname in KIND_FILE[section].items():
        items = list(by_kind[kind].values())
        (sdir / fname).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        total += len(items)
        nq = sum(len(it["questions"]) for it in items)
        print(f"  {section}/{fname:22} {len(items):>3} items · {nq:>3} questions")
    print(f"  -> {section}: {total} items total" + (f"  ({dropped} invalid dropped)" if dropped else ""))


def main() -> None:
    for section in KIND_FILE:
        merge_section(section)


if __name__ == "__main__":
    main()
