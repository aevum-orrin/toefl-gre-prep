# Vocab-completeness Loop — runbook for an autonomous session

Point a fresh Claude Code session at this file. Goal: iterate until the TOEFL vocab deck +
the vocab-srs app score **≥ 95 / 100** on `scripts/score_vocab.py`, or **10 iterations**,
whichever first. The score is the referee — it is machine-computed from the data + a live
server, never a vibe. **Read the project `CLAUDE.md` first** (storage layout, token-window
rule, commit identity, node policy). This runbook only adds the loop specifics.

## The one loop

```
for iteration in 1..10:
  1. SCORE   — run the scorer (command below) → note TOTAL and the lowest-scoring items
  2. PICK    — take the single dimension losing the most points
  3. FIX     — run that dimension's fixer (see "Fixers"), regenerating data only
  4. VERIFY  — re-run the scorer; spot-check 3-5 words in a real browser (Playwright MCP)
  5. COMMIT  — git commit the iteration (data + any code), note old→new score
  if TOTAL >= 95: stop
```

Announce each iteration in chat (one line: what you're fixing and why). Commit after every
iteration so any regression is one `git revert` away.

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
| **D2 释义与例句** | 30 | gloss_en 5 · sense.pos 4 · def_en 6 · def_zh 5 · example 6 · colloc≥2 4 |
| **D3 词根词缀词源** | 17 | resolved (has `etymology` OR cached `useful:false`) 14 · 3-field fullness 3 |
| **D4 结构一致性** | 10 | schema 3 · no-dup 2 · no empty-shell sense 3 · no mojibake 2 |
| **D5 学习元数据** | 10 | tier 3 · tpo_hf≥1500 2 · verb exchange 3 · freq\|bnc 2 |
| **D6 App 功能 (live)** | 15 | read APIs 4 · write+undo 2 · frontend e2e 6 · latency 3 |

If you think a dimension is worth measuring that isn't here (e.g. audio for real MP3s, synonym
sets, example-sentence quality via an LLM judge), **add an item to `score_vocab.py`** — but keep
every check machine-verifiable and deterministic, and say in the commit why you added it.

## Baseline (2026-07-19, compute node so tts-live=0): **81/100**
Biggest gaps, in order: **D3 词源 3.7/17** (etymology only ~5% resolved) ≫ D1 IPA (~1 pt of
missing US/UK, 23 words with no phonetic at all) > D2 def_en (~0.9, 15% of senses lack English
definitions). D4/D5/D6 are essentially full. So early iterations are almost all D3.

## Fixers (regenerate DATA; the app code is already complete)

- **D3 词源 (main target).** Each word needs `etymology:{breakdown,story,origin}` in the deck,
  OR a cache record marking it not-useful. Two ways to produce records into the cache
  `$LANG_PREP_CACHE/enrich_etym/toefl/<term>.json` (schema `{term,useful,breakdown,story,origin}`):
  - **Best (no quota): the loop's own model generates them.** Prioritize uncovered words by
    tier1→tier2, tpo_hf first (that's the study order). Write correct, standard etymologies only
    (Latin/Greek roots, transparent affixes, loanword notes), Chinese-glossed, per the format in
    `scripts/enrich_etym.py`'s system prompt and the `subsequent` example. `useful:false` for
    words where roots don't genuinely help a Chinese learner. A `Workflow` fan-out is ideal here.
  - **Free-LLM (quota-limited): `.venv/bin/python scripts/enrich_etym.py toefl --provider groq
    --max-fails 8`** (Groq dodges Gemini's low daily cap). Resumable; stops clean when quota hits.
  - Then **fold cache → deck**: `.venv/bin/python scripts/enrich_etym.py toefl` (no provider =
    apply-cache-only path). Re-score.
- **D1 发音.** `.venv/bin/python scripts/add_ipa.py` re-merges open-dict-data IPA. The residual
  ~4% (incl. 23 with nothing) aren't in ipa-dict — fill from another source: kaikki.org Wiktionary
  IPA (see Tools), or have the model supply US/UK IPA for that short tail. tts-live needs a login
  node.
- **D2 释义.** Missing `def_en` (~2200 senses) are ones where ECDICT had only a Chinese gloss.
  Fill English learner-definitions for those senses (model or kaikki), keeping the existing
  `def_zh`. `scripts/enrich_vocab.py` already fills examples/collocations.
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
| [tatuylonen/wiktextract](https://github.com/tatuylonen/wiktextract) · [kaikki.org](https://kaikki.org/) | 1.2k | machine-readable Wiktionary: authoritative **etymology + IPA + def_en + examples**, offline JSONL, no quota | **candidate for D3/D2/D1** — download the English extract, join by lemma |
| [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict) | 0.8k | US/UK IPA (already merged by `add_ipa.py`) | already used |

**kaikki.org is the highest-leverage un-used source**: one English JSONL (per-word `etymology_text`,
`sounds[].ipa`, `senses[].glosses`, `senses[].examples`) can fill D3 + the D1 tail + D2 `def_en`
from an authoritative dictionary with **no LLM quota**. If you pull it, cache the raw download on
scratch (it's large — check size first and tell the user before downloading GBs, per CLAUDE.md),
and reformat etymology into the Chinese-glossed breakdown the UI expects (that reformat can be the
model's job; the facts come from Wiktionary).

## Guardrails (from CLAUDE.md — do not skip)
- Commit identity: author `jackiectl`, `Co-Authored-By: Claude`, noreply email. **Don't push** unless asked.
- **Storage**: only code + the deck JSONs are in git; caches/big downloads go on scratch, and
  **ask the user before anything that would add real GBs** to scratch or home.
- **Token-window rule**: at ~90% of the 5-hour window, STOP — commit progress + a status note,
  resume next window. Don't restart from scratch.
- Be honest: the score is the score. Don't inflate an item; if a check is wrong, fix the checker
  and say so.
```
```
