# prep-core

Exam-agnostic core shared by my **TOEFL** and **GRE** prep repos. Everything here is
independent of any specific exam; each exam repo supplies its own rubrics, word lists and UI.

## What's inside

| Module | Class | Purpose |
|--------|-------|---------|
| `feedback` | `FeedbackEngine` | Score & revise writing/speaking via Claude API; **offline stub** when no key |
| `rubric` | `Rubric`, `Criterion` | Load exam rubrics from JSON; render them into prompts |
| `srs` | `SRS`, `Card` | SM-2 spaced-repetition vocab; JSON-persisted |
| `progress` | `ProgressStore` | Append-only JSONL practice log |
| `audio` | `Transcriber` | Local Whisper transcription for speaking practice (optional dep) |

## Install (editable, for development)

```bash
pip install -e /home/ctlang/prep-core            # core
pip install -e "/home/ctlang/prep-core[audio]"   # + whisper for speaking practice
```

The consuming repo (toefl-learning / gre-learning) depends on this via editable install
during development. `ANTHROPIC_API_KEY` (in the app's `.env`) switches FeedbackEngine from
the offline stub to real Claude calls.
