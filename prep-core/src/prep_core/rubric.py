"""Scoring rubric abstraction. Exam-specific rubrics live in the exam repo (TOEFL/GRE)
as JSON and are loaded here, so the engine itself stays exam-agnostic."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Criterion:
    key: str
    name: str
    description: str


@dataclass
class Rubric:
    name: str                       # e.g. "TOEFL Writing for an Academic Discussion"
    task_type: str                  # e.g. "academic_discussion"
    scale_min: int
    scale_max: int                  # 2026 TOEFL band tops out at 6; keep configurable for GRE
    criteria: list[Criterion]
    instructions: str = ""          # extra guidance handed to the model

    @classmethod
    def from_json(cls, path: str | Path) -> "Rubric":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Rubric":
        return cls(
            name=data["name"],
            task_type=data["task_type"],
            scale_min=data.get("scale_min", 1),
            scale_max=data.get("scale_max", 6),
            criteria=[Criterion(**c) for c in data["criteria"]],
            instructions=data.get("instructions", ""),
        )

    def as_prompt_block(self) -> str:
        lines = [f"Rubric: {self.name} (score each criterion {self.scale_min}-{self.scale_max})"]
        for c in self.criteria:
            lines.append(f"- {c.key} ({c.name}): {c.description}")
        if self.instructions:
            lines.append(f"Extra guidance: {self.instructions}")
        return "\n".join(lines)
