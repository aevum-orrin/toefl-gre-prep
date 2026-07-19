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

# --- Storage layout (keep home < 2GB; heavy/growing data lives on scratch) ---------------
# home repo = code + small AI question-bank JSON only. Everything heavy or growing goes on
# scratch (Neda's owned space): real ETS/TPO questions + audio, and ALL user practice records
# (SRS progress, recordings, essays, logs). Apps read these env vars; unset falls back to
# home/data for quick dev. Change LANG_PREP_CACHE once to relocate everything.
export LANG_PREP_CACHE="${LANG_PREP_CACHE:-/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache}"
export REAL_DATA_ROOT="${REAL_DATA_ROOT:-$LANG_PREP_CACHE/official-real}"   # real questions (ETS/TPO)
export PREP_DATA_DIR="${PREP_DATA_DIR:-$LANG_PREP_CACHE/user-data}"          # user's own records
mkdir -p "$PREP_DATA_DIR" "$REAL_DATA_ROOT" 2>/dev/null

# Runtime free-AI fallback order (live scoring + live prompt gen at localhost): Gemini FIRST,
# fall through to Groq only after Gemini's quota is exhausted / it fails repeatedly. Paid
# Anthropic is intentionally EXCLUDED at runtime — free tiers only. (Opus pre-generation is done
# offline via Claude Code subscription, not this runtime path.)
export LLM_FALLBACK_ORDER="${LLM_FALLBACK_ORDER:-gemini,groq}"

# WordNet data (English synonyms/antonyms for the vocab decks — scripts/add_syn_ant.py and the
# score_vocab.py syn/ant items). Kept on scratch, not $HOME. `.venv/bin/pip install nltk` once,
# then download 'wordnet' into this dir. The scripts default to this path too, so it's optional.
export NLTK_DATA="${NLTK_DATA:-$LANG_PREP_CACHE/nltk_data}"
