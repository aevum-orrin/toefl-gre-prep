# TOEFL & GRE Prep
# this is for vocab practice only
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
│   ├── writing-coach/ # AI essay scoring/polish (FastAPI + web)                 :8001
│   ├── speaking-app/  # speaking: Listen&Repeat + Interview (record+Whisper+AI) :8002
│   ├── vocab-srs/     # vocabulary: SM-2 flashcards over big ECDICT decks       :8003
│   ├── reading-listening/ # Reading + Listening practice, auto-scored, free     :8004
│   └── mock-test/     # full-length TIMED R/L, 2 adaptive modules, 1–6 band     :8005
├── scripts/           # data pipeline: build_vocab · enrich_vocab · merge_rl
├── toefl/             # TOEFL-specific data
│   ├── rubrics/{writing,speaking}/  # official 2026 0–5 facets
│   ├── speaking/      # Listen&Repeat sentences (60) + interview topics (20 × 4 Qs)
│   ├── writing/       # email (20) + academic-discussion (20) prompt banks
│   ├── reading/       # academic · daily_life · complete_words   (task-typed MCQ)
│   ├── listening/     # academic_talk · conversation · announcement · choose_response
│   ├── vocab/         # TOEFL wordlist — 9927 words (ECDICT-derived)
│   └── plan/          # 14-day plan
├── gre/vocab/         # GRE wordlist — 10526 words (ECDICT-derived)
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

## Vocabulary decks (ECDICT-backed) & Reading/Listening bank

`scripts/build_vocab.py` derives the decks from the open **ECDICT** dictionary, filtered by exam tags —
widened to neighbouring academic-exam lists for comprehensive ~10k decks (**TOEFL 9927** = toefl∪ielts∪ky,
**GRE 10526** = gre∪ky, incl. harder/rarer words). Each word carries IPA, per-part-of-speech English +
Chinese senses, a Collins difficulty star, a frequency rank, and verb forms, all offline. `scripts/enrich_vocab.py` then layers on a clean learner definition, one example sentence per
part of speech, and common collocations (free Gemini/Groq, **cached in scratch** so identical input
never re-calls). A daily **scrontab** (Slurm cron) job — `scripts/enrich_cron.sh` at 4 AM — resumes
enrichment on a compute node (which has outbound internet on Great Lakes), spending that day's free API
quota and stopping cleanly when it's used up (`--max-fails`), until both decks are fully enriched.
vocab-srs schedules reviews with SM-2 and introduces a capped number of new words per day (default 20),
most-frequent first.

The Reading/Listening bank is **task-typed** — one JSON file per 2026 task type, loaded by directory
glob (134 items / ~454 questions and growing). `scripts/merge_rl.py` merges freshly generated items into
the canonical per-type files. `mock-test` assembles these into a full-length, timed section.

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

Launch any tool with the helper (loads the env, starts uvicorn, prints the URL):

```bash
./run.sh writing    # writing-coach       http://localhost:8001
./run.sh speaking   # speaking-app        http://localhost:8002  (needs a mic → run on your laptop)
./run.sh vocab      # vocab-srs           http://localhost:8003
./run.sh reading    # reading-listening   http://localhost:8004
./run.sh mock       # mock-test (timed)   http://localhost:8005
```

…or run one directly: `source env.sh && cd tools/writing-coach && uvicorn app:app --reload --port 8001`.
Each tool has its own port, so several can run at once; `Ctrl+C` stops one. For speaking over SSH,
forward the port to your laptop (VS Code does this automatically).

## Progress

- [x] Monorepo + GitHub remote `aevum-orrin/toefl-gre-prep`
- [x] `prep-core`: **multi-backend engine** (gemini/groq/anthropic/offline) + live generation + SRS +
  Progress + Rubric + faster-whisper — unit tests pass
- [x] Verified **2026 official format + 4-section scoring** (`docs/2026-toefl-format.md`); rubrics on
  official 0–5 facets (dropped Integrated Writing, added Write an Email)
- [x] **Big vocab decks** from ECDICT — TOEFL 9927 / GRE 10526 (~10k each), per-POS senses + difficulty + frequency
- [x] **Five apps** (writing-coach, speaking-app, vocab-srs, reading-listening, mock-test) — end-to-end tested
- [x] **Task-typed R/L bank** (134 items / ~454 Q) + full-length timed **mock-test** (2 adaptive modules, 1–6 band)
- [x] Expanded prompt banks: Email 40 · Academic-Discussion 40 · Listen&Repeat 120 · Interview 39
- [x] Real (live) Gemini scoring + live generation verified; strict grading
- [~] Vocab enrichment (examples + collocations) filling in the background, most-frequent first
- [ ] Real microphone speaking test (on your laptop)
- [ ] GRE: add `gre/rubrics/*.json` (Issue/Argument), reuse the apps
