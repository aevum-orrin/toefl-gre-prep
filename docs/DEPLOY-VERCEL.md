# Deploying the vocab tool to Vercel

The vocab study tool as a public website, so it works from a phone and a laptop without SSH
port-forwarding. Progress syncs through a hosted Postgres database, because Vercel functions
have **no persistent disk** — anything written to a file there is lost.

The local tool (`./run.sh vocab`) is untouched and keeps working.

Nothing here assumes web-infra knowledge. Follow it top to bottom.

---

## Vocabulary (what these services are)

| Thing | What it actually is |
|---|---|
| **Vercel** | Hosting. It takes the repo, runs the Python API as on-demand functions, and serves the page from a CDN. |
| **Neon / Supabase** | Two interchangeable providers of a hosted **Postgres** database. Postgres is ordinary SQL storage; both run it in the cloud, free at this size. The app talks plain `psycopg` to a `DATABASE_URL`, so **either works with no code change**. |
| **Connection string** | The database's address *and password* in one line: `postgresql://user:pass@host/db?sslmode=require`. Treat it like a password. |
| **Connection pooler** | A front-end to the database that multiplexes many short connections onto a few real ones. **Required here** — see the warning in Step 1. |
| **Environment variable** | A named value handed to the app at runtime (e.g. `DATABASE_URL`). Set in the Vercel dashboard, never committed. |
| **Vercel Blob** | File storage on Vercel, used here to cache pronunciation mp3s. Optional. |

---

## Step 1 — create the database (Neon **or** Supabase — pick one)

Both are hosted Postgres and the app cannot tell them apart. The practical difference:

| | Neon | Supabase |
|---|---|---|
| When idle | compute suspends after ~5 min, **auto-resumes** on the next request | free projects **pause after ~7 days** and need a manual restore in the dashboard |
| Free tier | 0.5 GB | 500 MB database + 1 GB file storage |
| Extra | database branching; one-click from the Vercel marketplace | bundled Storage, which can replace Vercel Blob for the TTS mp3s |

Neon is the lower-maintenance default (come back after a holiday and it just works). Choose
Supabase if you already use it, or want one provider for both database and audio files.

> ⚠️ **Copy the POOLED connection string, not the direct one.** Each request opens its own
> short-lived connection — correct for serverless, but pointed at a *direct* endpoint enough
> concurrent requests will exhaust the connection limit and start erroring.
> **Supabase:** in *Connect*, choose **Transaction pooler** (port `6543`), not Direct (5432).
> **Neon:** use the host containing `-pooler`.

### Neon
1. <https://neon.tech> → **Sign up with GitHub** (the `jackiectl` account).
2. **Create a project** named `vocab-srs`, region closest to you (`US East (Ohio)` is fine).
3. Copy the pooled connection string:
   ```
   postgresql://neondb_owner:AbC123xyz@ep-cool-name-12345678-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### Supabase
1. <https://supabase.com> → **Sign up with GitHub**.
2. **New project** named `vocab-srs`; set a database password when asked and keep it.
3. **Connect → Transaction pooler**, copy the string and substitute that password:
   ```
   postgresql://postgres.abcdefghijkl:<password>@aws-0-us-east-2.pooler.supabase.com:6543/postgres
   ```
4. If the migration in Step 3 cannot reach it from the cluster, Supabase's **SQL Editor** in the
   dashboard is a usable fallback for creating the schema.

## Step 2 — hand the connection string to the migration (on the cluster)

Do **not** paste it into a chat or a commit. Write it to the gitignored file the tooling reads:

```bash
cd /home/ctlang/toefl-gre-prep
umask 077
echo 'DATABASE_URL=<paste the whole connection string here>' > .env.vercel.local
```

`.env*` is already in `.gitignore`, so this file can never be committed.

## Step 3 — create the tables and load the data

```bash
cd /home/ctlang/toefl-gre-prep
source env.sh
.venv/bin/python scripts/migrate_to_postgres.py
```

This creates the schema, loads all three decks (~22k words) and — importantly — **your existing
study progress** from `$PREP_DATA_DIR/srs/*.json`, plus notes. It is re-runnable: run it again
any time you have studied more locally and want the website to catch up.

Expected tail:
```
  words           22420 rows
  srs_cards       22420 rows
  notes               N rows
  intro_counts        N rows
done.
```

> If it hangs or times out, the cluster may block outbound Postgres (port 5432). Run the same
> command from a laptop that has the repo checked out, or use Neon's SQL editor in the browser.

## Step 4 — pick a passphrase

The site is a public URL, so it is protected by one shared passphrase. Choose any string; you
will type it once per device.

## Step 5 — deploy on Vercel

1. Go to <https://vercel.com> → **Sign up with GitHub**.
2. **Add New… → Project**, then import `jackiectl/toefl-gre-prep`.
3. **Important — set the branch**: under *Settings → Git → Production Branch*, use
   `test-vocab-web` (or merge that branch to `main` first).
4. Framework preset: **Other**. Leave the build/output settings empty — `vercel.json` covers it.
5. Before clicking Deploy, open **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string from Step 1 |
   | `PREP_TOKEN` | the passphrase from Step 4 |

6. Click **Deploy**. First build takes ~1–2 minutes.

### Optional — pronunciation cache
In the Vercel dashboard: **Storage → Create → Blob**, attach it to the project. Vercel injects
`BLOB_READ_WRITE_TOKEN` automatically. Without it pronunciation still works; it just re-synthesizes
each time instead of caching.

## Step 6 — check it

Open the deployment URL. You should get the login page, then the study card after entering the
passphrase.

Then verify from the cluster with the existing scorer, which drives the real APIs and frontend:

```bash
cd /home/ctlang/toefl-gre-prep && source env.sh
.venv/bin/python scripts/score_vocab.py gre --url https://<your-app>.vercel.app
```

---

## Keeping local and web in sync

They are separate stores. The website is authoritative once you start using it; to push newer
local study progress up, re-run Step 3. There is no automatic sync back down to the cluster —
see the open issue on backing Postgres up to scratch.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `500` on every API call | `DATABASE_URL` missing or wrong in Vercel's env vars |
| Works alone, errors when several tabs/devices hit it | direct (non-pooled) connection string — use the pooler endpoint from Step 1 |
| Worked, then "project paused" | Supabase free tier paused after ~7 days idle; restore it in the dashboard |
| Login always rejects | `PREP_TOKEN` not set, or set with surrounding quotes |
| Login loops back | Cookies blocked, or the site opened over plain `http` (the cookie is `secure`) |
| Build fails on `faster-whisper` | The root `requirements.txt` leaked into the build; `.vercelignore` must exclude it so `api/requirements.txt` is used |
| Cards load but pronunciation 502s | edge-tts could not reach Microsoft's endpoint; the browser falls back to `speechSynthesis` |
