#!/usr/bin/env bash
# One-shot scratch-purge protection. NOT scheduled — run it by hand every few weeks
# (./scripts/backup_scratch.sh). No LLM, no quota, ~1 minute.
#
# /scratch auto-deletes files not ACCESSED for 60 days (ARC policy; touch-evasion is a
# violation). This mirrors the irreplaceable parts into home, which is never purged:
#   user-data          — SRS progress, personal notes, recordings, practice logs
#   official-real/*    — the parsed real-question banks + source PDFs (minus raw/)
# raw/ (2.5 GB of extracted archives) is NOT mirrored: the original downloads live on the
# laptop. No --delete, so a purge on scratch can never propagate into the backup.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source env.sh >/dev/null 2>&1

echo "===== backup $(date '+%F %T') on $(hostname) ====="
BACKUP="$(pwd)/data/backup"
mkdir -p "$BACKUP"
rsync -a "$PREP_DATA_DIR/" "$BACKUP/user-data/" \
  && echo "  user-data          -> $(du -sh "$BACKUP/user-data" | cut -f1)"
rsync -a --exclude 'raw/' "$REAL_DATA_ROOT/" "$BACKUP/official-real-lite/" \
  && echo "  official-real-lite -> $(du -sh "$BACKUP/official-real-lite" | cut -f1)"
echo "===== done $(date '+%F %T') ====="
