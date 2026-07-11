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
    # second pass: 词根词缀/词源 (etymology) — same cache/resume design, rides leftover quota
    echo "--- $deck etymology via $prov ---"
    python3 scripts/enrich_etym.py "$deck" --provider "$prov" --batch 20 --sleep 2 --max-fails 8
  done
done

python3 - <<'PY'
import json
for d, p in [("toefl", "toefl/vocab/toefl_vocab.json"), ("gre", "gre/vocab/gre_vocab.json")]:
    x = json.load(open(p)); e = sum(1 for w in x if w.get("gloss_en"))
    print(f"  {d}: {e}/{len(x)} enriched")
PY

# ---- scratch-purge protection ----------------------------------------------------------
# /scratch auto-deletes files not ACCESSED for 60 days (ARC policy; touch-evasion is a
# violation). Nightly, mirror the small IRREPLACEABLE data into home (data/ is gitignored):
#   user-data (SRS progress, notes, recordings, logs; ~MBs) and official-real minus raw/
#   (parsed real questions + source PDFs; ~100 MB). raw/ (2.5 GB extracted archives) is NOT
#   mirrored — keep the original downloads on your laptop. No --delete: a purge on scratch
#   must never propagate into the backup.
BACKUP="$(pwd)/data/backup"
mkdir -p "$BACKUP"
rsync -a "$PREP_DATA_DIR/" "$BACKUP/user-data/" 2>/dev/null \
  && echo "backup: user-data mirrored to home"
rsync -a --exclude 'raw/' "$REAL_DATA_ROOT/" "$BACKUP/official-real-lite/" 2>/dev/null \
  && echo "backup: official-real (minus raw/) mirrored to home"
echo "===== done $(date '+%F %T') ====="
