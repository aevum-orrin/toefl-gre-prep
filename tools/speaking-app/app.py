"""speaking-app: local web tool for TOEFL 2026 speaking practice.

Two modes, mirroring the new 2026 speaking tasks:
  - Listen & Repeat:  browser speaks a sentence (Web Speech API) -> you repeat ->
                      faster-whisper transcribes -> word-overlap accuracy.
  - Take an Interview: browser reads a question -> you answer -> transcribe ->
                      Claude (prep_core.FeedbackEngine) scores delivery/language/topic.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8002
Open http://localhost:8002  (use localhost — mic needs a secure context; over SSH forward the port).
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

from prep_core import FeedbackEngine, Rubric, ProgressStore, load_env
from prep_core.audio import Transcriber, word_accuracy

HERE = Path(__file__).parent
REPO = HERE.parents[1]
load_env(REPO / ".env")

# Exam-specific content lives under the exam folder (this tool stays exam-agnostic).
SPEAKING_DIR = Path(os.environ.get("SPEAKING_DIR") or REPO / "toefl" / "speaking")
RUBRIC = Rubric.from_json(REPO / "toefl" / "rubrics" / "speaking.json")
DATA_DIR = REPO / "data"
REC_DIR = DATA_DIR / "recordings"          # gitignored

SENTENCES = json.loads((SPEAKING_DIR / "sentences.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((SPEAKING_DIR / "interview_questions.json").read_text(encoding="utf-8"))

engine = FeedbackEngine()                   # offline stub unless ANTHROPIC_API_KEY is set
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
    return {"offline": engine.offline, "model": engine.model,
            "whisper": transcriber.model_name,
            "hint": "Set ANTHROPIC_API_KEY in .env for real interview scoring." if engine.offline else "Live."}


@app.get("/api/repeat")
def repeat(i: int = 0):
    i %= len(SENTENCES)
    return {"i": i, "total": len(SENTENCES), "sentence": SENTENCES[i]}


@app.post("/api/repeat/score")
async def repeat_score(audio: UploadFile = File(...), target: str = Form(...)):
    path = await _save_upload(audio)
    result = transcriber.transcribe(path)
    acc = word_accuracy(target, result["text"])
    progress.log("speaking_repeat", accuracy=acc, target=target)
    return {"transcript": result["text"], "accuracy": acc, "target": target}


@app.get("/api/interview")
def interview(i: int = 0):
    i %= len(QUESTIONS)
    return {"i": i, "total": len(QUESTIONS), "question": QUESTIONS[i]}


@app.post("/api/interview/score")
async def interview_score(audio: UploadFile = File(...), question: str = Form(...)):
    path = await _save_upload(audio)
    result = transcriber.transcribe(path)
    fb = engine.score_speaking(result["text"], RUBRIC, question=question)
    progress.log("speaking_interview", band=fb.band, offline=fb.offline, question=question)
    return {"transcript": result["text"], **fb.to_dict()}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
