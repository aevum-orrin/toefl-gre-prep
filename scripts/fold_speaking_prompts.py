#!/usr/bin/env python3
"""Fold the extracted REAL independent-speaking prompts into the speaking app's interview bank.

Inputs (written by the extract-mixed-real workflow on scratch):
  official-real/speaking/real_independent_prompts_a.json  (核桃 50/60题: prompt + full model answer)
  official-real/speaking/real_independent_prompts_b.json  (88 TPO + 27 dated-2018: prompt + outline)

Output: merged into official-real/speaking/interview.json as [{topic, questions[], answers[]}]
(the speaking app's _norm_topic reads parallel questions/answers arrays and tags source:"real").
Prompts are grouped by topic label, ~5 questions per topic entry so an interview session stays
one-sitting sized. Existing topics are preserved; duplicate questions are skipped.

Usage:  source env.sh && python scripts/fold_speaking_prompts.py
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("REAL_DATA_ROOT")
            or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/official-real")
SPK = ROOT / "speaking"
CHUNK = 5


def main() -> None:
    out_fp = SPK / "interview.json"
    topics = json.loads(out_fp.read_text(encoding="utf-8")) if out_fp.exists() else []
    seen = {q.strip().lower() for t in topics for q in t.get("questions", [])}

    by_topic: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name in ("real_independent_prompts_a.json", "real_independent_prompts_b.json"):
        fp = SPK / name
        if not fp.exists():
            print(f"  !! missing {name}")
            continue
        for it in json.loads(fp.read_text(encoding="utf-8")):
            q = (it.get("prompt") or "").strip()
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            label = (it.get("topic") or "General").strip() or "General"
            origin = (it.get("origin") or "").strip()
            ans = (it.get("model_answer") or "").strip()
            if origin:
                ans = f"[{origin}] {ans}" if ans else f"[{origin}]"
            by_topic[label].append((q, ans))

    added_topics = added_qs = 0
    for label, pairs in sorted(by_topic.items(), key=lambda kv: -len(kv[1])):
        for i in range(0, len(pairs), CHUNK):
            chunk = pairs[i:i + CHUNK]
            topics.append({
                "topic": f"真题·{label}" + (f" {i // CHUNK + 1}" if len(pairs) > CHUNK else ""),
                "questions": [q for q, _ in chunk],
                "answers": [a for _, a in chunk],
            })
            added_topics += 1
            added_qs += len(chunk)

    out_fp.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"interview.json: +{added_qs} real prompts in {added_topics} topics "
          f"(now {len(topics)} topics total)")


if __name__ == "__main__":
    main()
