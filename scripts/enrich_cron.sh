#!/usr/bin/env bash
# Resume vocab enrichment using whatever free daily quota is available today, then stop.
#
# Meant to be run by scrontab (Slurm cron) on a Great Lakes COMPUTE node — those have outbound
# internet, so the Groq/Gemini calls work. Fully resumable: only still-unenriched words are sent
# (per-word cache in scratch), and when a provider's daily quota is hit the run exits cleanly via
# --max-fails instead of grinding. Each day it chips away at the long tail until both decks are full.
#
# It does NOT git-commit/push — it just updates the local deck JSON (what the app reads) and the
# scratch cache. Commit/push the enriched decks yourself when you want them on GitHub.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source env.sh >/dev/null 2>&1

echo "===== enrich run $(date '+%F %T') on $(hostname) ====="
for prov in groq gemini; do
  for deck in toefl gre; do
    echo "--- $deck via $prov ---"
    python3 scripts/enrich_vocab.py "$deck" --provider "$prov" --batch 20 --sleep 2 --max-fails 8
  done
done

python3 - <<'PY'
import json
for d, p in [("toefl", "toefl/vocab/toefl_vocab.json"), ("gre", "gre/vocab/gre_vocab.json")]:
    x = json.load(open(p)); e = sum(1 for w in x if w.get("gloss_en"))
    print(f"  {d}: {e}/{len(x)} enriched")
PY
echo "===== done $(date '+%F %T') ====="
