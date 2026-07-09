# reading-listening

Local web tool for **TOEFL 2026 Reading & Listening** practice. Both sections are auto-scored
multiple choice, so this tool uses **no LLM and no paid API — 100% free**.

- **Reading** — shows an academic passage or a daily-life text, then 4-option questions.
- **Listening** — the browser reads an academic talk / conversation / announcement **aloud**
  (Web Speech API, free) and **never shows the transcript**, so it stays a real listening test.
  Play, take notes, then answer.

Correct answers + explanations live server-side and are revealed only after you submit.

## Run

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh
cd tools/reading-listening
uvicorn app:app --reload --port 8004   # open http://localhost:8004
```

Listening needs speakers/headphones and a browser with Web Speech API (Chrome/Edge/Safari).

## Content
Banks live under the exam folder: `toefl/reading/passages.json` and `toefl/listening/talks.json`
(`{id, kind, title, passage|transcript, questions:[{q, options[4], answer, explanation}]}`). Point
`READING_FILE` / `LISTENING_FILE` at GRE equivalents to reuse the app.

## Endpoints
- `GET /api/status` — item counts per section
- `GET /api/item?section=reading|listening&i=N` — one item (answers stripped)
- `POST /api/check` — `{section, id, answers:[idx…]}` → score + per-question correctness + explanations
  (logged to `data/progress.jsonl`)
