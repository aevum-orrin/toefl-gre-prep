"""writing-coach: local web tool that scores & polishes TOEFL/GRE writing using prep-core.

Backend-agnostic: scores with whatever LLM prep_core picks (free Gemini by default; Groq/Anthropic
via LLM_PROVIDER; offline stub with no key). Serves the official 2026 TOEFL writing tasks
(Write an Email, Write for an Academic Discussion) with a real prompt bank.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8001
Then open http://localhost:8001  (set GEMINI_API_KEY in ../../.env for real, free feedback).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import FeedbackEngine, Rubric, ProgressStore, load_env

HERE = Path(__file__).parent
REPO = HERE.parents[1]                                    # monorepo root
load_env(REPO / ".env")                                  # in-process only (keeps key out of the shell)

# Exam-specific rubrics + prompt banks live under the exam folder; this tool is exam-agnostic.
# GRE reuses this same app by pointing RUBRICS_DIR / WRITING_DIR at gre/.
RUBRIC_DIR = Path(os.environ.get("RUBRICS_DIR") or REPO / "toefl" / "rubrics" / "writing")
WRITING_DIR = Path(os.environ.get("WRITING_DIR") or REPO / "toefl" / "writing")
DATA_DIR = REPO / "data"                                  # gitignored

# Load every rubric JSON once, keyed by task_type.
RUBRICS: dict[str, Rubric] = {}
for p in sorted(RUBRIC_DIR.glob("*.json")):
    r = Rubric.from_json(p)
    RUBRICS[r.task_type] = r

# Optional prompt banks (generated content). task_type -> list of prompt objects.
_PROMPT_FILES = {"write_email": "email_prompts.json", "academic_discussion": "discussion_prompts.json"}
PROMPTS: dict[str, list] = {}
for task_type, fname in _PROMPT_FILES.items():
    fp = WRITING_DIR / fname
    if fp.exists():
        PROMPTS[task_type] = json.loads(fp.read_text(encoding="utf-8"))

engine = FeedbackEngine()             # provider auto-picked from env; offline stub if no key
progress = ProgressStore(DATA_DIR / "progress.jsonl")

app = FastAPI(title="Writing Coach")


class ScoreRequest(BaseModel):
    task_type: str
    essay: str
    prompt_text: str = ""


@app.get("/api/tasks")
def tasks():
    return [{"task_type": r.task_type, "name": r.name, "scale": [r.scale_min, r.scale_max],
             "prompts": len(PROMPTS.get(r.task_type, []))} for r in RUBRICS.values()]


@app.get("/api/status")
def status():
    return {"offline": engine.offline, "provider": engine.provider_name, "model": engine.model,
            "hint": "Set GEMINI_API_KEY (free) in .env for real feedback." if engine.offline else "Live."}


@app.get("/api/prompts")
def prompts(task_type: str):
    """The prompt bank for a task (empty list if none generated yet)."""
    return PROMPTS.get(task_type, [])


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
