#!/usr/bin/env bash
# Source this before working: `source env.sh`
# Loads modern Python + ffmpeg (Great Lakes / Lmod) and activates the project venv.
source /usr/share/lmod/lmod/init/bash 2>/dev/null
module load python/3.12.1 ffmpeg/7.1.0 2>/dev/null

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$HERE/.venv" ]; then
  source "$HERE/.venv/bin/activate"
fi

# NOTE: we deliberately do NOT export .env here. The apps load .env in-process
# (prep_core.load_env). Exporting ANTHROPIC_API_KEY into this shell would make
# Claude Code bill that key per-token instead of using your Max subscription.
# So you can safely `source env.sh` and run Claude Code in the same shell.
