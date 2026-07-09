# TOEFL & GRE Prep

A personal TOEFL + GRE prep **monorepo** — one repo holding both exams plus shared code tools: a
short (two-week) sprint on the **2026 new TOEFL**, then **GRE** afterwards. Across the four skills the
focus is on **speaking + writing** (the two weak spots).

> Baseline: TOEFL 107/120 (old scale) two years ago. Day-by-day TOEFL plan:
> [toefl/plan/14-day-plan.md](toefl/plan/14-day-plan.md).

## Why relearn: 2026 TOEFL vs. the version I took two years ago

The test I took in 2024 was already the **2023-07 revision**, so for me the genuinely new material is
the **2026-01-21 reform**:

| Aspect | 2023-07 (what I took) | **2026-01 (this sprint)** |
|--------|------------------------|-----------------------------|
| Total time | ~116 min | **~90 min** |
| Reading / Listening | fixed | **multistage adaptive** |
| Speaking | 4 tasks | **2 new tasks: Listen and Repeat + Take an Interview** |
| Scoring | 0–120 | **new 1–6 band (CEFR-aligned), 4-section average**; 0–120 kept during transition |

**Takeaway:** Speaking is a completely new task set and needs dedicated practice (speaking-app);
Reading/Listening adapt to the adaptive format; Writing keeps Academic Discussion and adds Write an
Email (writing-coach). Full verified format: [docs/2026-toefl-format.md](docs/2026-toefl-format.md).

## Layout (monorepo, everything on `main`)

```
toefl-gre-prep/
├── prep-core/         # shared core (pip -e installable, exam-agnostic)
│   └── src/prep_core/ # FeedbackEngine · providers (multi-backend) · generate (live gen)
│                      #   · SRS · ProgressStore · Rubric · audio (faster-whisper)
├── tools/             # shared apps — used by both TOEFL and GRE
│   ├── writing-coach/ # AI essay scoring/polish (FastAPI + web)              :8001
│   ├── speaking-app/  # speaking: Listen&Repeat + Interview (record+Whisper+AI) :8002
│   └── vocab-srs/     # vocabulary: SM-2 spaced-repetition flashcards        :8003
│   └── reading-listening/ # Reading + Listening MCQ, auto-scored, free       :8004
├── toefl/             # TOEFL-specific data
│   ├── rubrics/{writing,speaking}/  # official 2026 0–5 facets
│   ├── speaking/      # Listen&Repeat sentences (60) + interview topics (20 × 4 Qs)
│   ├── writing/       # email (20) + academic-discussion (20) prompt banks
│   ├── reading/ listening/  # passage + talk banks (12 each) with MCQ
│   ├── vocab/         # TOEFL wordlist (100)
│   └── plan/          # 14-day plan
├── gre/vocab/         # GRE wordlist (100); other GRE content added later
├── docs/              # 2026-toefl-format.md — verified official format + scoring (source of truth)
└── data/              # recordings, progress, SRS state (gitignored)
```

**Reuse:** every exam-agnostic capability lives in `prep-core`; apps point at exam data via
`RUBRICS_DIR` / `SPEAKING_DIR` / wordlist paths. Adding GRE = new `gre/rubrics/*.json` + the existing
`gre/vocab`, with **no change** to the apps or the core.

## AI backend: free-first, one-flag switchable

`FeedbackEngine` and live generation run on a pluggable backend selected by `LLM_PROVIDER` in `.env`
(if unset, it auto-picks the first backend with a key, free-first order gemini→groq→anthropic):

| provider | cost | notes |
|----------|------|-------|
| **gemini** (default) | **free** | Google AI Studio key (no card). Best free quality. On the free tier, inputs may be used by Google to train + human-reviewed. Auto-retries and falls back to gemini-2.0-flash / flash-lite on 503s. |
| **groq** | **free** | Llama-3.3-70B, ~1s feedback, contractually does **not** train on your data (better privacy). |
| **anthropic** | paid | Claude, top quality, **per-token billing (separate from the subscription / Apple Pay)**. |
| **offline** | free | deterministic stub when no key — pipeline only, not real scoring. |

Speech is free and local throughout: **faster-whisper** (STT) + browser **Web Speech API** (TTS). The
prompt banks double as offline practice material and as the fallback when live generation is
unavailable. **Grading is strict** — a top score means a genuinely flawless response.

## Environment (Great Lakes login node)

```bash
source env.sh                     # module load python/3.12.1 ffmpeg/7.1.0 + activate .venv
pip install -r requirements.txt   # first time; includes editable ./prep-core[audio]
```

**Get started for free:** `cp .env.example .env`, then put a free `GEMINI_API_KEY`
(https://aistudio.google.com/apikey, no card) in it for real scoring + live generation. For better
privacy use `GROQ_API_KEY` with `LLM_PROVIDER=groq`. Apps load `.env` **in-process** and never export
it — an exported `ANTHROPIC_API_KEY` would make Claude Code bill that key per-token instead of the Max
subscription. **The Anthropic API is a separate pay-per-token account — not Apple Pay, not the
subscription**; with no card added it simply fails rather than charging silently.

## Usage

```bash
# writing feedback
cd tools/writing-coach && uvicorn app:app --reload --port 8001    # http://localhost:8001
# speaking (needs a mic → run on your laptop; over SSH forward the port to localhost)
cd tools/speaking-app && uvicorn app:app --reload --port 8002     # http://localhost:8002
# vocabulary (SM-2 spaced repetition, shared by TOEFL/GRE)
cd tools/vocab-srs && uvicorn app:app --reload --port 8003        # http://localhost:8003
# reading + listening (auto-scored, no key needed)
cd tools/reading-listening && uvicorn app:app --reload --port 8004 # http://localhost:8004
```

## Progress

- [x] Monorepo + GitHub remote (repo renamed `toefl-gre-prep`)
- [x] `prep-core`: **multi-backend engine** (gemini/groq/anthropic/offline) + **live generation** +
  SRS + Progress + Rubric + faster-whisper — 4 unit tests pass
- [x] Verified **2026 official format + 4-section scoring** (`docs/2026-toefl-format.md`); rubrics
  updated to official 0–5 facets (drop Integrated Writing, add Write an Email)
- [x] Content banks: Listen&Repeat 60 / interview 20 topics / email 20 / discussion 20 / reading 12 /
  listening 12 / vocab 100×2
- [x] Four apps (writing-coach, speaking-app, vocab-srs, reading-listening) — end-to-end tested
- [x] Real (live) Gemini scoring + live generation verified; strict grading
- [ ] Real microphone speaking test (on your laptop)
- [ ] GRE: add `gre/rubrics/*.json` (Issue/Argument), reuse the four apps
