"""Real-time practice-item generation. Uses the same pluggable provider as the feedback engine, so
on the free Gemini/Groq tier the app can generate fresh, on-format 2026 items on demand (the user's
preference) — and gracefully fall back to the pre-built bank when no backend is available.

Kept exam-agnostic-ish: the prompts describe the official 2026 TOEFL task shapes; a GRE variant would
add its own prompts. All methods return plain dicts/str the web layer can serialize directly."""
from __future__ import annotations

from .providers import Provider, make_provider

_SYS = ("You generate authentic practice items for the official 2026 TOEFL iBT. Follow the exact task "
        "format requested. Output must be natural, exam-realistic, and self-contained.")

_INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "questions"],
    "additionalProperties": False,
}

_PROMPTS_SCHEMA = {
    "type": "object",
    "properties": {"prompts": {"type": "array", "items": {"type": "string"}}},
    "required": ["prompts"],
    "additionalProperties": False,
}

_WRITING_KIND = {
    "write_email": ("a 2026 TOEFL 'Write an Email' task: describe a realistic academic or social "
                    "situation, then state what the test-taker must write (a request, information, or "
                    "a proposed solution). Put the situation and the instruction in one self-"
                    "contained prompt."),
    "academic_discussion": ("a 2026 TOEFL 'Write for an Academic Discussion' task: a professor's "
                            "question to the class (1-3 sentences) followed by two short classmate "
                            "posts taking different stances. Put it all in one self-contained prompt, "
                            "labelling the professor and the two students."),
}


class QuestionGenerator:
    """Wraps a Provider. `available` is False when no backend is usable (caller uses the bank)."""

    def __init__(self, provider: Provider | None = None):
        self.provider = provider if provider is not None else make_provider()

    @property
    def available(self) -> bool:
        return self.provider is not None

    def interview_topic(self) -> dict:
        """A 2026 'Take an Interview' set: one topic + exactly 4 spontaneous follow-up questions."""
        user = (
            "Generate ONE 2026 TOEFL Speaking 'Take an Interview' item: a single academic/campus topic "
            "and exactly 4 spoken follow-up questions about the test-taker's experiences and opinions, "
            "progressively deeper, spontaneous, no reading required. Vary the topic each time."
        )
        data = self.provider.complete_json(_SYS, user, _INTERVIEW_SCHEMA)
        qs = [q for q in data.get("questions", []) if isinstance(q, str)][:4]
        return {"topic": data.get("topic", "Interview"), "questions": qs}

    def repeat_sentence(self) -> str:
        """A 2026 'Listen and Repeat' sentence: one natural campus/academic sentence, ~7-20 words."""
        user = (
            "Generate ONE natural English sentence for the 2026 TOEFL 'Listen and Repeat' task: a single "
            "sentence of about 7-20 words on a campus, community, or academic topic, clearly "
            "pronounceable. Output ONLY the sentence, no quotes or numbering."
        )
        return self.provider.complete_text(_SYS, user).strip().strip('"')

    def similar_prompts(self, task_type: str, example: str = "", n: int = 3) -> list[str]:
        """n NEW writing prompts of the same task type + difficulty as `example`, different topics."""
        kind = _WRITING_KIND.get(task_type, "a TOEFL writing task")
        user = (
            f"Generate {n} NEW practice prompts, each being {kind} Match the type and difficulty of "
            f"this example but use different topics; make each a complete, self-contained prompt the "
            f"test-taker could answer directly.\n\nExample prompt:\n\"\"\"\n{example or '(none)'}\n\"\"\""
        )
        data = self.provider.complete_json(_SYS, user, _PROMPTS_SCHEMA)
        return [p for p in data.get("prompts", []) if isinstance(p, str)][:n]
