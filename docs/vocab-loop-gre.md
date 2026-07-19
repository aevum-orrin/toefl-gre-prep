# GRE Vocab-completeness Loop — runbook for an autonomous session

Point a fresh Claude Code session at this file. Goal: iterate until the **GRE** vocab deck +
the vocab-srs app score **≥ 95 / 100** on `scripts/score_vocab.py gre`, or **10 iterations**,
whichever first. The score is the referee — machine-computed from the data + a live server,
never a vibe. **Read the project `CLAUDE.md` first** (storage layout, token-window rule, commit
identity, node policy) and the sibling [docs/vocab-loop.md](vocab-loop.md) (the TOEFL run that
reached 99.6 with this exact toolchain — GRE reuses every script, just `deck=gre`).

## The one loop (GLOBAL shape — read this, it is the whole point)

```
for iteration in 1..10:
  1. SCORE    — run the scorer → note TOTAL and EVERY dimension's gap (fine-grained, fractional)
  2. FIX-ALL  — in the SAME iteration raise EVERY deficient dimension at once (run all the
                relevant fixers: D1 ipa, D2 def_en+gloss_en+examples+colloc, D3 词源).
                NOT "only the lowest dimension this round, the next-lowest next round".
  3. VERIFY   — re-run the scorer; spot-check 3-5 words in a real browser (Playwright MCP)
  4. COMMIT   — git commit the iteration (data + any code), note old→new score
  if TOTAL >= 95: stop
```

Per the **global rule** in `~/.claude/CLAUDE.md` ("Loop Engineering"): every iteration is the
SAME full sweep that pushes ALL dimensions up together, then re-scores (a sub-agent fan-out is
fine). Fine-grained fractional scores (16.7, 6.87…) are the meter. Announce a one-line score
delta each round; commit each round so a regression is one `git revert` away.

## Run environment (get this wrong and you waste hours — identical to the TOEFL loop)
- **Run on a LOGIN node** (`gl-login1..5`), NOT a compute node — compute nodes 502 on edge-tts
  (the D1 tts-live item) and can't reach any network. Check `hostname -s` → want `gl-login*`.
- **`source env.sh`** first (exports `LANG_PREP_CACHE`, `PREP_DATA_DIR`, `REAL_DATA_ROOT`).
- **Scoring uses a THROWAWAY server on a temp `PREP_DATA_DIR`** (never the real 8003) — `--e2e`
  and `--allow-write` grade words:

```bash
source env.sh
export SCRATCHPREP=$(mktemp -d /tmp/vocab-score-XXXX)
NODE=$(ls -d ~/.vscode-server/cli/servers/Stable-*/server/node | head -1)
( cd tools/vocab-srs && PREP_DATA_DIR=$SCRATCHPREP PREP_IDLE_MIN=0 \
    setsid nohup ../../.venv/bin/uvicorn app:app --port 8096 >/tmp/score-srv.log 2>&1 </dev/null & )
sleep 9
.venv/bin/python scripts/score_vocab.py gre --url http://127.0.0.1:8096 --allow-write --e2e --node "$NODE"
# the app loads the deck IN MEMORY at startup — RESTART this server after any deck change to re-score live.
# stop it when done: kill $(ss -ltnp | grep ':8096 ' | grep -o 'pid=[0-9]*' | cut -d= -f2)
```

## ✅ DONE (2026-07-19): **96.2 / 100** — target met in ONE iteration
Full sweep in a single round: `merge_kaikki_fields gre` + `add_syn_ant gre` (deterministic D1/D2 +
syn/ant 4/4) → 349-batch Sonnet etym fan-out folded (D3 5.2→**17.0/17**, 10524/10526 resolved =
7577 etymologies + 2947 judged-not-useful) → all 21 enrich batches folded (D2 example 4.14, colloc
2.48). 3 out-files had unescaped inner ASCII quotes in Chinese content — repaired deterministically
(no LLM) by converting inner `"`→`”` while preserving JSON-structural quotes. Final: D1 17.8 · D2 28.5 ·
D3 17.0 · D4 10 · D5 7.9 (tpo_hf 0/2 is N/A for GRE) · D6 15. Commits `50a1a27`→`5c31415`→`18f0299`.
Remaining headroom (optional, ~ceiling 97.5): D2 example→5 / colloc→3 by widening the enrich fan-out.

## Baseline (2026-07-19): **78.1 / 100** on `gl-login4` (full live checks pass)
Verified end-to-end (D6 15/15, tts-live 4/4). Full field audit of the 10526-word / 14931-sense deck:

| Dim | now | gap | detail (from the audit) |
|---|---|---|---|
| **D1 发音** | 17.0/18 | −1.0 | ipa_us 6.45 (830 missing, 623 kaikki-fillable) · ipa_uk 4.56 (929 missing, 756 fillable) · 17 words no phonetic |
| **D2 释义例句** | 25.1/30* | **−4.9** | *(baseline pre-dates the syn/ant items; re-score.)* gloss_en 3.74/5 · def_en 5.11/6 · **example 4.43/6 (3907 senses missing)** · **colloc≥2 2.95/4** · def_zh 4.88/5 (not kaikki-fillable) · **synonyms/antonyms 0/2+0/2 until `add_syn_ant.py gre` runs** (D2 is now 30 pts split gloss_en 5·pos 4·def_en 5·def_zh 4·example 5·colloc 3·syn 2·ant 2) |
| **D3 词源** | 3.1/17 | **−13.9** | only 63 have etymology + 17 not-useful = **80/10526 resolved**. `etymology_text` available for 10244. THE dominant gap. |
| **D4 结构** | 10.0/10 | 0 | schema/dedup/shell/mojibake all clean |
| **D5 元数据** | 7.9/10 | −2.1 | tier 3/3 · verb-exchange 2.98 · freq\|bnc 1.93 · **tpo_hf 0/2 — STRUCTURALLY N/A for GRE (TPO is TOEFL-only)** |
| **D6 App** | 15.0/15 | 0 | read/write/e2e/latency all green on a login node |

**Realistic ceiling ≈ 97.5/100**: the `tpo_hf>=1500` item (2 pts) can never fire for GRE, and
def_zh caps ~4.88 (kaikki has no Chinese). So the reachable max is ~97–98; **≥95 is comfortably
reachable by clearing D3 + D2** — but you must raise D2 examples/colloc too, not just the deterministic
fields. Do **not** hand GRE free points by editing the scorer's tpo_hf item — that's gaming; leave it.
(If you genuinely want a GRE-appropriate high-freq metadata item, add a NEW machine-checkable one and
say why in the commit — do not relabel the TOEFL one.)

## Fixers — reuse the TOEFL toolchain, all `deck=gre`

> ### ⚠️ FIRST THING EACH ITERATION: regenerate the batch files from the CURRENT deck
> The `make_*_batches.py` scripts pick which words still need work by reading the deck's CURRENT
> state. So **always run Step 1 (deterministic merge) FIRST, then (re)run `make_etym_batches.py gre`
> and `make_enrich_batches.py gre --incomplete` BEFORE launching any Workflow.** Otherwise you
> reprocess words that are already done (waste) or miss ones (stall).
> **NOTE (2026-07-19):** a previous session PRE-GENERATED stale batch files on scratch
> (`enrich_batches/etym/gre/` 349 files, `enrich_batches/gre/` 21 files) while writing this runbook.
> **Ignore/overwrite them** — the make-scripts wipe and rewrite the batch dir every run, so just
> run them fresh after Step 1 and use the pending list they produce.

**kaikki is pre-joined for GRE**: `$LANG_PREP_CACHE/kaikki/gre_kaikki.json` (~25 MB), per-term
`{etymology_text, ipa_us, ipa_uk, by_pos:{pos:{glosses, examples}}}`. Coverage: etymology_text 10244,
ipa 10045, glosses all. Facts are local + quota-free; the model only reformats. Rebuild with
`.venv/bin/python scripts/kaikki_extract.py` (~1 min) if ever needed.

**MODEL POLICY (user, 2026-07-19):** big fan-outs run on **Sonnet** (`{"model":"sonnet"}`) — Opus
was proven equal-quality but burns the subscription quota too fast for a task this size. **Never**
route to a free/external LLM (Gemini/Groq): that means **do NOT run `enrich_etym.py` or
`enrich_vocab.py` directly** — they `load_env(.env)` and will kick off a real Gemini/Groq run. Use
the Workflow fan-out + the `fold_*` scripts, which apply the cache to the deck with **no LLM call**.

### Step 1 — deterministic D1 + D2 fill (no LLM, run FIRST, ~2 s)
```bash
.venv/bin/python scripts/merge_kaikki_fields.py gre     # ipa_us/uk + sense.def_en + word gloss_en (fill-empty-only)
.venv/bin/python scripts/add_syn_ant.py gre             # English synonyms/antonyms from WordNet (D2)
```
`merge` fills only EMPTY fields (never clobbers open-dict IPA / ECDICT glosses): ipa_us +~623,
ipa_uk +~756, def_en +~2207, gloss_en +~2645. `add_syn_ant` fills every word WordNet has syn/ant
for (one deterministic pass → the D2 syn/ant items go straight to full). **WordNet install once**
(persists on scratch): `.venv/bin/pip install nltk && NLTK_DATA=$LANG_PREP_CACHE/nltk_data \
.venv/bin/python -c "import nltk;nltk.download('wordnet',download_dir='$NLTK_DATA')"` — already done
2026-07-19, data is on scratch, so normally you can skip it.

### Step 2 — D3 词源 (the big one: kaikki etymology_text → Chinese 词根词缀, Sonnet fan-out)
```bash
.venv/bin/python scripts/make_etym_batches.py gre --batch 30      # -> ~349 batches, priority-ordered
.venv/bin/python scripts/fold_etym_out.py pending gre             # -> JSON list of pending indices
```
Then a Workflow over the pending indices (in waves; the out-files on scratch make it fully resumable):
```
Workflow({ scriptPath: "scripts/etym_workflow.js",
           args: { deck: "gre", model: "sonnet", indices: [<pending...>] } })
```
Each agent reads `enrich_batches/etym/gre/batch_XXXX.json`, reformats `etymology_text` into
`{breakdown, story, origin}` (or `useful:false` when roots don't help a Chinese learner), and Writes
`enrich_out/etym/gre/batch_XXXX.out.json`. Then fold (validates JSON, distributes to per-term cache,
applies cache→deck DIRECTLY — no LLM):
```bash
.venv/bin/python scripts/fold_etym_out.py fold gre
```
**Gotcha:** a rare agent emits invalid JSON (unescaped inner quote). The audit loop below catches it;
just `rm` that one out-file and re-run its single index. Validate before folding:
```bash
.venv/bin/python - <<'PY'
import json,os
from pathlib import Path
D=Path(os.environ["LANG_PREP_CACHE"])/"enrich_out/etym/gre"
files=sorted(D.glob("batch_*.out.json"))
for f in files:
    try: json.loads(f.read_text())
    except Exception as e: print("BAD", f.name, str(e)[:60])
print("checked", len(files), "out-files")
PY
```

### Step 3 — D2 examples + collocations (LLM fan-out, Sonnet) — the piece merge can't do
`gloss_en` is now filled by Step 1, so use **`--incomplete`** selection (picks words with any sense
missing an example or <2 collocations, regardless of gloss_en — the plain mode would skip them):
```bash
.venv/bin/python scripts/make_enrich_batches.py gre --tiers 1,2 --incomplete --size 60
# note the batch count N it prints; input dir = $LANG_PREP_CACHE/enrich_batches/gre
```
Workflow (writes `enrich_out/gre/batch_NNN.json`, resumable — re-run only the `only:[...]` that are missing):
```
Workflow({ scriptPath: "scripts/enrich_workflow.js",
           args: { deck: "gre", model: "sonnet",
                   inDir: "$LANG_PREP_CACHE/enrich_batches/gre",
                   outDir: "$LANG_PREP_CACHE/enrich_out/gre",
                   start: 0, end: N } })
```
Fold into the deck (no LLM — reads the out-files, merges gloss_en/example/colloc per sense):
```bash
.venv/bin/python scripts/fold_enrich.py gre
```
Tier 3 ("trivially simple") is excluded by default. If after Steps 1-3 the example/colloc items are
still short of target, widen to `--tiers 1,2,3 --incomplete` — but weigh it: tier-3 words are basic
and the ≥95 target is usually met without them once D3 is full.

### D4 / D5
D4 is already 10/10. D5: tier 3/3, verb-exchange/freq already near-full, **tpo_hf 0/2 is N/A (leave it)**.
Only revisit D4/D5 if a fix elsewhere regresses them — the scorer will show it.

## Visual spot-check each iteration (Playwright MCP, already connected)
After folding, RESTART the throwaway server (in-memory deck) and eyeball a few freshly-filled words:
```
mcp__playwright__browser_navigate  http://127.0.0.1:8096/
# press "/" to open search, type a word you just filled, Enter, Space to reveal
# confirm: 🌱 词根词缀 block renders (breakdown/story/origin), US/UK IPA, a def_en, an example
```
Chromium runs headless on the cluster — no install needed.

## Budget & freedom (user-set) — HIGH AUTONOMY, same as the TOEFL loop
Re-research freely (web/WebFetch open), download big files to scratch, add tooling. **Boundaries
(only these):** write only inside `/home/ctlang` and Neda's scratch
(`/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/`); big files on scratch under `$LANG_PREP_CACHE`,
never into `$HOME`; don't recklessly delete other projects' scratch caches. Big fan-outs on **Sonnet**.

## Guardrails (from CLAUDE.md — do not skip)
- Commit identity: author `jackiectl`, `Co-Authored-By: Claude`, noreply email. **Don't push** unless asked.
- **Token-window rule**: at ~90% of the 5-hour window, STOP — commit progress + a status note, resume next window.
  The etym/enrich caches + out-files make every step fully resumable; never restart from scratch.
- Be honest: the score is the score. If a check is wrong, fix the CHECKER and say so — never inflate an item.
```
