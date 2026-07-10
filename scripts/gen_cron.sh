#!/usr/bin/env bash
# Staggered Reading/Listening bank top-up for scrontab. Each invocation generates ONE
# task kind (small batch) so a single run is a light, few-minute API burst that won't
# trip the free-tier rate limit — schedule several rows a few hours apart to cover all
# kinds through the day. After generating, it folds new items into the canonical files.
#
# Arg 1 = task kind (default: rotate is caller's job). Arg 2 = count (default 4).
# Runs on the free provider (Groq preferred; Gemini fallback). Updates local JSON only;
# commit/push yourself when you want the new items on GitHub.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source env.sh >/dev/null 2>&1

KIND="${1:?usage: gen_cron.sh <kind> [count]}"
N="${2:-4}"

echo "===== gen $KIND x$N  $(date '+%F %T') on $(hostname) ====="
python3 scripts/gen_bank.py "$KIND" --n "$N" --provider groq || \
  python3 scripts/gen_bank.py "$KIND" --n "$N" --provider gemini
python3 scripts/merge_rl.py
echo "===== gen done $(date '+%F %T') ====="
