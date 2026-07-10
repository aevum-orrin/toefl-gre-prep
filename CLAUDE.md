# CLAUDE.md — toefl-gre-prep (project memory)

Project-specific guidance for Claude Code in this folder. The global
`~/.claude/CLAUDE.md` (attribution, language, HPC, storage rules) still applies; this file
**adds** project specifics and — most importantly — **records where files live**, so a fresh
session immediately knows the layout. **Keep this file updated** as things change.

## What this is
Personal **TOEFL (2-week sprint) + GRE** prep monorepo. FastAPI + static-HTML tools over a
shared `prep-core`. Target = **2026-01 new TOEFL** format. Focus: speaking + writing.

## ⚠️ Storage — where everything lives (READ THIS FIRST)
Home repo must stay **< 2 GB**. Only **code + small AI question-bank/vocab JSON** are in git.
Everything heavy, private, or growing lives on **scratch (Neda's owned space)** and is
**never committed**. Full detail: [docs/STORAGE.md](docs/STORAGE.md).

**Scratch root** — `$LANG_PREP_CACHE` = `/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache`:
- `official-real/` = `$REAL_DATA_ROOT` — **REAL questions** (official ETS + future TPO), PDFs,
  future listening audio. Copyright: local only, never pushed. Subdirs: `reading/ listening/
  speaking/ writing/ pdf/ tpo/`. **User drops TPO downloads into `official-real/tpo/`.**
- `user-data/` = `$PREP_DATA_DIR` — ALL user records: `srs/` (SM-2 progress), `recordings/`,
  `progress.jsonl`, future `essays/`.
- `enrich/ rl_gen/ gen_banks/` — vocab-enrichment cache + AI-gen staging.

`env.sh` exports `LANG_PREP_CACHE`, `REAL_DATA_ROOT`, `PREP_DATA_DIR`; apps read them (fall
back to `home/data/` only if unset). **Change `LANG_PREP_CACHE` once to relocate everything.**
Home `data/` is gitignored; it should end up nearly empty (records now live on scratch).

## Question provenance (labeling rule the user set)
Every question item carries `source`: **`"real"`** (真题 = official ETS + TPO) or **`"ai"`**
(AI 练习题). Apps load real first, mix with AI, and the UI badges each (🟢 真题 / 🔵 AI 练习题).
Real items are AI-generated bulk's ground truth: AI questions must **imitate the real
format/length/word-count** AND **cover all TOEFL domains** (STEM, humanities, history, …) that
the tiny real set can't span.

## Tools (ports) — `./run.sh <name>`
writing (8001) · speaking (8002, needs mic → run on laptop) · vocab (8003) · reading (8004) ·
mock (8005). `./run.sh` with no arg prints the menu.

## Vocab specifics
ECDICT-backed decks `toefl/vocab` (9927) + `gre/vocab` (10526), each word tagged `tier`
(1 high-freq → 2 rare → 3 simple) via `scripts/order_vocab.py`. vocab-srs: new-card cap
default UNLIMITED; Enter=graduate-forever, Space→reveal→1/2/3 (Again/Hard/Good), ←undo/→redo.

## Scheduled jobs (scrontab; `scrontab -l`)
- vocab enrich 02:00 (drjieliu99) + 04:00 (nmasoud) — `scripts/enrich_cron.sh`
- R/L gen: reading 10:00 + listening 18:00 (engin1) — `scripts/gen_cron.sh <section>`
- (pre-existing `glcfs_fetch` 7:30 engin1 — NOT ours, preserve it)
NODE POLICY: heavy/long jobs on owned accounts (nmasoud/drjieliu99); engin1 short jobs only.

## Conventions
- Commits: author `aevum-orrin`, `Co-Authored-By: Claude`, noreply email. Push when "差不多了".
- Docs/READMEs English; chat mixed zh-en.
- Free LLMs (Gemini/Groq) for runtime + scheduled gen; Opus (this session) pre-generates
  best-quality banks. `.env` NOT exported (keeps Claude Code on the Max subscription).

_Last updated: 2026-07-10._
