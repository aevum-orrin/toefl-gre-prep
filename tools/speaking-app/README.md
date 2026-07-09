# speaking-app

Local web tool for **TOEFL 2026 speaking** practice. Two modes matching the new tasks:

- **Listen & Repeat** — the browser reads a sentence aloud (Web Speech API, free), you repeat it,
  `faster-whisper` transcribes your audio (local, free), and you get a word-match score.
- **Take an Interview** — one topic with 4 spoken questions; the browser reads each aloud, you answer,
  it transcribes, and `prep_core.FeedbackEngine` scores it 0–5 against the official 2026 rubric
  (topic/fluency/intelligibility/language) + gives a model answer.

Content is **hybrid**: a pre-built bank (instant, exam-faithful, offline-safe) plus a **✨ Fresh**
button that generates a brand-new item live on the free LLM tier, with the bank as fallback.

## Run (on a machine with a microphone — i.e. your laptop)

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh
cd tools/speaking-app
uvicorn app:app --reload --port 8002   # open http://localhost:8002
```

**Mic needs a secure context** — use `http://localhost` (not the machine's IP). If the server runs
on the cluster, SSH-forward the port so the browser sees localhost:

```bash
ssh -L 8002:localhost:8002 greatlakes   # then open http://localhost:8002 on your laptop
```

The cluster has **no microphone**, so recording only works where the browser + mic are (your laptop).
Whisper runs server-side; first run downloads the model (~75 MB). `WHISPER_MODEL=base.en`/`small.en`
for better accuracy; `tiny.en` is the fast default. Real interview scoring + live generation need a
free `GEMINI_API_KEY` in `.env`.

## Reuse for GRE
GRE has no speaking section, so this app is TOEFL-only — but its building blocks (`Transcriber`,
`word_accuracy`, `FeedbackEngine`, `QuestionGenerator`) all live in `prep-core`, so nothing is wasted.

## Endpoints
- `GET /api/status` — offline/live + provider/whisper + `live_generation`
- `GET /api/repeat?i=N` · `GET /api/repeat/generate` · `POST /api/repeat/score` (audio + `target`)
- `GET /api/interview?i=N` · `GET /api/interview/generate` · `POST /api/interview/score` (audio + `question`)
