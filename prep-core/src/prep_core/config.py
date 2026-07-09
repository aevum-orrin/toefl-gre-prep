"""Tiny .env loader so apps read secrets from a file WITHOUT exporting them into the
interactive shell. This matters here: if ANTHROPIC_API_KEY is exported in a shell that
also runs Claude Code, Claude Code bills that key per-token instead of using the Max
subscription. Loading in-process keeps the key scoped to the app."""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path | None = None, override: bool = False) -> dict:
    """Load KEY=VALUE lines from a .env file into os.environ.

    By default does NOT override values already set in the environment (shell wins),
    and does nothing if the file is absent. Returns the dict of parsed pairs.
    """
    p = Path(path) if path else _find_dotenv()
    loaded: dict[str, str] = {}
    if not p or not p.exists():
        return loaded
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = val
        loaded[key] = val
    return loaded


def _find_dotenv() -> Path | None:
    for base in [Path.cwd(), *Path.cwd().parents]:
        candidate = base / ".env"
        if candidate.exists():
            return candidate
    return None
