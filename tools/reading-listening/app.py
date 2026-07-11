"""reading-listening: local web tool for TOEFL 2026 Reading & Listening practice.

Both sections are auto-scored multiple choice, so this tool needs NO LLM and NO paid API — it's
100% free. Listening plays the transcript aloud with the browser's Web Speech API (free) and never
shows the text, so it stays a real listening test. Correct answers/explanations live server-side and
are only revealed after you submit.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8004
Open http://localhost:8004
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import ProgressStore

HERE = Path(__file__).parent
REPO = HERE.parents[1]
DATA_DIR = Path(os.environ.get("PREP_DATA_DIR") or REPO / "data")   # user records -> scratch (env.sh)

# One directory per section; every *.json inside is a task-type bank file (academic.json,
# daily_life.json, complete_words.json / academic_talk.json, conversation.json, …). Drop a new
# file in and it is picked up on restart.
SECTION_DIRS = {
    "reading": Path(os.environ.get("READING_DIR") or REPO / "toefl" / "reading"),
    "listening": Path(os.environ.get("LISTENING_DIR") or REPO / "toefl" / "listening"),
}
# Real ETS/TPO items live on SCRATCH (not home/not git) — dozens of TPO sets + listening
# audio would blow the home-folder budget, so heavy real data stays on scratch. They're
# served alongside the AI-practice bank; real items load FIRST so they surface early; each
# item carries a `source` ("real" 真题 | "ai" AI 练习题) that the UI badges.
REAL_ROOT = Path(os.environ.get("REAL_DATA_ROOT")
                 or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/official-real")
REAL_DIRS = {
    "reading": REAL_ROOT / "reading",
    "listening": REAL_ROOT / "listening",
}


def _load(section: str) -> list[dict]:
    items: list[dict] = []
    for base in (REAL_DIRS[section], SECTION_DIRS[section]):   # real first, then AI
        if not base.exists():
            continue
        for f in sorted(base.glob("*.json")):
            try:
                loaded = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(loaded, dict):        # a single-item file (e.g. one TPO passage)
                loaded = [loaded]
            for it in loaded:
                it.setdefault("source", "ai")
                # keep only single-answer MC the UI can score: >=2 options AND an int answer
                # (drops degenerate fill-in items and real "Select TWO" questions whose
                # answer is a list — the grader compares one chosen index)
                it["questions"] = [q for q in it.get("questions", [])
                                   if isinstance(q.get("options"), list) and len(q["options"]) >= 2
                                   and isinstance(q.get("answer"), int)]
            items += [it for it in loaded if it.get("questions")]
    return items


ITEMS: dict[str, list[dict]] = {s: _load(s) for s in SECTION_DIRS}
BY_ID: dict[str, dict[str, dict]] = {s: {it["id"]: it for it in items} for s, items in ITEMS.items()}

progress = ProgressStore(DATA_DIR / "progress.jsonl")
app = FastAPI(title="TOEFL Reading & Listening")


class Answers(BaseModel):
    section: str
    id: str
    answers: list[int]                       # chosen option index per question (-1 = unanswered)


def _public_item(section: str, it: dict) -> dict:
    """Strip answers/explanations before sending to the browser."""
    qs = [{"q": q["q"], "options": q["options"]} for q in it["questions"]]
    out = {"id": it["id"], "kind": it.get("kind", ""), "title": it.get("title", ""),
           "source": it.get("source", "ai"), "questions": qs}
    if section == "reading":
        out["passage"] = it["passage"]       # reading text is meant to be read
    else:
        out["transcript"] = it["transcript"]  # for TTS only; the frontend never displays it
    return out


@app.get("/api/status")
def status():
    return {s: len(ITEMS[s]) for s in SECTION_DIRS}


@app.get("/api/item")
def item(section: str, i: int = 0):
    items = ITEMS.get(section)
    if not items:
        return {"error": f"no items for section '{section}' (bank not generated yet)"}
    i %= len(items)
    return {"i": i, "total": len(items), "section": section, **_public_item(section, items[i])}


@app.post("/api/check")
def check(a: Answers):
    it = BY_ID.get(a.section, {}).get(a.id)
    if it is None:
        return {"error": "unknown item"}
    qs = it["questions"]
    results, correct = [], 0
    for idx, q in enumerate(qs):
        chosen = a.answers[idx] if idx < len(a.answers) else -1
        ok = chosen == q["answer"]
        correct += ok
        results.append({"chosen": chosen, "answer": q["answer"], "correct": ok,
                        "explanation": q.get("explanation", "")})
    score = round(correct / len(qs), 3) if qs else 0.0
    progress.log(f"{a.section}_mcq", item=a.id, correct=correct, total=len(qs), score=score)
    return {"correct": correct, "total": len(qs), "score": score, "results": results}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
