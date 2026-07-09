# speaking-app

Local web tool for **TOEFL 2026 speaking** practice. Two modes matching the new tasks:

- **Listen & Repeat** — the browser reads a sentence aloud (Web Speech API), you repeat it,
  `faster-whisper` transcribes your audio, and you get a word-match score.
- **Take an Interview** — the browser reads an interview question, you answer, it transcribes,
  and `prep_core.FeedbackEngine` (Claude) scores delivery / language / topic development + gives
  a model answer.

## Run (on a machine with a microphone — i.e. your laptop)

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh
cd tools/speaking-app
uvicorn app:app --reload --port 8002
# open http://localhost:8002
```

**Mic needs a secure context** — use `http://localhost` (not the machine's IP). If the server
runs on the cluster, SSH-forward the port so the browser sees localhost:

```bash
ssh -L 8002:localhost:8002 greatlakes   # then open http://localhost:8002 on your laptop
```

The cluster has **no microphone**, so recording only works where the browser + mic are (your
laptop). Whisper transcription runs server-side; the first run downloads the model (~75 MB).
Set `WHISPER_MODEL=base.en` (or `small.en`) for better accuracy; `tiny.en` is the fast default.

## Reuse for GRE

GRE has no speaking section, so this app is TOEFL-only — but its building blocks
(`Transcriber`, `word_accuracy`, `FeedbackEngine`) all live in `prep-core`, so nothing is wasted.

## Endpoints
- `GET /api/status` — offline/live + whisper model
- `GET /api/repeat?i=N` / `POST /api/repeat/score` (audio + `target`) → `{transcript, accuracy}`
- `GET /api/interview?i=N` / `POST /api/interview/score` (audio + `question`) → feedback JSON
