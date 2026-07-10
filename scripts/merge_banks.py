#!/usr/bin/env python3
"""Merge generated writing/speaking prompt-bank additions (scratch/gen_banks) into
the repo banks. Idempotent: dedups by id (email/discussion), topic (interview), or
exact text (Listen-and-Repeat sentences). Malformed items are skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = Path("/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/gen_banks")


def _read(p: Path) -> list:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except (json.JSONDecodeError, ValueError, OSError):
        return []


def _write(p: Path, data: list) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def merge_keyed(repo_p: Path, gen_p: Path, key: str, required: list[str]) -> tuple[int, int]:
    base = _read(repo_p)
    seen = {it.get(key) for it in base if isinstance(it, dict)}
    added = 0
    for it in _read(gen_p):
        if not isinstance(it, dict) or not all(it.get(r) for r in required):
            continue
        if it.get(key) in seen:
            continue
        seen.add(it.get(key))
        base.append(it)
        added += 1
    _write(repo_p, base)
    return len(base), added


def merge_strings(repo_p: Path, gen_p: Path) -> tuple[int, int]:
    base = _read(repo_p)
    seen = {s.strip().lower() for s in base if isinstance(s, str)}
    added = 0
    for s in _read(gen_p):
        if not isinstance(s, str) or not s.strip() or s.strip().lower() in seen:
            continue
        seen.add(s.strip().lower())
        base.append(s.strip())
        added += 1
    _write(repo_p, base)
    return len(base), added


def main() -> None:
    total, added = merge_keyed(REPO / "toefl/writing/email_prompts.json",
                               GEN / "email_b.json", "id", ["situation", "prompt"])
    print(f"  email       +{added:3} -> {total}")
    total, added = merge_keyed(REPO / "toefl/writing/discussion_prompts.json",
                               GEN / "discussion_b.json", "id", ["professor", "posts"])
    print(f"  discussion  +{added:3} -> {total}")
    total, added = merge_keyed(REPO / "toefl/speaking/interview_questions.json",
                               GEN / "interview_b.json", "topic", ["topic", "questions"])
    print(f"  interview   +{added:3} -> {total}")
    total, added = merge_strings(REPO / "toefl/speaking/sentences.json",
                                 GEN / "sentences_b.json")
    print(f"  sentences   +{added:3} -> {total}")


if __name__ == "__main__":
    main()
