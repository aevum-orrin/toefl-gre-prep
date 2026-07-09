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
DATA_DIR = REPO / "data"

SECTIONS = {
    "reading": Path(os.environ.get("READING_FILE") or REPO / "toefl" / "reading" / "passages.json"),
    "listening": Path(os.environ.get("LISTENING_FILE") or REPO / "toefl" / "listening" / "talks.json"),
}


def _load(section: str) -> list[dict]:
    p = SECTIONS[section]
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


ITEMS: dict[str, list[dict]] = {s: _load(s) for s in SECTIONS}
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
    out = {"id": it["id"], "kind": it.get("kind", ""), "title": it.get("title", ""), "questions": qs}
    if section == "reading":
        out["passage"] = it["passage"]       # reading text is meant to be read
    else:
        out["transcript"] = it["transcript"]  # for TTS only; the frontend never displays it
    return out


@app.get("/api/status")
def status():
    return {s: len(ITEMS[s]) for s in SECTIONS}


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
