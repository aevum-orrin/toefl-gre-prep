"""writing-coach: local web tool that scores & polishes TOEFL essays using prep-core.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8001
Then open http://localhost:8001  (set ANTHROPIC_API_KEY in ../../.env for real feedback).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import FeedbackEngine, Rubric, ProgressStore

HERE = Path(__file__).parent
RUBRIC_DIR = HERE / "rubrics"
DATA_DIR = HERE.parents[1] / "data"   # toefl/data (gitignored)

# Load every rubric JSON once, keyed by task_type.
RUBRICS: dict[str, Rubric] = {
    Rubric.from_json(p).task_type: Rubric.from_json(p)
    for p in RUBRIC_DIR.glob("*.json")
}

engine = FeedbackEngine()             # offline stub unless ANTHROPIC_API_KEY is set
progress = ProgressStore(DATA_DIR / "progress.jsonl")

app = FastAPI(title="TOEFL Writing Coach")


class ScoreRequest(BaseModel):
    task_type: str
    essay: str
    prompt_text: str = ""


@app.get("/api/tasks")
def tasks():
    return [{"task_type": r.task_type, "name": r.name,
             "scale": [r.scale_min, r.scale_max]} for r in RUBRICS.values()]


@app.get("/api/status")
def status():
    return {"offline": engine.offline, "model": engine.model,
            "hint": "Set ANTHROPIC_API_KEY in toefl/.env for real Claude feedback." if engine.offline else "Live."}


@app.post("/api/score")
def score(req: ScoreRequest):
    rubric = RUBRICS.get(req.task_type)
    if rubric is None:
        return {"error": f"unknown task_type '{req.task_type}'", "available": list(RUBRICS)}
    fb = engine.score_writing(req.essay, rubric, prompt_text=req.prompt_text)
    progress.log("writing", task=req.task_type, band=fb.band, offline=fb.offline,
                 words=len(req.essay.split()))
    return fb.to_dict()


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
