# Vocab-completeness Loop — runbook for an autonomous session

Point a fresh Claude Code session at this file. Goal: iterate until the TOEFL vocab deck +
the vocab-srs app score **≥ 95 / 100** on `scripts/score_vocab.py`, or **10 iterations**,
whichever first. The score is the referee — it is machine-computed from the data + a live
server, never a vibe. **Read the project `CLAUDE.md` first** (storage layout, token-window
rule, commit identity, node policy). This runbook only adds the loop specifics.

## The one loop

```
for iteration in 1..10:
  1. SCORE   — run the scorer (command below) → note TOTAL and every dimension's gap
  2. FIX-ALL — in the SAME iteration, raise EVERY deficient dimension at once (run all the
               relevant fixers below — D1 ipa, D2 def_en/examples/colloc, D3 词源, …),
               regenerating data only. NOT "only the lowest dimension this round".
  3. VERIFY  — re-run the scorer; spot-check 3-5 words in a real browser (Playwright MCP)
  4. COMMIT  — git commit the iteration (data + any code), note old→new score
  if TOTAL >= 95: stop
```

**Loop shape (global rule, ~/.claude/CLAUDE.md):** every iteration does the SAME thing — a full
sweep that pushes ALL dimensions up together, then re-scores. Do NOT fix only the lowest dimension
one round and the next-lowest the next; that is wrong. Fine-grained fractional scores are the meter.
Announce each iteration in chat (one line: score delta). Commit after every iteration so any
regression is one `git revert` away.

## Run environment (matters — get this wrong and you waste hours)

- **Run on a LOGIN node** (`gl-login1..5`), NOT a compute node. Compute nodes (e.g. `gl1511`)
  have restricted outbound internet, so **edge-tts (server TTS) 502s** and **free-LLM enrichment
  can't reach Gemini/Groq**. On a compute node the TTS-live item and any API-based fixer silently
  score 0. Check with: `hostname -s` (want `gl-login*`).
- **`source env.sh`** first (exports `LANG_PREP_CACHE`, `PREP_DATA_DIR`, `REAL_DATA_ROOT`).
- **Scoring/testing uses a THROWAWAY server**, never the real 8003 you study on — `--allow-write`
  and `--e2e` grade words. Always start the scoring server on a temp `PREP_DATA_DIR`:

```bash
source env.sh
export SCRATCHPREP=$(mktemp -d /tmp/vocab-score-XXXX)
NODE=$(ls -d ~/.vscode-server/cli/servers/Stable-*/server/node | head -1)
# throwaway server on 8096 (idle-shutdown off so it survives the score)
( cd tools/vocab-srs && PREP_DATA_DIR=$SCRATCHPREP PREP_IDLE_MIN=0 \
    setsid nohup ../../.venv/bin/uvicorn app:app --port 8096 >/tmp/score-srv.log 2>&1 </dev/null & )
sleep 9
.venv/bin/python scripts/score_vocab.py toefl --url http://127.0.0.1:8096 --allow-write --e2e --node "$NODE"
# stop it when done:
kill $(ss -ltnp | grep ':8096 ' | grep -o 'pid=[0-9]*' | cut -d= -f2) 2>/dev/null
```

The scorer writes `data/vocab_score_toefl.json` (per-item breakdown) and prints a table.

## Rubric (100 pts) — source of truth is `scripts/score_vocab.py`

| Dim | Pts | Items |
|---|---|---|
| **D1 发音** | 18 | ipa_us 7 · ipa_uk 5 · any-phonetic 2 · tts-live 4 |
| **D2 释义与例句** | 30 | gloss_en 5 · sense.pos 4 · def_en 5 · def_zh 4 · example 5 · colloc≥2 3 · synonyms 2 · antonyms 2 (syn/ant = filled/WordNet-available, `add_syn_ant.py`) |
| **D3 词根词缀词源** | 17 | resolved (has `etymology` OR cached `useful:false`) 14 · 3-field fullness 3 |
| **D4 结构一致性** | 10 | schema 3 · no-dup 2 · no empty-shell sense 3 · no mojibake 2 |
| **D5 学习元数据** | 10 | tier 3 · tpo_hf≥1500 2 · verb exchange 3 · freq\|bnc 2 |
| **D6 App 功能 (live)** | 15 | read APIs 4 · write+undo 2 · frontend e2e 6 · latency 3 |

If you think a dimension is worth measuring that isn't here (e.g. audio for real MP3s, synonym
sets, example-sentence quality via an LLM judge), **add an item to `score_vocab.py`** — but keep
every check machine-verifiable and deterministic, and say in the commit why you added it.

## Baseline (2026-07-19): **85/100** → **REACHED 99.6/100 in iteration 1** (login node)
TOEFL deck completeness loop is **DONE** (target ≥95). Verified end-to-end on `gl-login4`.
The whole 85→99.6 climb came from filling the completeness facets in one comprehensive sweep
(user-directed loop shape: each iteration补全所有缺项 + score/debug, not one-dimension-per-round):
- **D3 词源 3.7 → 17.0/17** (the whole gap): 10351/10358 resolved (7046 etymology + 3305
  judged-not-useful). Reformatted kaikki `etymology_text` → Chinese `{breakdown,story,origin}`
  via an **Opus/Sonnet Workflow fan-out** (`scripts/etym_workflow.js`, 327 batches of ~30 words),
  **no external/free LLM**. Pipeline: `make_etym_batches.py` (priority-ordered pending) →
  fan-out writes per-batch out-files on scratch → `fold_etym_out.py fold` (distributes to per-term
  cache + applies cache→deck DIRECTLY; NEVER via `enrich_etym.py`, whose `.env` keys would kick
  off a real runtime LLM run). Fully resumable via the out-files + cache.
- **D2 sense.def_en 5.1 → 6.0/6** and **D1 ipa tail**: `scripts/merge_kaikki_fields.py` —
  deterministic fill-empty-only from kaikki (`def_en` +2198 as list; ipa_us +211, ipa_uk +581).
- D4 10/10, D5 9.9/10, D6 15/15 held (no regression; scorer confirms).

**To resume/extend** (e.g. GRE deck, or re-run after adding a scorer item): same pipeline,
`make_etym_batches.py gre` → `etym_workflow.js` (pass `{"indices":[...],"model":"sonnet"}` to
save quota, or omit `model` for this session's Opus) → `fold_etym_out.py fold gre`. The bad-JSON
tail (rare unescaped inner-quote) is caught by the validator loop — just delete that out-file and
re-run its single index.

## Fixers (regenerate DATA; the app code is already complete)

**kaikki.org is DOWNLOADED AND PRE-JOINED** (2026-07-19). One pass over the 3.2 GB English
extract already pulled every deck word into compact files on scratch:
`$LANG_PREP_CACHE/kaikki/<deck>_kaikki.json` (~25 MB each), schema per term:
`{etymology_text, ipa_us, ipa_uk, by_pos:{pos:{glosses:[...], examples:[...]}}}`.
Coverage — **TOEFL 10353/10358 matched · etymology_text 9671 · ipa 9607 · glosses all**;
GRE 10525/10526 · etymology 10244 · ipa 10045. So the FACTS for D3/D1/D2 are now local and
quota-free; the model's remaining job is reformatting, not research. Rebuild anytime with
`.venv/bin/python scripts/kaikki_extract.py` (~1 min).

- **D3 词源 (main target).** Each word needs `etymology:{breakdown,story,origin}` in the deck,
  OR a cache record marking it not-useful, in `$LANG_PREP_CACHE/enrich_etym/toefl/<term>.json`
  (schema `{term,useful,breakdown,story,origin}`). Then fold cache→deck with
  `.venv/bin/python scripts/enrich_etym.py toefl` (no --provider = apply-cache-only) and re-score.
  - **Best now (no quota): reformat kaikki `etymology_text` → the Chinese-glossed breakdown.**
    Read the word's `etymology_text` from `<deck>_kaikki.json` (authoritative Wiktionary facts:
    source language, roots, cognates) and have the model turn it into `{breakdown, story, origin}`
    in the exact format of `scripts/enrich_etym.py`'s system prompt + the `subsequent` example.
    `useful:false` when roots genuinely don't help a Chinese learner (very short native words,
    opaque origins). Prioritize uncovered words tier1→tier2, tpo_hf first (the study order). A
    `Workflow` fan-out over batches of ~30 words is ideal — it's reformatting, so it's fast/cheap
    and reliable. This is ~9800 words, so it spans several iterations / token windows: commit each
    batch, the cache makes it fully resumable.
  - Fallback (quota-limited, if you want pure-LLM for the ~700 words kaikki lacks etymology for):
    `.venv/bin/python scripts/enrich_etym.py toefl --provider groq --max-fails 8`.
- **D1 发音.** For the ~4% ipa_us / 7% ipa_uk tail (incl. 23 with nothing): merge from the kaikki
  extract's `ipa_us`/`ipa_uk` (9607 covered) — write a tiny merge that only fills EMPTY fields so
  it never clobbers the open-dict-data values already there; re-run `add_ipa.py` semantics or add
  a `--from-kaikki` path. tts-live needs a login node.
- **D2 释义.** Missing `def_en` (~2200 senses, ECDICT had only a Chinese gloss): fill from the
  kaikki extract's `by_pos[pos].glosses` (English learner definitions), matched to our sense by
  `pos`, keeping the existing `def_zh`. Only fill empty `def_en`; never overwrite.
- **D4/D5.** Already ~full; only touch if a fix elsewhere regresses them (the scorer will show it).

After any data change, **rebuild is not needed** — the app reads the JSON live; just restart the
throwaway server (or your real 8003) to pick up the new deck.

## Visual spot-check each iteration (Playwright MCP, 35k⭐, already connected)

After a fix, eyeball a few words in a real browser so the score can't hide a rendering bug:
```
mcp__playwright__browser_navigate  http://127.0.0.1:8096/     (the throwaway server)
mcp__playwright__browser_snapshot                              (card rendered? etym block? IPA?)
mcp__playwright__browser_take_screenshot                       (optional, for the commit note)
```
Press Space via the UI to reveal and confirm the 🌱 词源 block / US-UK IPA / examples show for a
word you just filled. Chromium runs headless on the cluster — no install needed.

## Relevant tools (all >1k⭐ except noted; the stack is already wired)

| Tool | ⭐ | Role | Status |
|---|---|---|---|
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 35k | drive/inspect the app in a real browser | **connected** (MCP) |
| [rany2/edge-tts](https://github.com/rany2/edge-tts) | 11k | free MS neural TTS (`/api/tts`) | installed; needs login node |
| [skywind3000/ECDICT](https://github.com/skywind3000/ECDICT) | 8k | the deck backbone (senses, freq, tags) | already the source |
| [tatuylonen/wiktextract](https://github.com/tatuylonen/wiktextract) · [kaikki.org](https://kaikki.org/) | 1.2k | machine-readable Wiktionary: authoritative **etymology + IPA + def_en + examples**, offline JSONL, no quota | **DOWNLOADED + pre-joined** → `$LANG_PREP_CACHE/kaikki/<deck>_kaikki.json` (see Fixers) |
| [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict) | 0.8k | US/UK IPA (already merged by `add_ipa.py`) | already used |

**kaikki.org is the highest-leverage un-used source**: one English JSONL (per-word `etymology_text`,
`sounds[].ipa`, `senses[].glosses`, `senses[].examples`) can fill D3 + the D1 tail + D2 `def_en`
from an authoritative dictionary with **no LLM quota**. If you pull it, cache the raw download on
scratch (it's large — check size first and tell the user before downloading GBs, per CLAUDE.md),
and reformat etymology into the Chinese-glossed breakdown the UI expects (that reformat can be the
model's job; the facts come from Wiktionary).

## Budget & freedom (user-set, 2026-07-19) — HIGH AUTONOMY
The user has explicitly given this loop **lots of time and tokens and a wide leash**. Quality
first; don't box yourself into one method. Specifically all of the following are pre-authorized,
no need to ask permission first:
- **Re-research freely** — not just reformatting kaikki. Look words up on the web, cross-check
  etymologies against multiple sources, generate from the model directly — whatever gives the
  best result.
- **Web search / WebFetch are fully open**, even when token-heavy. Use them liberally.
- **Download anything you need** (datasets, dictionaries, models, tools) — big files welcome.
- **Add tooling when it helps**: install/pull GitHub skills, pip packages, Claude Code plugins,
  or new MCP servers. Some installs (MCP OAuth, Claude Code extensions) need an interactive step
  the loop can't do headlessly — when that's the case, **ask the user to install it** (they've
  offered) and continue with other work meanwhile.

**The boundaries (only these):**
1. **Write only inside `/home/ctlang` and Neda's scratch**
   (`/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/`). Reading anything else is fine; do NOT
   create/modify/delete files anywhere outside those two areas.
2. **Big files go on scratch under `$LANG_PREP_CACHE`**
   (`/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache`) — NEVER into `/home/ctlang`
   (80 GB $HOME quota). Only code + the small deck JSONs belong in git.
3. **Don't recklessly delete large files** — especially the OTHER projects' caches that live
   beside ours under the same scratch root (`brdly-cache/ pw-cache/ xg-cache/ …`) and the raw
   downloads in `lang-prep-cache/official-real/raw/`. Delete only scratch data you created and
   can regenerate.

## Guardrails (from CLAUDE.md — do not skip)
- Commit identity: author `jackiectl`, `Co-Authored-By: Claude`, noreply email. **Don't push** unless asked.
- **Token-window rule**: at ~90% of the 5-hour window, STOP — commit progress + a status note,
  resume next window. Don't restart from scratch.
- Be honest: the score is the score. Don't inflate an item; if a check is wrong, fix the checker
  and say so.
```
```
