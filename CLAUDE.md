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
- `enrich/ enrich_batches/ enrich_out/ rl_gen/ gen_banks/` — vocab-enrichment cache + Opus
  bulk-enrich batch I/O + AI-gen staging.
- `official-real/raw/` — user-uploaded real-material archives, EXTRACTED (TPO54-75, 机经,
  听/读/写/词/口语资料; PDFs + MP3 audio; 2nd wave 2026-07-10: 新东方/Koolearn 全科课程讲义,
  核桃英语, 思维导图 PNG, 语法课 PPT). `official-real/tpo_txt/<TPO>/` — TPO PDFs/DOCX converted
  to text (reading_q/reading_a/listening_q/listening_transcript/listening_a…) for Opus parsing
  into `official-real/reading|listening/tpo_*.json` (source:"real"). User uploads more archives
  to `official-real/`; unzip (`unzip -O GBK`) / unrar (`unar`), then delete the archive.
- `official-real/tpo_txt/_materials/<group>/` — ALL 2nd-wave course files dumped to text
  (182 files; .ppt read via olefile TextAtom parse). **`_materials/_survey_full.json` = 15-agent
  Opus survey of every file** (contents + extractable data + top picks) — consult it before any
  extraction. Biggest finds: TPO21-35 complete KEYED reading bank (~45 passages/~600 Q);
  TPO40-54 listening transcripts; 88 TPO + 27 dated-2018 + 110 with-answer real speaking prompts;
  48 complete Task-5 conv+prompt items; TPO1-34 Task3/4/6 gold outline keys; 17 official
  integrated-writing sets (reading+lecture); ETS 2015 sampler (keyed R/L + scored essays).
  `tpo_txt/_vocab/` — vocab-source dumps (TPO高频词, 场景词汇, 词组句型).

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
ECDICT-backed decks `toefl/vocab` (10358) + `gre/vocab` (10526) + `toefl/vocab/scene_vocab`
(scenes, 1536 topical words/phrases from uploaded real material), each word tagged `tier`
(1 high-freq → 2 rare → 3 simple) via `scripts/order_vocab.py`. TOEFL deck: 2235 words carry
`tpo_hf: true` (attested in the uploaded TPO高频词 real-exam list; includes 431 added words) and
study FIRST within each tier (`scripts/tpo_hf_vocab.py` re-sorts (tier, ¬tpo_hf, freq)). UI badges
🔥TPO高频 + topic. Tier1+2 100% Opus-enriched. vocab-srs: new-card cap default UNLIMITED;
Enter=graduate-forever, Space→reveal→1/2/3 (Again/Hard/Good), ←undo/→redo.

vocab-srs UI extras (2026-07-10):
- **Again spacing guard**: any graded word waits ≥15 other cards before reappearing
  (`RECENT_GAP` in vocab-srs/app.py, in-memory buffer).
- **US/UK IPA** (`ipa_us`/`ipa_uk` in decks; merged by `scripts/add_ipa.py` from
  `$LANG_PREP_CACHE/ipa-dict/` — open-dict-data, ~96% coverage) + **4 TTS voices**
  (US/UK × ♂/♀). Auto-plays US ♂ on every card switch/undo; per-slot voice overrides + auto
  toggle in the 🔊⚙ header menu (localStorage). Per-POS row also shows IPA + US-♂ button.
  TTS engine (2026-07-11): default = **server-side edge-tts neural voices** (`/api/tts`,
  Andrew/Aria/Ryan/Sonia, free MS endpoint, mp3 cached in `$LANG_PREP_CACHE/tts/` ~9KB/word,
  worst case ~0.5GB scratch); browser speechSynthesis is the fallback only — macOS Chrome
  randomly drops it with "canceled" (known Chromium bug), which is why the server engine exists.
- **词根词缀·词源**: optional `etymology` {breakdown, story, origin} per word, shown as a
  collapsed 🌱 block above the primary definition. Generated by `scripts/enrich_etym.py`
  (free-LLM, per-word cache `$LANG_PREP_CACHE/enrich_etym/`, resumable; useful=false cached →
  no block). Wired into `enrich_cron.sh` as a second nightly pass after the main enrichment.
- **Personal notes**: collapsed 📝 markdown box on the reveal page (GPT-paste friendly);
  autosaves to `$PREP_DATA_DIR/notes/vocab_notes.json`, keyed by term, shared across decks.
  Rendered by vendored marked.js + DOMPurify in `tools/vocab-srs/static/vendor/` (in git, ~60KB).
- **词汇检索**: collapsed 🔎 in-deck substring search (`/api/search`) → click a hit to open the
  word as a full study page (`/api/entry`); grading it uses the normal /api/review so it counts
  toward today. **⬅ 返回检索前** is a true back-stack (client-side), distinct from ← undo.

## Scheduled jobs (scrontab; `scrontab -l`)
- vocab enrich 02:00 (drjieliu99) + 04:00 (nmasoud) — `scripts/enrich_cron.sh`. This is the
  ONLY scheduled generation: ~20k words is genuinely huge + quota-bound, so a daily drip fits.
- (pre-existing `glcfs_fetch` 7:30 engin1 — NOT ours, preserve it)
- **R/L question generation is NOT scheduled** (removed 2026-07-10): it's deterministic, so it's
  run in ONE Opus batch on demand (`scripts/gen_bank.py` / subagents), sweeping all 44 domains at
  once — the 2-week exam timeline can't wait for a daily rotation. Do the bulk sweep AFTER the
  user uploads TPO (dedupe/fill gaps against real coverage). Principle: anything determinable now
  is done now with Opus, not dripped by a free model on a timer.
NODE POLICY: heavy/long jobs on owned accounts (nmasoud/drjieliu99); engin1 short jobs only.

## Conventions
- Commits: author `aevum-orrin`, `Co-Authored-By: Claude`, noreply email. Push when "差不多了".
- Docs/READMEs English; chat mixed zh-en.
- Free LLMs (Gemini/Groq) for runtime + scheduled gen; Opus (this session) pre-generates
  best-quality banks. `.env` NOT exported (keeps Claude Code on the Max subscription).

_Last updated: 2026-07-10 (v3: vocab-srs pronunciation/IPA, etymology, notes, in-deck search)._
