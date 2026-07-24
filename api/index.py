"""Vercel entry point. @vercel/python serves the ASGI `app` object found here."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vocab_web.app import app  # noqa: E402,F401
