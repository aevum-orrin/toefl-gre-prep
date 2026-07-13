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
Home `data/` is gitignored; it holds only `data/backup/` (see below).

⚠️ **Scratch auto-purge**: /scratch deletes files not ACCESSED for 60 days (rolling per-file;
owned roots included; touch-evasion prohibited). Caches (tts/enrich/ipa-dict) are re-generable
= fine; the irreplaceable bits (user-data; official-real minus raw/) are mirrored into home
`data/backup/` by **`./scripts/backup_scratch.sh`** — a MANUAL one-shot (no cron any more);
run it every few weeks. `official-real/raw/` (2.5 GB) is NOT backed up — the user keeps the
original archives on the laptop. Details: docs/STORAGE.md.

## Question provenance (labeling rule the user set)
Every question item carries `source`: **`"real"`** (真题 = official ETS + TPO) or **`"ai"`**
(AI 练习题). Apps load real first, mix with AI, and the UI badges each (🟢 真题 / 🔵 AI 练习题).
Real items are AI-generated bulk's ground truth: AI questions must **imitate the real
format/length/word-count** AND **cover all TOEFL domains** (STEM, humanities, history, …) that
the tiny real set can't span.

## Tools (ports) — `./run.sh <name> [PORT]`
writing (8001) · speaking (8002, needs mic → run on laptop) · vocab (8003) · reading (8004) ·
mock (8005). `./run.sh` with no arg prints the menu. Optional 2nd arg overrides the port.

⚠️ **"页面一直转/打不开" is almost never the server** (2026-07-13 incident). Login nodes are
SHARED and the laptop reaches them through a VS Code / SSH port-forward, so check in this order:
1. On the cluster: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8003/` → 200 means
   the app is fine; `ss -tnp | grep '127.0.0.1:8003'` with NO established connection means the
   browser's requests never even arrive → it's the forward, not the code.
2. The laptop's `localhost:8003` may still be forwarded by an OLDER VS Code window / ssh -L to a
   DIFFERENT login node (sessions land on gl-login1…5 at random). Fix: re-forward in VS Code's
   PORTS panel, close the stale window, or just `./run.sh vocab 8013` (fresh port → fresh forward).
3. Other users' processes can own a port on a login node (`ss -ltn` shows it with no owner) —
   run.sh now refuses to start on a busy port instead of dying with "address already in use".
4. Frontend served with `Cache-Control: no-cache` (all apps), so a stale cached page is no longer
   a possible cause; if the card is stuck on "…" the script threw — see the test below.

## Vocab specifics
ECDICT-backed decks `toefl/vocab` (10358 words / 14880 POS senses) + `gre/vocab` (10526) +
`toefl/vocab/scene_vocab` (scenes, 1536 topical words/phrases), each word tagged `tier`
(1 high-freq / 2 rare / 3 simple) by `scripts/order_vocab.py`.
- **TOEFL deck is COMPLETE (2026-07-11)**: every word has gloss_en; every POS sense has an
  example + collocations; no untagged senses. Pipeline: `fix_pos.py` (recovers POS from
  ECDICT's WordNet-style bare tags — this alone fixed 5214 words that showed a "—" row) →
  `make_pos_batches.py` + `pos_workflow.js` (Opus: adds POS a learner's dictionary lists but
  ECDICT lacked, e.g. `elite` adjective; fills example-less senses) → `fold_pos.py`.
- **Study order** (`order_vocab.py`, user's call): tier1+tier2 are SHUFFLED into one mixed
  block (seeded, stable across rebuilds) — no more "all high-freq, then all rare"; TPO-attested
  words (`tpo_hf`, 2235 of them via `tpo_hf_vocab.py`) come first inside it; tier-3 basics last.
- vocab-srs keys: `Space` reveal · `1/2/3` grade · **`4` = 朗读（美式男声 Andrew，任何单词页面都能按，
  正面/背面/检索跳转页都行；笔记框内打字不触发）** · `Enter` know-it · `←`/`→` undo/redo · `/` 检索.
- vocab-srs: new-card cap UNLIMITED; Space→reveal→1/2/3 (Again/Hard/Good); Enter (pre-reveal)
  = graduate-forever, **BUT refused for any word ever graded "Again"** (kept as a Good review
  instead; flag persists in `$PREP_DATA_DIR/srs/<deck>.flags.json`, UI shows 🔁 + a toast).
  ←/→ undo/redo the LAST ACTION (reveal counts): Space,1,← lands back on the answer screen so
  you can press 2 instead. Notes box = live split (Markdown left, preview right, auto-growing).
- **Scheduling algorithm (user-specified, 2026-07-12)** — SM-2 backbone + proficiency:
  - Every card carries `prof` 0..1 (reward-EMA over the WHOLE grade history: again/hard=0,
    good=0.8, enter=1.0, α=0.4; the user's "RL reward" idea). `prof` scales SM-2 interval
    growth ×(0.5+prof); failing also drops ease by 0.2. Shown as 熟练度% in the reveal meta.
  - Enter semantics: first sight → gone forever; on a SEEN word (never Again'd) → strong pass
    + flag `enter`, word returns ONCE for confirmation, second consecutive Enter → gone
    (any 1/2/3 in between resets the streak); ever-Again'd → refused forever (sticky-Again).
  - /api/next priority: today's Again-lapses past the 15-card gap → NEW words (never-seen
    strictly before seen, user's call) → ordinary due reviews. NOTE: with new/day=∞ the
    day-level reviews only surface after the new pool is exhausted — use a finite new/day
    (e.g. 300) to interleave daily reviews.
  - Flow tests: scratchpad test_flow.py pattern (7 cases) + prep-core/tests/test_srs.py.

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
  no block). Run on demand: `python scripts/enrich_etym.py <deck>` (630 words cached so far).
- **Personal notes**: collapsed 📝 markdown box on the reveal page (GPT-paste friendly);
  autosaves to `$PREP_DATA_DIR/notes/vocab_notes.json`, keyed by term, shared across decks.
  Rendered by vendored marked.js + DOMPurify in `tools/vocab-srs/static/vendor/` (in git, ~60KB).
- **词汇检索** (2026-07-13: now GLOBAL): a floating widget like the timer, present on EVERY
  screen — front side before Space, reveal page, even the "nothing due" screen. Open with the
  bottom-left button / `/` / `Ctrl+K`; ↑↓ select, Enter open, Esc close. In-deck substring match
  (`/api/search`) → click a hit → full study page (`/api/entry`); grading uses the normal
  /api/review so it counts toward today. **⬅ 返回检索前** = client-side back-STACK: N chained
  lookups → N presses to walk home, each restoring that screen exactly (revealed or not);
  depth shown on the button. Distinct from ← undo (which reverts grades).
  E2E test: scratchpad test_lookup.mjs drives the real frontend JS (node vm + stub DOM) against
  a live backend — 18 assertions over the chain/back/no-op-self-jump paths.

## Scheduled jobs (scrontab) — only these two; ask before adding more (user rule 2026-07-11)
`scrontab -l` holds the user's pre-existing `glcfs_fetch` (7:30, engin1 — **do not touch**)
and `prep_backup` (03:00 on days 1/11/21/31 ≈ every 10 days, engin1, **user-approved
2026-07-13**): runs `./scripts/backup_scratch.sh` = REAL rsync of user-data + official-real
(minus raw/) into home `data/backup/`. It can also be run by hand any time.
Vocab-enrichment crons were deleted 2026-07-11 (deterministic work → one Opus pass on demand).
- ⚠️ NEVER add atime-refresh / read-sweep / touch jobs to dodge the 60-day scratch purge —
  explicit ARC policy violation (escalating penalties). Real backups only.
- One-shot backups of the OTHER scratch projects' irreplaceable data (music-in, uploads,
  MaterialsMatters, gf data, genomes; ~1GB) live in `~/scratch-backup/` (see its README).
- NODE POLICY (if a job ever is needed): heavy/long on owned accounts (nmasoud/drjieliu99);
  engin1 short jobs only.

## ⚠️ Token-window rule (user-set, 2026-07-11)
**Whenever the rolling 5-hour token window reaches ~90% used, STOP generating immediately**:
pause the work, save progress (update this file + auto-memory RESUME state), and `git commit`.
Resume when the window refreshes — same Effort, continue where left off.

## Real-question extraction state (2026-07-11)
Real banks live on scratch `official-real/` and auto-load into the apps (🟢真题 badge):
- **Reading: 97 real items / 976 Q** — TPO21-35 complete (45 passages, keyed, from 新东方
  bank), TPO58-74 (wave-1 + spec retries), ETS 2015 sampler. All content-filter blocks
  solved via `scripts/assemble_spec.py` line-range specs (agent never outputs passage text).
- **Listening: 223 real items / 878 Q** — TPO58-74 (12 TPOs: 57 items/262 Q, official keys),
  TPO40-54 real transcripts × AI-generated questions (90 items/510 Q, title-tagged
  「AI配题·原文真题」, `tpo40_54_with_aiq.json`), 2026 official tests, 题型 drills (28),
  ETS sampler. Raw keyless transcripts stay in `transcripts_tpo*.json` (loader ignores).
- **Writing: discussion.json = 113 real-prompt items** (111 real past prompts + AI-generated
  student posts, `note` marks the hybrid; posts format = [{name,text}]). Plus on scratch:
  `model_essays.json` (7), `ets_scored_samples.json` (4 ETS-scored essays for grader
  calibration), raw prompt files `real_prompts_{xdf,lisheng}.json`.
- **Speaking: interview.json = 75 real topics / ~372 real prompts** (172 folded by
  `scripts/fold_speaking_prompts.py` from 核桃50/60题 + 88 TPO + 27 dated-2018; answers[]
  carries model answers/outlines). Raw files `real_independent_prompts_{a,b}.json`.
- Apps' loaders keep only single-answer MC (int answer; "Select TWO" list-answers dropped).
- Speaking/writing REFERENCE data on scratch (not app-loaded yet): `speaking/task5_conversations_{1,2}.json`
  (34 real conv+ETS-prompt items), `speaking/task3_gold_outlines.json` (34) +
  `task46_gold_outlines.json` (68) — gold outlines for AI-grader few-shots;
  `writing/integrated_sets_{a1,a2,b1,b2}.json` (17 full reading+lecture sets).
- STILL PENDING: AI question-gen over the 90 keyless TPO40-54 transcripts; TPO45/46 stems
  (no keys); 阅读题型专项 81 Q (keys only recoverable for TPO21-35 overlap); TPO54/55/56/57/
  67/75 listening (missing q or a text); wiring ~690 real MP3s into listening playback;
  GRE vocab enrichment.

## Conventions
- Commits: author `aevum-orrin`, `Co-Authored-By: Claude`, noreply email. Push when "差不多了".
- Docs/READMEs English; chat mixed zh-en.
- Free LLMs (Gemini/Groq) for runtime + scheduled gen; Opus (this session) pre-generates
  best-quality banks. `.env` NOT exported (keeps Claude Code on the Max subscription).

_Last updated: 2026-07-11 (v6: TOEFL vocab complete — POS recovery + expansion, mixed study order, action-level undo, Again-sticky Enter, split notes editor; all cron jobs removed)._
