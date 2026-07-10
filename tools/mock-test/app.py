"""mock-test: full-length, timed 2026 TOEFL Reading & Listening simulation.

Assembles a section from the task-type bank (toefl/reading, toefl/listening) in TWO
multistage-adaptive modules: module 1 is fixed; module 2 is "hard" (academic-heavy)
or "easy" (daily-life-heavy) depending on the module-1 score — mirroring the real
2026 routing. Auto-scored, estimates a 1-6 band. Fully offline, no LLM.

HONEST APPROXIMATION: ETS does not publish per-module item counts or the raw->band
conversion, so this is a fixed standard-difficulty mock, not the exact adaptive test.
The UI says so.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8005
Open http://localhost:8005
"""
from __future__ import annotations

import json
import random
import secrets
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).parent
REPO = HERE.parents[1]

SECTION_DIRS = {
    "reading": REPO / "toefl" / "reading",
    "listening": REPO / "toefl" / "listening",
}
TIME_LIMIT_SEC = {"reading": 30 * 60, "listening": 29 * 60}

# Module blueprint: (kind, how many items to sample without replacement).
# Approximates the 2026 mix; module 2 differs by measured level.
BLUEPRINTS = {
    "reading": {
        "1":    [("academic_passage", 2), ("daily_life", 2), ("complete_words", 1)],
        "hard": [("academic_passage", 3), ("complete_words", 1)],
        "easy": [("daily_life", 4), ("academic_passage", 1), ("complete_words", 1)],
    },
    "listening": {
        "1":    [("choose_response", 3), ("conversation", 1), ("announcement", 1), ("academic_talk", 1)],
        "hard": [("academic_talk", 2), ("conversation", 1)],
        "easy": [("academic_talk", 1), ("conversation", 1), ("choose_response", 3), ("announcement", 1)],
    },
}


def _load_by_kind(section: str) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(SECTION_DIRS[section].glob("*.json")):
        try:
            for it in json.loads(f.read_text(encoding="utf-8")):
                by[it.get("kind", "")].append(it)
        except (json.JSONDecodeError, ValueError):
            continue
    return by


BANK = {s: _load_by_kind(s) for s in SECTION_DIRS}
TESTS: dict[str, dict] = {}   # in-memory session store (answer keys never leave the server)

app = FastAPI(title="TOEFL Mock Test")


class Start(BaseModel):
    section: str


class Submit(BaseModel):
    test_id: str
    module: int                              # 1 or 2
    responses: dict[str, list[int]]          # item_id -> chosen option index per question


def _sample(section: str, blueprint, used: set[str]) -> list[dict]:
    out: list[dict] = []
    for kind, n in blueprint:
        pool = [it for it in BANK[section].get(kind, []) if it["id"] not in used]
        random.shuffle(pool)
        for it in pool[:n]:
            used.add(it["id"])
            out.append(it)
    return out


def _public(it: dict) -> dict:
    out = {"id": it["id"], "kind": it.get("kind", ""), "title": it.get("title", ""),
           "questions": [{"q": q["q"], "options": q["options"]} for q in it["questions"]]}
    if "passage" in it:
        out["passage"] = it["passage"]
    if "transcript" in it:
        out["transcript"] = it["transcript"]  # listening: TTS only, UI never displays it
    return out


def _grade(items: list[dict], responses: dict[str, list[int]]):
    correct = total = 0
    review = []
    for it in items:
        chosen = responses.get(it["id"], [])
        qres = []
        for i, q in enumerate(it["questions"]):
            c = chosen[i] if i < len(chosen) else -1
            ok = (c == q["answer"])
            correct += ok
            total += 1
            qres.append({"q": q["q"], "options": q["options"], "chosen": c,
                         "answer": q["answer"], "correct": ok, "explanation": q.get("explanation", "")})
        review.append({"kind": it.get("kind", ""), "title": it.get("title", ""), "results": qres})
    return correct, total, review


_CEFR = [(6.0, "C2"), (5.0, "C1"), (4.0, "B2"), (3.0, "B1"), (2.0, "A2"), (1.0, "A1")]


def _band(pct: float) -> float:
    return max(1.0, min(6.0, round((1.0 + 5.0 * pct) * 2) / 2))


def _cefr(band: float) -> str:
    return next((lbl for thr, lbl in _CEFR if band >= thr), "A1")


@app.get("/api/status")
def status():
    return {s: {k: len(v) for k, v in BANK[s].items()} for s in SECTION_DIRS}


@app.post("/api/mock/start")
def start(s: Start):
    if s.section not in BANK:
        return {"error": f"unknown section '{s.section}'"}
    used: set[str] = set()
    m1 = _sample(s.section, BLUEPRINTS[s.section]["1"], used)
    if not m1:
        return {"error": "bank is empty for this section — generate content first"}
    tid = secrets.token_hex(6)
    TESTS[tid] = {"section": s.section, "used": used, "m1": m1, "m2": None,
                  "variant": None, "acc": {"correct": 0, "total": 0}, "review": []}
    return {"test_id": tid, "section": s.section, "module": 1, "total_modules": 2,
            "time_limit_sec": TIME_LIMIT_SEC[s.section],
            "items": [_public(it) for it in m1]}


@app.post("/api/mock/submit")
def submit(sub: Submit):
    t = TESTS.get(sub.test_id)
    if not t:
        return {"error": "unknown or finished test — start a new one"}
    section = t["section"]

    if sub.module == 1:
        c, tot, rev = _grade(t["m1"], sub.responses)
        t["acc"]["correct"] += c
        t["acc"]["total"] += tot
        t["review"] += rev
        variant = "hard" if (tot and c / tot >= 0.6) else "easy"
        m2 = _sample(section, BLUEPRINTS[section][variant], t["used"])
        t["m2"], t["variant"] = m2, variant
        return {"module": 2, "variant": variant,
                "module1": {"correct": c, "total": tot},
                "items": [_public(it) for it in m2]}

    if t.get("m2") is None:
        return {"error": "submit module 1 first"}
    c, tot, rev = _grade(t["m2"], sub.responses)
    t["acc"]["correct"] += c
    t["acc"]["total"] += tot
    t["review"] += rev
    a = t["acc"]
    pct = a["correct"] / a["total"] if a["total"] else 0.0
    band = _band(pct)
    out = {"done": True, "section": section, "variant": t["variant"],
           "correct": a["correct"], "total": a["total"], "pct": round(pct * 100),
           "band": band, "cefr": _cefr(band), "review": t["review"]}
    TESTS.pop(sub.test_id, None)
    return out


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
