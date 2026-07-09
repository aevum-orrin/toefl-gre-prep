"""Pluggable LLM backends behind ONE interface, so the whole app can run on a *free* model by
default yet switch to a paid one with an env var and zero code changes.

    complete_json(system, user, schema) -> dict     # structured scoring output
    complete_text(system, user)         -> str      # free-form (real-time question generation)

Provider is chosen by `LLM_PROVIDER` (gemini | groq | anthropic | offline). If unset, we auto-pick
the first backend whose API key is present, in FREE-FIRST order: gemini -> groq -> anthropic.
`make_provider()` returns None when no real backend is usable (e.g. offline / no keys) — callers
then fall back to their own offline stub.

Cost/privacy notes (2026):
  gemini    Google AI Studio free tier, best free quality. NOTE: free-tier inputs may be used by
            Google to train + seen by human reviewers (except EEA/CH/UK). Key: GEMINI_API_KEY.
  groq      Llama-3.3-70B free tier, ~1s feedback, contractually NO training on your data. Best
            free choice for privacy. Key: GROQ_API_KEY.
  anthropic Claude, best quality, PAID per-token (separate from the Max subscription). Key:
            ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import os
import re

# Free-first auto-detection order.
_AUTO_ORDER = ("gemini", "groq", "anthropic")

_ENV_KEY = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

_DEFAULT_MODEL = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-opus-4-8",
}


class Provider:
    """Base class. Subclasses set .name/.model and implement the two calls."""

    name = "base"

    def __init__(self, model: str):
        self.model = model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        raise NotImplementedError

    def complete_text(self, system: str, user: str) -> str:
        raise NotImplementedError


# --------------------------------------------------------------------------- Gemini
class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(model or os.environ.get("GEMINI_MODEL") or _DEFAULT_MODEL["gemini"])
        from google import genai  # lazy: only imported when actually used
        self._genai = genai
        from google.genai import types
        self._types = types
        self._client = genai.Client(api_key=api_key)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        cfg = self._types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=_gemini_schema(schema),
            temperature=0.2,
        )
        resp = self._client.models.generate_content(model=self.model, contents=user, config=cfg)
        return json.loads(resp.text)

    def complete_text(self, system: str, user: str) -> str:
        cfg = self._types.GenerateContentConfig(system_instruction=system, temperature=0.9)
        resp = self._client.models.generate_content(model=self.model, contents=user, config=cfg)
        return resp.text or ""


# --------------------------------------------------------------------------- Groq
class GroqProvider(Provider):
    name = "groq"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(model or os.environ.get("GROQ_MODEL") or _DEFAULT_MODEL["groq"])
        from groq import Groq  # lazy
        self._client = Groq(api_key=api_key)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        # Groq's json_object mode guarantees valid JSON but not the exact shape, so we pin the
        # shape by appending the schema to the system prompt; the engine coerces with defaults.
        sys = f"{system}\n\nReturn ONLY a JSON object matching this schema:\n{json.dumps(schema)}"
        resp = self._client.chat.completions.create(
            model=self.model, temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        )
        return json.loads(resp.choices[0].message.content)

    def complete_text(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model, temperature=0.9,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


# --------------------------------------------------------------------------- Anthropic
class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(model or _DEFAULT_MODEL["anthropic"])
        from anthropic import Anthropic  # lazy
        self._client = Anthropic(api_key=api_key)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        resp = self._client.messages.create(
            model=self.model, max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": schema}},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        return json.loads(text) if text.lstrip().startswith("{") else _extract_json(text)

    def complete_text(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model, max_tokens=2000, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")


_PROVIDERS = {"gemini": GeminiProvider, "groq": GroqProvider, "anthropic": AnthropicProvider}


def make_provider(name: str | None = None, model: str | None = None,
                  api_key: str | None = None) -> Provider | None:
    """Build the requested provider, or auto-pick the first with a key (free-first).

    Returns None when the caller should fall back to an offline stub: name=='offline',
    an explicit name whose key is missing, or no keys present at all.
    """
    name = (name or os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if name == "offline":
        return None
    if name:  # explicit choice
        cls = _PROVIDERS.get(name)
        if cls is None:
            raise ValueError(f"unknown LLM_PROVIDER '{name}'; choose from {list(_PROVIDERS)} or 'offline'")
        key = api_key or os.environ.get(_ENV_KEY[name])
        return cls(key, model) if key else None
    # auto: first backend whose key is set, in free-first order
    for cand in _AUTO_ORDER:
        key = os.environ.get(_ENV_KEY[cand])
        if key:
            return _PROVIDERS[cand](key, model if cand == name else None)
    return None


def _gemini_schema(schema: dict) -> dict:
    """Gemini's response_schema is an OpenAPI-3.0 subset: it rejects `additionalProperties`.
    Strip it (and recurse) so our strict JSON Schema is accepted."""
    if not isinstance(schema, dict):
        return schema
    out = {k: v for k, v in schema.items() if k != "additionalProperties"}
    if "properties" in out:
        out["properties"] = {k: _gemini_schema(v) for k, v in out["properties"].items()}
    if "items" in out:
        out["items"] = _gemini_schema(out["items"])
    return out


def _extract_json(text: str) -> dict:
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
