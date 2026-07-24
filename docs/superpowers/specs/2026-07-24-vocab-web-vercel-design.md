# vocab-srs on Vercel — design

Date: 2026-07-24 · Branch: `test-vocab-web` · Status: approved (approach A)

## Goal
Deploy the `vocab-srs` tool as a public-URL website on Vercel so it can be used from phone and
laptop, replacing the current "SSH into a login node, port-forward 8003" workflow. Single user
(the repo owner). Study progress must sync across devices.

## Why the current app cannot be lifted as-is
| Current behaviour | Breaks on Vercel because |
|---|---|
| Deck (14 MB JSON × 2 + 1.3 MB) parsed into process memory at startup | serverless cold start re-parses every time (1–3 s) |
| SRS progress = whole-file read/write of `$PREP_DATA_DIR/srs/<deck>.json` | functions have **no persistent disk**; writes are lost |
| `_RECENT` in-process `deque` (15-card spacing guard) | each invocation may be a fresh container |
| TTS mp3 cached under `$LANG_PREP_CACHE/tts/` | same ephemeral-disk problem |

## Approach (A): keep FastAPI, move deck + user data into Postgres
Chosen over (B) rewriting the SRS engine client-side — the SM-2 + `prof` + Enter/sticky-Again +
undo/redo semantics are subtle and already tested; rewriting them in JS risks behaviour drift.
Chosen over (C) bundling the deck and only moving progress to a KV store — that leaves the
1–3 s cold start in place.

Moving the deck into the DB fixes persistence **and** cold start in one step.

### Deployment shape
```
api/index.py       FastAPI ASGI app (@vercel/python)   -> /api/*
static/index.html  existing frontend, served by CDN    -> /
vercel.json        routes + function config
requirements.txt   fastapi, psycopg[binary], edge-tts, pydantic
```

### Data model (Neon Postgres)
```sql
words(deck, term, ord, tier, phonetic, ipa_us, ipa_uk, gloss_en,
      synonyms jsonb, antonyms jsonb, etymology jsonb, senses jsonb,
      frq int, bnc int, PRIMARY KEY (deck, term))
srs_cards(user_id, deck, term, ease real, interval int, reps int,
      due text, prof real, flags jsonb, updated_at timestamptz,
      PRIMARY KEY (user_id, deck, term))
notes(user_id, term, md, updated_at timestamptz, PRIMARY KEY (user_id, term))
```
Indexes: `srs_cards(user_id, deck, due)` for the due query; `words(deck, ord)` for new-card order;
`words(deck, term text_pattern_ops)` for `/api/search` substring lookup.

**`ord` is load-bearing.** It stores the word's index in the deck array, so `ORDER BY ord`
reproduces exactly the existing seeded study order (TPO-attested first, tier1+tier2 shuffled
together, tier3 last) from `scripts/order_vocab.py`. Without it, going to a DB would silently
reshuffle the study sequence.

### Statelessness: `_RECENT` moves to the client
The 15-card spacing guard becomes a client-supplied `exclude` parameter on `/api/next` — the
frontend already knows which terms it just showed. This removes the last piece of per-process
state, so any function instance can serve any request.

### Access control
Public URL with a single user ⇒ anyone could otherwise read and *write* the study progress.
Minimal scheme: `PREP_TOKEN` env var; `POST /api/login` compares and sets a signed httpOnly
cookie; a dependency guards every other `/api/*` route. No user table, no OAuth.
`user_id` is a constant (`"me"`) so the schema is already multi-user-ready if that ever changes.

### TTS
`/api/tts` keeps edge-tts (the server-side neural voices exist because macOS Chrome drops
`speechSynthesis` with "canceled"). Cache moves from local disk to **Vercel Blob**, keyed by
`voice/md5(text)`; on miss, synthesize → upload → serve. Browser `speechSynthesis` stays as the
client-side fallback.

### Migration
`scripts/migrate_to_postgres.py`:
1. create schema (idempotent),
2. load `toefl/vocab/toefl_vocab.json`, `gre/vocab/gre_vocab.json`,
   `toefl/vocab/scene_vocab.json` → `words` (preserving array index as `ord`),
3. load `$PREP_DATA_DIR/srs/{toefl,gre,scenes}.json` + `*.flags.json` → `srs_cards`,
4. load `$PREP_DATA_DIR/notes/vocab_notes.json` → `notes`.

Real study history exists on scratch and must survive the move; the script is re-runnable
(upsert) so it can be repeated after more local studying.

### Verification
`scripts/score_vocab.py <deck> --url <deployed-url>` already drives the real frontend and the
read/write APIs (D6 live-checks, 15 pts). Pointing it at the Vercel URL validates the deployment
end-to-end without writing a new e2e suite. Local check first via `vercel dev` or uvicorn against
the same `DATABASE_URL`.

## Out of scope
Multi-user accounts, the other tools (writing/speaking/reading/mock), offline mode, and moving
the copyrighted real-question banks (they stay on scratch and are never deployed).

## Risks
- **Cluster → Neon egress**: login nodes may block outbound 5432. Fallback: run the migration
  from the laptop, or use Neon's HTTP SQL endpoint.
- **Free-tier limits**: Neon 0.5 GB is ample (~60 MB expected); Vercel Blob free tier covers the
  mp3 cache. Both are single-user traffic.
