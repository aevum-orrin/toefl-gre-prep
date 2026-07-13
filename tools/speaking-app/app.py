"""speaking-app: local web tool for TOEFL 2026 speaking practice.

Two modes = the two new 2026 speaking tasks:
  - Listen & Repeat:   browser speaks a sentence (Web Speech API) -> you repeat ->
                       faster-whisper transcribes -> word-overlap accuracy.
  - Take an Interview: one topic with 4 spoken questions -> you answer each ->
                       transcribe -> prep_core.FeedbackEngine scores against the official rubric.

Content is HYBRID: a pre-built bank (instant, exam-faithful, offline-safe) plus optional REAL-TIME
generation of fresh items on the free LLM tier (?/generate endpoints), with the bank as fallback.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8002
Open http://localhost:8002  (localhost — mic needs a secure context; over SSH forward the port).
Speaking needs a microphone, so run this on your laptop, not a cluster node.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from prep_core import (FeedbackEngine, Rubric, ProgressStore, QuestionGenerator, load_env,
                       make_fallback_provider)
from prep_core.audio import Transcriber, word_accuracy

HERE = Path(__file__).parent
REPO = HERE.parents[1]
load_env(REPO / ".env")

# Exam-specific content lives under the exam folder (this tool stays exam-agnostic).
SPEAKING_DIR = Path(os.environ.get("SPEAKING_DIR") or REPO / "toefl" / "speaking")
RUBRIC = Rubric.from_json(REPO / "toefl" / "rubrics" / "speaking" / "speaking_interview.json")
DATA_DIR = Path(os.environ.get("PREP_DATA_DIR") or REPO / "data")   # user records -> scratch (env.sh)
REC_DIR = DATA_DIR / "recordings"          # recordings can get large -> scratch

# Real ETS/TPO speaking content lives on scratch (REAL_DATA_ROOT); mixed in, real first.
REAL_ROOT = Path(os.environ.get("REAL_DATA_ROOT")
                 or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/official-real")


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return default


# Listen-and-Repeat sentences: real first, then AI bank; SENT_SRC tracks provenance per index.
_real_sents = [s for s in _read_json(REAL_ROOT / "speaking" / "sentences.json", []) if isinstance(s, str)]
_ai_sents = [s for s in _read_json(SPEAKING_DIR / "sentences.json", []) if isinstance(s, str)]
SENTENCES: list[str] = _real_sents + _ai_sents
SENT_SRC: list[str] = ["real"] * len(_real_sents) + ["ai"] * len(_ai_sents)


def _norm_topic(item, src):
    if isinstance(item, dict) and "questions" in item:
        return {"topic": item.get("topic", "Interview"),
                "questions": [q for q in item["questions"] if isinstance(q, str)],
                "answers": [a for a in item.get("answers", []) if isinstance(a, str)],
                "source": item.get("source", src)}
    if isinstance(item, str):
        return {"topic": "Interview", "questions": [item], "answers": [], "source": src}
    return None


def _load_interview_topics() -> list[dict]:
    """Interview bank as [{topic, questions, answers, source}] — real (scratch) first, then AI."""
    real = [_norm_topic(x, "real") for x in _read_json(REAL_ROOT / "speaking" / "interview.json", [])]
    ai = [_norm_topic(x, "ai") for x in _read_json(SPEAKING_DIR / "interview_questions.json", [])]
    return [t for t in real + ai if t]


TOPICS = _load_interview_topics()

engine = FeedbackEngine(provider=make_fallback_provider())   # live scoring: Gemini->Groq (env order)
generator = QuestionGenerator(engine.provider)   # real-time gen when a backend is available
transcriber = Transcriber(os.environ.get("WHISPER_MODEL", "tiny.en"))
progress = ProgressStore(DATA_DIR / "progress.jsonl")

app = FastAPI(title="TOEFL Speaking App")


async def _save_upload(upload: UploadFile) -> str:
    REC_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "clip.webm").suffix or ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix, dir=REC_DIR)
    with os.fdopen(fd, "wb") as f:
        f.write(await upload.read())
    return path


@app.get("/api/status")
def status():
    return {"offline": engine.offline, "provider": engine.provider_name, "model": engine.model,
            "whisper": transcriber.model_name, "live_generation": generator.available,
            "hint": "Set GEMINI_API_KEY (free) in .env for real scoring + live question generation."
                    if engine.offline else "Live."}


# ---- Listen and Repeat ----
@app.get("/api/repeat")
def repeat(i: int = 0):
    i %= len(SENTENCES)
    return {"i": i, "total": len(SENTENCES), "sentence": SENTENCES[i], "source": "bank",
            "provenance": SENT_SRC[i]}


@app.get("/api/repeat/generate")
def repeat_generate():
    """Fresh sentence from the LLM; falls back to the bank if no backend is available."""
    if generator.available:
        try:
            return {"sentence": generator.repeat_sentence(), "source": "live"}
        except Exception as e:  # rate limit / network -> graceful fallback
            return {"sentence": SENTENCES[0], "source": "bank", "note": f"live gen failed: {e}"}
    return {"sentence": SENTENCES[0], "source": "bank", "note": "no LLM backend; set a key for live gen"}


@app.post("/api/repeat/score")
async def repeat_score(audio: UploadFile = File(...), target: str = Form(...)):
    path = await _save_upload(audio)
    result = transcriber.transcribe(path)
    acc = word_accuracy(target, result["text"])
    progress.log("speaking_repeat", accuracy=acc, target=target)
    return {"transcript": result["text"], "accuracy": acc, "target": target}


# ---- Take an Interview ----
@app.get("/api/interview")
def interview(i: int = 0):
    i %= len(TOPICS)
    t = TOPICS[i]
    return {"i": i, "total": len(TOPICS), "topic": t["topic"], "questions": t["questions"],
            "source": "bank", "provenance": t.get("source", "ai")}


@app.get("/api/interview/generate")
def interview_generate():
    """Fresh topic + 4 questions from the LLM; falls back to the bank if unavailable."""
    if generator.available:
        try:
            t = generator.interview_topic()
            return {**t, "source": "live"}
        except Exception as e:
            return {**TOPICS[0], "source": "bank", "note": f"live gen failed: {e}"}
    return {**TOPICS[0], "source": "bank", "note": "no LLM backend; set a key for live gen"}


@app.get("/api/interview/model")
def interview_model(i: int = 0, q: int = 0):
    """Pre-written top-band model answer for a bank interview question (null for fresh topics)."""
    if 0 <= i < len(TOPICS):
        answers = TOPICS[i].get("answers") or []
        if 0 <= q < len(answers) and answers[q]:
            return {"answer": answers[q], "source": "bank"}
    return {"answer": None}


@app.post("/api/interview/score")
async def interview_score(audio: UploadFile = File(...), question: str = Form(...)):
    path = await _save_upload(audio)
    result = transcriber.transcribe(path)
    try:
        fb = engine.score_speaking(result["text"], RUBRIC, question=question)
    except Exception as e:                       # transient LLM error (e.g. 503 overload)
        return {"transcript": result["text"], "error": f"Scoring backend busy, please retry. ({type(e).__name__})"}
    progress.log("speaking_interview", band=fb.band, offline=fb.offline, question=question)
    return {"transcript": result["text"], **fb.to_dict()}


@app.get("/")
def index():
    # no-cache: always revalidate, so a stale cached page can never run outdated JS
    return FileResponse(HERE / "static" / "index.html",
                        headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
