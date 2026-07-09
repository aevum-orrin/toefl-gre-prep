"""Practice-log store: append-only JSONL of attempts (writing, speaking, quiz...),
so any exam repo can track progress over the sprint without its own storage code."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ProgressStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def log(self, kind: str, **fields) -> dict:
        """kind: e.g. 'writing', 'speaking', 'vocab'. fields: arbitrary metrics (band, task, etc.)."""
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind, **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self, kind: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if kind is None or e.get("kind") == kind:
                out.append(e)
        return out
