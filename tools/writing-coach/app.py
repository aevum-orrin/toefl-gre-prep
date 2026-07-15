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

from prep_core import (FeedbackEngine, Rubric, ProgressStore, QuestionGenerator,
                       make_fallback_provider, load_env)

HERE = Path(__file__).parent
REPO = HERE.parents[1]                                    # monorepo root
load_env(REPO / ".env")                                  # in-process only (keeps key out of the shell)

# Exam-specific rubrics + prompt banks live under the exam folder; this tool is exam-agnostic.
# GRE reuses this same app by pointing RUBRICS_DIR / WRITING_DIR at gre/.
RUBRIC_DIR = Path(os.environ.get("RUBRICS_DIR") or REPO / "toefl" / "rubrics" / "writing")
WRITING_DIR = Path(os.environ.get("WRITING_DIR") or REPO / "toefl" / "writing")
DATA_DIR = Path(os.environ.get("PREP_DATA_DIR") or REPO / "data")   # user records -> scratch (env.sh)

# Load every rubric JSON once, keyed by task_type.
RUBRICS: dict[str, Rubric] = {}
for p in sorted(RUBRIC_DIR.glob("*.json")):
    r = Rubric.from_json(p)
    RUBRICS[r.task_type] = r

# Prompt banks. task_type -> list of prompt objects. Real ETS/TPO prompts (scratch, source:"real")
# load FIRST, then the AI-practice bank (source:"ai"); the UI badges each.
_PROMPT_FILES = {"write_email": "email_prompts.json", "academic_discussion": "discussion_prompts.json"}
_REAL_FILES = {"write_email": "email.json", "academic_discussion": "discussion.json"}
REAL_ROOT = Path(os.environ.get("REAL_DATA_ROOT")
                 or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/official-real")
PROMPTS: dict[str, list] = {}
for task_type, fname in _PROMPT_FILES.items():
    items: list = []
    real_fp = REAL_ROOT / "writing" / _REAL_FILES[task_type]
    if real_fp.exists():
        try:
            for it in json.loads(real_fp.read_text(encoding="utf-8")):
                it.setdefault("source", "real")
                items.append(it)
        except (json.JSONDecodeError, ValueError):
            pass
    fp = WRITING_DIR / fname
    if fp.exists():
        for it in json.loads(fp.read_text(encoding="utf-8")):
            it.setdefault("source", "ai")
            items.append(it)
    if items:
        PROMPTS[task_type] = items

# Indexes over the bank so base prompts serve instantly: pre-written model essays keyed by BOTH the
# base id and each similar-prompt id, and the pre-written set of 3 similar prompts per base prompt.
MODEL_ESSAYS: dict[str, dict[str, str]] = {}      # task_type -> {prompt_id: essay}
SIMILARS: dict[str, dict[str, list]] = {}          # task_type -> {base_id: [{id, text}, ...]}
for _tt, _items in PROMPTS.items():
    _me, _sims = {}, {}
    for _it in _items:
        if _it.get("model_essay"):
            _me[_it["id"]] = _it["model_essay"]
        _sl = []
        for _s in _it.get("similar", []):
            if _s.get("id"):
                if _s.get("model_essay"):
                    _me[_s["id"]] = _s["model_essay"]
                _sl.append({"id": _s["id"], "text": _s.get("text", "")})
        if _sl:
            _sims[_it["id"]] = _sl
    MODEL_ESSAYS[_tt] = _me
    SIMILARS[_tt] = _sims

engine = FeedbackEngine(provider=make_fallback_provider())   # live scoring: Gemini->Groq (env order)
generator = QuestionGenerator(engine.provider)   # for similar-question suggestions
# A model essay must appear even if the primary backend is down, so it uses a best-first fallback
# chain (Claude > Groq > Gemini) that degrades until one model answers.
essay_provider = make_fallback_provider()
progress = ProgressStore(DATA_DIR / "progress.jsonl")

_ESSAY_SYSTEM = {
    "write_email": (
        "You are an expert TOEFL iBT 2026 test-taker. Write a MODEL response to the given "
        "'Write an Email' task that would earn the top band (5/5): 80-120 words, appropriate "
        "salutation and closing, accomplish EVERY requirement stated in the task, polite and "
        "appropriately formal register, clear organization. Return ONLY the email text."
    ),
    "academic_discussion": (
        "You are an expert TOEFL iBT 2026 test-taker. Write a MODEL post for the given 'Write for "
        "an Academic Discussion' task that would earn the top band (5/5): 100-130 words, a clear "
        "opinion that directly answers the professor and is backed by a specific reason or example, "
        "engaging naturally with the classmates' posts, natural academic register. Return ONLY the post."
    ),
}

app = FastAPI(title="Writing Coach")
# Auto-exit after a long idle stretch so a server forgotten on one shared login node
# frees its port/resources instead of lingering (see prep_core.serverutil).
from prep_core import install_idle_shutdown
install_idle_shutdown(app)



class ScoreRequest(BaseModel):
    task_type: str
    essay: str
    prompt_text: str = ""


class SimilarRequest(BaseModel):
    task_type: str
    example: str = ""
    prompt_id: str = ""


class EssayRequest(BaseModel):
    task_type: str
    prompt_id: str = ""
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
    """The prompt bank for a task (model_essay stripped so it isn't revealed before scoring)."""
    hide = ("model_essay", "similar")
    return [{k: v for k, v in it.items() if k not in hide} for it in PROMPTS.get(task_type, [])]


@app.post("/api/similar")
def similar(req: SimilarRequest):
    """3 same-type practice prompts. For a base-bank prompt these are PRE-WRITTEN (each with its own
    model essay), so they're instant and top quality; for a pasted prompt they're generated live."""
    pre = SIMILARS.get(req.task_type, {}).get(req.prompt_id)
    if pre:
        return {"available": True, "source": "bank", "prompts": pre}
    if not generator.available:
        return {"available": False, "prompts": []}
    try:
        texts = generator.similar_prompts(req.task_type, req.example)
        return {"available": True, "source": "generated", "prompts": [{"id": "", "text": t} for t in texts]}
    except Exception as e:
        return {"available": False, "prompts": [], "error": str(e)}


@app.post("/api/score")
def score(req: ScoreRequest):
    rubric = RUBRICS.get(req.task_type)
    if rubric is None:
        return {"error": f"unknown task_type '{req.task_type}'", "available": list(RUBRICS)}
    try:
        fb = engine.score_writing(req.essay, rubric, prompt_text=req.prompt_text)
    except Exception as e:                       # transient LLM error (e.g. 503 overload)
        return {"error": f"Scoring backend busy, please retry. ({type(e).__name__})"}
    progress.log("writing", task=req.task_type, band=fb.band, offline=fb.offline,
                 words=len(req.essay.split()))
    return fb.to_dict()


@app.post("/api/model_essay")
def model_essay(req: EssayRequest):
    """A top-band model answer (范文). Pre-written for base-bank prompts (instant); otherwise
    generated on demand with the best available model, degrading until one succeeds."""
    pre = MODEL_ESSAYS.get(req.task_type, {}).get(req.prompt_id)
    if pre:
        return {"essay": pre, "source": "bank", "provider": "pre-written"}
    if essay_provider is None:
        return {"error": "No model backend configured — add GEMINI_API_KEY or GROQ_API_KEY to .env."}
    system = _ESSAY_SYSTEM.get(req.task_type, _ESSAY_SYSTEM["academic_discussion"])
    task = req.prompt_text.strip() or "(the task prompt was not provided)"
    try:
        essay = essay_provider.complete_text(system, f"Task:\n{task}\n\nWrite the model response now.")
    except Exception as e:                       # every backend in the chain failed
        return {"error": f"All model providers are busy — please retry. ({type(e).__name__})"}
    return {"essay": (essay or "").strip(), "source": "generated", "provider": essay_provider.name}


@app.get("/")
def index():
    # no-cache: always revalidate, so a stale cached page can never run outdated JS
    return FileResponse(HERE / "static" / "index.html",
                        headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
