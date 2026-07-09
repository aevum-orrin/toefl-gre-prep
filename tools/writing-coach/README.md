# writing-coach

Local web tool: paste a TOEFL essay → get a band score, per-criterion feedback, top fixes,
and a polished rewrite. Powered by `prep_core.FeedbackEngine` (Claude API).

## Run

```bash
cd /home/ctlang/toefl
source env.sh                      # loads Python 3.12 + venv + .env
cd tools/writing-coach
uvicorn app:app --reload --port 8001
# open http://localhost:8001
```

Without `ANTHROPIC_API_KEY` it runs in **offline stub** mode (structure works, scores are fake).
Add the key to `toefl/.env` for real Claude scoring.

## Add / edit tasks

Drop a rubric JSON in `rubrics/` (see `academic_discussion.json`). It appears automatically.
This is the reuse seam for **GRE**: the GRE repo ships its own `rubrics/` (Issue / Argument)
and reuses this exact app + prep-core unchanged.

## Endpoints
- `GET /api/tasks` — available rubrics
- `GET /api/status` — offline vs live
- `POST /api/score` — `{task_type, essay, prompt_text}` → feedback JSON (also logged to `data/progress.jsonl`)
