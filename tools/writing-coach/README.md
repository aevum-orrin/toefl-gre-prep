# writing-coach

Local web tool: pick a 2026 TOEFL writing task, load a real prompt (or paste your own), write your
response → get a 0–5 task score, per-criterion feedback, top fixes, and a polished rewrite. Powered by
`prep_core.FeedbackEngine` over a pluggable backend (free **Gemini** by default; Groq / Anthropic /
offline via `LLM_PROVIDER`).

## Run

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh
cd tools/writing-coach
uvicorn app:app --reload --port 8001   # open http://localhost:8001
```

With no LLM key it runs in **offline stub** mode (structure works, scores are fake). Add a free
`GEMINI_API_KEY` (https://aistudio.google.com/apikey) to `toefl-gre-prep/.env` for real feedback
(loaded in-process, not into the shell).

## Tasks & prompts (2026 official)

Writing rubrics live under `toefl/rubrics/writing/*.json` (this app reads `RUBRICS_DIR`, default that
folder): **Write an Email** and **Write for an Academic Discussion**, each with the official 0–5
facets. Prompt banks live in `toefl/writing/{email_prompts,discussion_prompts}.json`, served via
`/api/prompts`. Reuse seam for **GRE**: add `gre/rubrics/` (Issue / Argument) + point
`RUBRICS_DIR`/`WRITING_DIR` there — prep-core and this app unchanged.

## Endpoints
- `GET /api/tasks` — rubrics (+ prompt counts)
- `GET /api/prompts?task_type=…` — the prompt bank for a task
- `GET /api/status` — offline/live + provider/model
- `POST /api/score` — `{task_type, essay, prompt_text}` → feedback JSON (logged to `data/progress.jsonl`)
