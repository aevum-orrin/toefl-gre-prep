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
| Vocab enrichment cache, AI-gen staging, raw ECDICT | `$LANG_PREP_CACHE/{enrich,rl_gen,gen_banks,raw}` (scratch) | ❌ no |

## The scratch root

```
$LANG_PREP_CACHE = /scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache
├── enrich/            # per-word vocab enrichment cache (resumable)
├── rl_gen/            # AI-generated R/L items staged before merge
├── gen_banks/         # AI-generated speaking/writing items staged before merge
├── official-real/     # $REAL_DATA_ROOT — REAL questions (copyright: local only, never pushed)
│   ├── reading/  listening/  speaking/  writing/   # extracted items (source:"real")
│   ├── pdf/           # source ETS PDFs
│   └── tpo/           # drop TPO downloads here (any format); a parser folds them in
└── user-data/         # $PREP_DATA_DIR — everything the user produces
    ├── srs/           # SM-2 scheduling state per deck (toefl.json, gre.json, *.intro.json)
    ├── recordings/    # speaking recordings (webm/mp3) — can get large
    ├── progress.jsonl # cross-tool practice log
    └── essays/        # (future) saved essays + feedback
```

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
