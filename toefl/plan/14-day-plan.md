# 14-Day TOEFL Sprint Plan (2026 format)

Baseline 107. Focus on **speaking + writing**, while adapting to 2026 adaptive Reading/Listening and
the new Speaking task types.

## Diagnostic (Day 0 first)

Take one full mock in the 2026 format (TPO or an official practice test) and get a band per section to
locate real weaknesses — "I feel speaking/writing are weak" is not reliable; use data.

## Daily rhythm (adjust as needed)

| Day | Theme | Morning | Afternoon | Evening (AI tools) |
|-----|-------|---------|-----------|--------------------|
| D1 | Diagnostic + new task types | Full mock | Review all four sections | Record a speaking baseline, score it in speaking-app |
| D2 | Speaking · Listen & Repeat | Official-sample intensive listening/shadowing | Shadow 20 min | speaking-app repeat scoring + writing-coach on 1 discussion |
| D3 | Speaking · Take an Interview | Interview bank (one topic, 4 Qs) | Timed recorded answers | speaking-app AI feedback on pronunciation/fluency (✨ live-gen new items) |
| D4 | Writing · Academic Discussion | Structure template + argument bank | Timed 10-min drafts ×2 | writing-coach polish + compare to model |
| D5 | Writing · Write an Email | Email register/politeness + 20-prompt bank | Timed 7-min drafts ×2 | writing-coach checks register / whether the purpose is met |
| D6 | Reading · adaptive strategy | reading-listening timed reading | Categorize error types | vocab-srs for the day's new words |
| D7 | Listening · adaptive + lecture notes | reading-listening lectures (TTS read aloud) | Note-taking review | Redo the week's errors |
| D8 | Mid mock | Full mock in the new format | Review all four sections | Re-weight weaknesses |
| D9–D12 | Weakness-weighted rotation | 1 round each of speaking/writing | Shore up reading/listening | Nightly AI feedback + vocab-srs |
| D13 | Full mock (final push) | Mock | Refine speaking/writing templates | Last high-frequency vocab round |
| D14 | Taper + light review | Templates / error log | Rest, fix sleep schedule | Pre-test state check |

## Reusable architecture (TOEFL ↔ GRE)

**Monorepo**: one repo `toefl-gre-prep`, with both exams + shared code as sibling folders (all on
`main`).

```
toefl-gre-prep/
├── prep-core/   shared core (pip install -e ./prep-core)
├── tools/       shared apps (writing-coach, speaking-app, vocab-srs, reading-listening)
├── toefl/       TOEFL data (rubrics, speaking, writing, reading, listening, vocab, plan)
└── gre/         GRE data (vocab ready; rubrics added later)
```

- **`prep-core` provides**: `FeedbackEngine` (multi-backend gemini/groq/anthropic/offline + rubric),
  `QuestionGenerator` (live generation), `SRS`, `Transcriber` (faster-whisper), `ProgressStore`.
- **Free-first AI**: defaults to the Gemini free tier; speech uses local faster-whisper + browser TTS,
  so it is zero-cost end to end.
- **Adding GRE**: create `gre/rubrics/*.json` (Issue/Argument); vocab is ready; the four apps need
  **no changes**.

## The four tools (all local web pages, ports 8001–8004)

### writing-coach :8001
- Pick a 2026 writing task (Write an Email / Academic Discussion) → load an official-style prompt or
  paste your own → strict 0–5 score + per-facet feedback + polished rewrite + 3 similar prompts.

### speaking-app :8002 (needs a mic → run on your laptop)
- Listen & Repeat: TTS plays a sentence → record → Whisper transcribes → word-overlap score.
- Take an Interview: one topic, 4 questions → timed recording → AI feedback against the official
  rubric; ✨ can generate fresh items live.

### vocab-srs :8003
- SM-2 spaced-repetition flashcards; shared TOEFL/GRE wordlists; Anki-style four-button grading.

### reading-listening :8004 (free, no key needed)
- Reading: academic / daily-life texts + 4-option MCQ, auto-scored with explanations.
- Listening: browser TTS reads lectures/conversations aloud (transcript hidden) → 4-option MCQ,
  auto-scored.
