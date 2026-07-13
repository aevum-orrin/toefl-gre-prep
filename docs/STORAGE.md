# Storage layout

The home repo must stay small (**target < 2 GB**, it's on `$HOME`). Only **code + small
AI-practice question banks** live in git. Everything heavy, private, or growing lives on
**scratch** (Neda's owned space) and is **never** committed.

## Where things live

| What | Location | In git? |
|------|----------|---------|
| App code, prep-core, scripts | `~/toefl-gre-prep/` (home) | ✅ yes |
| AI-practice question banks (small JSON) | `toefl/…`, `gre/…` | ✅ yes |
| Vocab decks (ECDICT-derived JSON) | `toefl/vocab`, `gre/vocab` | ✅ yes |
| **Real questions** (ETS official, TPO) + PDFs + listening audio | `$REAL_DATA_ROOT` (scratch) | ❌ no |
| **User records** — SRS progress, recordings, essays, practice logs | `$PREP_DATA_DIR` (scratch) | ❌ no |
| Vocab enrichment cache, AI-gen staging, raw ECDICT | `$LANG_PREP_CACHE/{enrich,enrich_etym,rl_gen,gen_banks,raw}` (scratch) | ❌ no |
| IPA source dictionaries (open-dict-data/ipa-dict, US+UK) | `$LANG_PREP_CACHE/ipa-dict/` (scratch) | ❌ no |

## The scratch root

```
$LANG_PREP_CACHE = /scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache
├── enrich/            # per-word vocab enrichment cache (resumable)
├── enrich_etym/       # per-word 词根词缀/词源 (etymology) cache (resumable)
├── ipa-dict/          # en_US.txt + en_UK.txt IPA source (scripts/add_ipa.py merges into decks)
├── tts/<voice>/       # pronunciation mp3 cache (edge-tts neural voices, ~9 KB/word, on demand;
│                      #   worst case ≈0.5 GB if every word × all 4 voices — realistically ~150 MB)
├── rl_gen/            # AI-generated R/L items staged before merge
├── gen_banks/         # AI-generated speaking/writing items staged before merge
├── official-real/     # $REAL_DATA_ROOT — REAL questions (copyright: local only, never pushed)
│   ├── reading/  listening/  speaking/  writing/   # extracted items (source:"real")
│   ├── pdf/           # source ETS PDFs
│   └── tpo/           # drop TPO downloads here (any format); a parser folds them in
└── user-data/         # $PREP_DATA_DIR — everything the user produces
    ├── srs/           # SM-2 scheduling state per deck (toefl.json, gre.json, *.intro.json)
    ├── notes/         # vocab_notes.json — personal per-word markdown notes (all decks share it)
    ├── recordings/    # speaking recordings (webm/mp3) — can get large
    ├── progress.jsonl # cross-tool practice log
    └── essays/        # (future) saved essays + feedback
```

## ⚠️ Scratch auto-purge (and our protection)

Great Lakes **/scratch deletes any file not *accessed* for 60 days** (rolling, per-file —
not a fixed calendar sweep; the clock resets every time a file is actually read/written).
This applies to owned roots (`nmasoud_owned_root`) too, and artificially `touch`-ing files
to dodge the purge is an explicit policy violation (escalating penalties).

Consequences for this repo, by data class:

- **Re-generable caches — fine to lose**: `tts/` (re-synthesized on demand), `enrich/` +
  `enrich_etym/` (results already merged into the deck JSONs in git; cache only exists for
  resume), `ipa-dict/` (already merged; re-downloadable), `rl_gen/ gen_banks/ build/`.
- **Irreplaceable — protected by scheduled backup**: the `prep_backup` scrontab job (every
  10 days; also runnable by hand: `./scripts/backup_scratch.sh`) mirrors (rsync, no
  --delete so a purge never propagates) into home `data/backup/` (gitignored):
  - `user-data/` → `data/backup/user-data/` (SRS progress, notes, recordings, logs; ~MBs)
  - `official-real/` minus `raw/` → `data/backup/official-real-lite/` (~100 MB: parsed real
    questions, tpo_txt, source PDFs)
- **`official-real/raw/` (2.5 GB extracted archives) is NOT backed up** — too big for home;
  keep the original downloads on your laptop. If a stretch of >60 days without touching them
  is expected, re-upload or ask for a Turbo/other plan.

During active daily study everything hot is being accessed anyway; the real risk window is
a multi-week pause (e.g. after TOEFL, before resuming GRE).

## How it's wired

`env.sh` exports three vars (with sane defaults); every app reads them and falls back to
`home/data` only if unset (quick dev):

- `LANG_PREP_CACHE` — the scratch root. **Change this one var to relocate everything.**
- `REAL_DATA_ROOT` — real questions (`$LANG_PREP_CACHE/official-real`).
- `PREP_DATA_DIR` — user records (`$LANG_PREP_CACHE/user-data`).

Apps serve **real + AI items together**; each item carries `source` (`"real"` 真题 |
`"ai"` AI 练习题) which the UI badges. Real items load first so they surface early.

## Question provenance (labeling rule)

- Official ETS practice tests **and** TPO → treated as **真题** (`source:"real"`).
- Everything the app generates → **AI 练习题** (`source:"ai"`).

Real ETS/TPO content is ETS-copyrighted: kept on scratch for **personal study only**, never
pushed to the public repo. AI items imitate the real format/length/word-count and are
generated to cover **all TOEFL domains** (STEM, humanities, history, …) that the small real
set can't span.
