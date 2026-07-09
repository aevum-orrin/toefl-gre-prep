"""AI feedback engine. Wraps the Claude API to score & revise writing and speaking against
a Rubric, using structured outputs (guaranteed-valid JSON) + adaptive thinking. Falls back to
a deterministic offline stub when no API key is available, so the app and tests run without
network or secrets."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict

from .rubric import Rubric

DEFAULT_MODEL = "claude-opus-4-8"


@dataclass
class WritingFeedback:
    band: float                       # overall, on the rubric's scale
    criteria: dict                    # key -> {"score": float, "comment": str}
    top_fixes: list                   # list[str], highest-leverage improvements
    revised: str                      # a polished rewrite (essay) or model answer (speaking)
    offline: bool = False             # True when produced by the stub, not the model

    def to_dict(self) -> dict:
        return asdict(self)


_SYSTEM_WRITING = (
    "You are a strict but constructive TOEFL/GRE writing rater. Score the essay against the "
    "rubric, comment briefly on each criterion, list the highest-leverage fixes, and give one "
    "polished rewrite that keeps the author's ideas but fixes language and structure."
)
_SYSTEM_SPEAKING = (
    "You are a TOEFL speaking rater. You receive an automatic transcript of a spoken response, "
    "so ignore minor transcription artifacts and filler; judge delivery, language use, and topic "
    "development against the rubric. Comment on each criterion, list the highest-leverage fixes, "
    "and provide one improved model answer the test-taker could aim for."
)


class FeedbackEngine:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 offline: bool | None = None):
        self.model = model
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        # Auto-detect offline: no key -> stub. Caller can force either way.
        self.offline = (not key) if offline is None else offline
        self._client = None
        if not self.offline:
            from anthropic import Anthropic  # lazy: only needed for real calls
            self._client = Anthropic(api_key=key)

    def score_writing(self, essay: str, rubric: Rubric, prompt_text: str = "") -> WritingFeedback:
        if self.offline:
            return self._offline_stub(essay, rubric)
        user = (
            f"{rubric.as_prompt_block()}\n\n"
            f"Task prompt shown to the test-taker:\n{prompt_text or '(not provided)'}\n\n"
            f"Essay to score:\n\"\"\"\n{essay}\n\"\"\""
        )
        return self._score(_SYSTEM_WRITING, user, rubric)

    def score_speaking(self, transcript: str, rubric: Rubric, question: str = "") -> WritingFeedback:
        if self.offline:
            return self._offline_stub(transcript, rubric)
        user = (
            f"{rubric.as_prompt_block()}\n\n"
            f"Speaking prompt:\n{question or '(not provided)'}\n\n"
            f"Transcript of the spoken response:\n\"\"\"\n{transcript}\n\"\"\""
        )
        return self._score(_SYSTEM_SPEAKING, user, rubric)

    # -- shared real-API path: structured output guarantees valid JSON in the schema shape --
    def _score(self, system: str, user: str, rubric: Rubric) -> WritingFeedback:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": _schema_for(rubric)}},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        data = json.loads(text) if text.lstrip().startswith("{") else _extract_json(text)
        return WritingFeedback(
            band=float(data.get("band", 0)),
            criteria=data.get("criteria", {}),
            top_fixes=data.get("top_fixes", []),
            revised=data.get("revised", ""),
            offline=False,
        )

    # -- offline fallback: deterministic, no network. Enough to exercise the pipeline. --
    def _offline_stub(self, text: str, rubric: Rubric) -> WritingFeedback:
        n = len(re.findall(r"[A-Za-z']+", text))
        span = rubric.scale_max - rubric.scale_min
        band = round(rubric.scale_min + span * min(1.0, n / 220.0), 1)  # heuristic, NOT a real score
        criteria = {
            c.key: {"score": band, "comment": f"[offline stub] {c.name}: set ANTHROPIC_API_KEY for real feedback."}
            for c in rubric.criteria
        }
        fixes = [
            "This is OFFLINE STUB output — no ANTHROPIC_API_KEY was set.",
            f"Word count ~{n}. Real scoring needs the Claude API key in .env.",
        ]
        return WritingFeedback(band=band, criteria=criteria, top_fixes=fixes, revised=text, offline=True)


def _schema_for(rubric: Rubric) -> dict:
    """Build a strict JSON schema whose criteria keys match this rubric."""
    crit = {
        c.key: {"type": "object",
                "properties": {"score": {"type": "number"}, "comment": {"type": "string"}},
                "required": ["score", "comment"], "additionalProperties": False}
        for c in rubric.criteria
    }
    return {
        "type": "object",
        "properties": {
            "band": {"type": "number"},
            "criteria": {"type": "object", "properties": crit,
                         "required": list(crit), "additionalProperties": False},
            "top_fixes": {"type": "array", "items": {"type": "string"}},
            "revised": {"type": "string"},
        },
        "required": ["band", "criteria", "top_fixes", "revised"],
        "additionalProperties": False,
    }


def _extract_json(text: str) -> dict:
    """Fallback parser if structured output ever returns fences/prose around the JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise
