# writing-coach

Local web tool: paste a TOEFL essay → get a band score, per-criterion feedback, top fixes,
and a polished rewrite. Powered by `prep_core.FeedbackEngine` (Claude API).

## Run

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh                      # loads Python 3.12 + venv
cd tools/writing-coach
uvicorn app:app --reload --port 8001
# open http://localhost:8001
```

Without `ANTHROPIC_API_KEY` it runs in **offline stub** mode (structure works, scores are fake).
Add the key to `toefl-gre-prep/.env` for real Claude scoring (loaded in-process, not into the shell).

## Add / edit tasks

Rubrics live under the exam folder: `toefl/rubrics/*.json` (this app is exam-agnostic and reads
`RUBRICS_DIR`, default `toefl/rubrics`). Drop a new rubric JSON there and it appears automatically.
This is the reuse seam for **GRE**: add `gre/rubrics/` (Issue / Argument) and run the same app with
`RUBRICS_DIR=…/gre/rubrics` — prep-core and this app unchanged.

## Endpoints
- `GET /api/tasks` — available rubrics
- `GET /api/status` — offline vs live
- `POST /api/score` — `{task_type, essay, prompt_text}` → feedback JSON (also logged to `data/progress.jsonl`)
