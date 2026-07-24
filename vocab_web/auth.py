"""Minimal single-user gate.

The deployment has a public URL, so without this anyone who finds it could read — and worse,
*write* — the study progress. There are no accounts: one shared passphrase (`PREP_TOKEN`) is
exchanged for a signed, httpOnly cookie. That is proportionate for a single-user study tool;
it is deliberately NOT a general auth system.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import HTTPException, Request

COOKIE = "prep_auth"


def _token() -> str:
    tok = os.environ.get("PREP_TOKEN")
    if not tok:
        raise RuntimeError("PREP_TOKEN is not set (see docs/DEPLOY-VERCEL.md)")
    return tok


def make_cookie() -> str:
    """A deterministic HMAC of the token — the cookie never contains the passphrase itself."""
    secret = _token().encode()
    return hmac.new(secret, b"vocab-web-v1", hashlib.sha256).hexdigest()


def check(password: str) -> bool:
    return hmac.compare_digest(password or "", _token())


def require(request: Request) -> None:
    """FastAPI dependency guarding every /api route except /api/login."""
    if os.environ.get("PREP_AUTH_DISABLED") == "1":      # local dev convenience
        return
    got = request.cookies.get(COOKIE, "")
    if not hmac.compare_digest(got, make_cookie()):
        raise HTTPException(status_code=401, detail="not logged in")
