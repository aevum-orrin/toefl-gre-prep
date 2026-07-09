#!/usr/bin/env bash
# Source this before working: `source env.sh`
# Loads modern Python + ffmpeg (Great Lakes / Lmod) and activates the project venv.
source /usr/share/lmod/lmod/init/bash 2>/dev/null
module load python/3.12.1 ffmpeg/7.1.0 2>/dev/null

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$HERE/.venv" ]; then
  source "$HERE/.venv/bin/activate"
fi

# Load local secrets (ANTHROPIC_API_KEY etc.) if present; .env is gitignored.
if [ -f "$HERE/.env" ]; then
  set -a; source "$HERE/.env"; set +a
fi
