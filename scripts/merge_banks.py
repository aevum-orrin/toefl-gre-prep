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


def merge_essays(repo_p: Path, gen_names: list[str]) -> tuple[int, int]:
    """Attach a pre-written `model_essay` to each prompt item by id."""
    items = _read(repo_p)
    essays: dict[str, str] = {}
    for name in gen_names:
        d = _read(GEN / name)
        if isinstance(d, dict):
            essays.update(d)
        elif not d:  # _read returns [] for a JSON object; re-read as dict
            try:
                obj = json.loads((GEN / name).read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    essays.update(obj)
            except (json.JSONDecodeError, ValueError, OSError):
                pass
    n = 0
    for it in items:
        e = essays.get(it.get("id"))
        if isinstance(e, str) and e.strip():
            it["model_essay"] = e.strip()
            n += 1
    _write(repo_p, items)
    return len(items), n


def merge_sims(repo_p: Path, gen_names: list[str]) -> tuple[int, int]:
    """Attach 3 pre-written similar prompts (each with its own model essay) per base prompt."""
    items = _read(repo_p)
    sims: dict = {}
    for name in gen_names:
        try:
            obj = json.loads((GEN / name).read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                sims.update(obj)
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    n = 0
    for it in items:
        arr = sims.get(it.get("id"))
        if not isinstance(arr, list):
            continue
        built = [
            {"id": f"{it['id']}-s{i + 1}", "text": (o.get("text") or "").strip(),
             "model_essay": (o.get("model_essay") or "").strip()}
            for i, o in enumerate(arr[:3])
            if isinstance(o, dict) and (o.get("text") or "").strip()
        ]
        if built:
            it["similar"] = built
            n += 1
    _write(repo_p, items)
    return len(items), n


def merge_answers(repo_p: Path, gen_names: list[str]) -> tuple[int, int]:
    """Attach pre-written model answers (one per interview question) by topic name."""
    items = _read(repo_p)
    ans: dict = {}
    for name in gen_names:
        try:
            obj = json.loads((GEN / name).read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                ans.update(obj)
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    n = 0
    for it in items:
        a = ans.get(it.get("topic"))
        if isinstance(a, list) and a:
            it["answers"] = [x.strip() for x in a[:len(it.get("questions", []))]
                             if isinstance(x, str) and x.strip()]
            if it["answers"]:
                n += 1
    _write(repo_p, items)
    return len(items), n


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

    total, added = merge_essays(REPO / "toefl/writing/email_prompts.json",
                                ["email_essays_a.json", "email_essays_b.json"])
    print(f"  email model essays:      {added}/{total}")
    total, added = merge_essays(REPO / "toefl/writing/discussion_prompts.json",
                                ["discussion_essays_a.json", "discussion_essays_b.json"])
    print(f"  discussion model essays: {added}/{total}")

    total, added = merge_sims(REPO / "toefl/writing/email_prompts.json",
                              ["email_sim_a.json", "email_sim_b.json", "email_sim_c.json", "email_sim_d.json"])
    print(f"  email similar sets:      {added}/{total}")
    total, added = merge_sims(REPO / "toefl/writing/discussion_prompts.json",
                              ["disc_sim_a.json", "disc_sim_b.json", "disc_sim_c.json", "disc_sim_d.json"])
    print(f"  discussion similar sets: {added}/{total}")

    total, added = merge_answers(REPO / "toefl/speaking/interview_questions.json",
                                 ["interview_ans_a.json", "interview_ans_b.json",
                                  "interview_ans_c.json", "interview_ans_d.json"])
    print(f"  interview model answers: {added}/{total}")


if __name__ == "__main__":
    main()
