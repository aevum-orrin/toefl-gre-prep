#!/usr/bin/env bash
# ONE scrontab job per section: generate a small batch for every task kind in that
# section (reading = 3 kinds, listening = 4 kinds) in a single run, spacing the API
# calls with a sleep so a run stays under the free-tier per-minute rate limit, then
# fold everything in once via merge_rl.py. Two jobs total (reading + listening),
# not one-per-kind. Updates local JSON only; commit/push yourself.
#
# Usage: gen_cron.sh reading|listening [n_per_kind]   (default n_per_kind = 4)
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source env.sh >/dev/null 2>&1

SECTION="${1:?usage: gen_cron.sh reading|listening [n_per_kind]}"
N="${2:-4}"

case "$SECTION" in
  reading)   KINDS=(academic_passage daily_life complete_words) ;;
  listening) KINDS=(academic_talk conversation announcement choose_response) ;;
  *) echo "unknown section '$SECTION' (use reading|listening)"; exit 1 ;;
esac

echo "===== gen $SECTION ($N per kind) $(date '+%F %T') on $(hostname) ====="
for k in "${KINDS[@]}"; do
  python3 scripts/gen_bank.py "$k" --n "$N" --provider groq --sleep 6 || \
    python3 scripts/gen_bank.py "$k" --n "$N" --provider gemini --sleep 6
done
python3 scripts/merge_rl.py
echo "===== gen done $(date '+%F %T') ====="
