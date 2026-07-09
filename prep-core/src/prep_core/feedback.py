"""AI feedback engine: scores & revises writing and speaking against a Rubric, using structured
JSON output. Backend-agnostic — it talks to whatever `providers.make_provider()` picks (free Gemini
by default, or Groq / Anthropic), and falls back to a deterministic OFFLINE STUB when no backend is
usable, so the app and tests run without network or secrets."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from .rubric import Rubric
from .providers import make_provider, Provider

DEFAULT_MODEL = "claude-opus-4-8"  # kept for back-compat imports; real default is provider-driven


@dataclass
class WritingFeedback:
    band: float                       # overall, on the rubric's scale
    criteria: dict                    # key -> {"score": float, "comment": str}
    top_fixes: list                   # list[str], highest-leverage improvements
    revised: str                      # a polished rewrite (essay) or model answer (speaking)
    offline: bool = False             # True when produced by the stub, not a model

    def to_dict(self) -> dict:
        return asdict(self)


_SEVERITY = (
    "Rate STRICTLY, like a demanding senior ETS rater — calibrate hard, never lenient. Hunt down and "
    "report EVERY weakness you can justify: grammar, verb tense/agreement, articles, prepositions, "
    "word form, collocation, awkward or unidiomatic phrasing, register, spelling, punctuation, weak "
    "transitions, coherence gaps, thin or unsupported ideas, and any failure to fully satisfy the "
    "task. Quote the offending text when you flag something. Do NOT inflate scores to be encouraging. "
    "Reserve the top score for a response that is genuinely flawless at the rubric's top-band "
    "standard; if you hesitate between two scores, give the LOWER one and say why. A competent-but-"
    "ordinary response should land mid-band, not top. Be specific and honest, not nice."
)
_SYSTEM_WRITING = (
    "You are an exacting TOEFL/GRE writing rater applying the official 2026 ETS rubric at full "
    "strictness. " + _SEVERITY + " Score each criterion, comment specifically on each, list the "
    "highest-leverage fixes in priority order, and give one polished rewrite that keeps the author's "
    "ideas but fixes language, structure, and task fulfilment."
)
_SYSTEM_SPEAKING = (
    "You are an exacting TOEFL speaking rater applying the official 2026 ETS rubric at full "
    "strictness. You receive an automatic transcript, so ignore pure transcription artifacts, but "
    "judge grammar, vocabulary range/accuracy, and topic development hard. " + _SEVERITY +
    " Comment specifically on each criterion, list the highest-leverage fixes, and provide one "
    "improved model answer to aim for."
)


class FeedbackEngine:
    def __init__(self, provider: str | Provider | None = None, model: str | None = None,
                 api_key: str | None = None, offline: bool | None = None):
        """provider: a provider name ('gemini'|'groq'|'anthropic'|'offline'), a ready Provider,
        or None to auto-pick from env (LLM_PROVIDER, else first key found, free-first)."""
        if offline is True or provider == "offline":
            self.provider = None
        elif isinstance(provider, Provider):
            self.provider = provider
        else:
            self.provider = make_provider(provider, model=model, api_key=api_key)
        self.offline = (self.provider is None) if offline is None else offline
        self.provider_name = self.provider.name if self.provider else "offline"
        self.model = self.provider.model if self.provider else (model or "offline-stub")

    def score_writing(self, essay: str, rubric: Rubric, prompt_text: str = "") -> WritingFeedback:
        if self.offline:
            return self._offline_stub(essay, rubric)
        user = (
            f"{rubric.as_prompt_block()}\n\n"
            f"Task prompt shown to the test-taker:\n{prompt_text or '(not provided)'}\n\n"
            f"Response to score:\n\"\"\"\n{essay}\n\"\"\""
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

    # -- shared real path: provider returns JSON in the rubric's schema shape --
    def _score(self, system: str, user: str, rubric: Rubric) -> WritingFeedback:
        data = self.provider.complete_json(system, user, _schema_for(rubric))
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
            c.key: {"score": band, "comment": f"[offline stub] {c.name}: set an LLM key for real feedback."}
            for c in rubric.criteria
        }
        fixes = [
            "This is OFFLINE STUB output — no LLM backend was usable (no API key set).",
            f"Word count ~{n}. Set GEMINI_API_KEY (free) or another key in .env for real scoring.",
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
