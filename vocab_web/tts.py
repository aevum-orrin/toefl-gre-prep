"""Server-side pronunciation via free Microsoft Edge neural voices.

Why server-side at all: the browser's own speechSynthesis is flaky (macOS Chrome drops it with
"canceled"), so the frontend prefers this endpoint and falls back to speechSynthesis only if it
fails. Locally the mp3s were cached on scratch; on Vercel there is no persistent disk, so the
cache is Vercel Blob. A miss costs one edge-tts round trip (~300 ms); a hit is a CDN redirect.

If BLOB_READ_WRITE_TOKEN is absent the endpoint still works — it just synthesizes every time
and streams the bytes back, so a deployment without Blob configured degrades rather than breaks.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

import httpx

try:
    import edge_tts
except ImportError:
    edge_tts = None

VOICES = {
    "usM": "en-US-AndrewNeural",   # relaxed US male (default auto-play)
    "usF": "en-US-AriaNeural",
    "ukM": "en-GB-RyanNeural",
    "ukF": "en-GB-SoniaNeural",
}
BLOB_API = "https://blob.vercel-storage.com"


def blob_key(text: str, voice: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "x"
    return f"tts/{voice}/{stem}_{hashlib.md5(text.encode()).hexdigest()[:8]}.mp3"


async def _blob_lookup(key: str) -> str | None:
    """Return the public URL if this mp3 was already synthesized."""
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        return None
    async with httpx.AsyncClient(timeout=6) as cx:
        r = await cx.get(f"{BLOB_API}/?prefix={key}&limit=1",
                         headers={"authorization": f"Bearer {token}"})
        if r.status_code == 200:
            blobs = r.json().get("blobs") or []
            if blobs and blobs[0].get("pathname") == key:
                return blobs[0].get("url")
    return None


async def _blob_put(key: str, data: bytes) -> str | None:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15) as cx:
        r = await cx.put(f"{BLOB_API}/{key}", content=data,
                         headers={"authorization": f"Bearer {token}",
                                  "x-content-type": "audio/mpeg",
                                  "x-add-random-suffix": "0",
                                  "x-cache-control-max-age": "31536000"})
        if r.status_code in (200, 201):
            return r.json().get("url")
    return None


async def synthesize(text: str, voice: str) -> bytes:
    if edge_tts is None:
        raise RuntimeError("edge-tts not installed")
    tmp = Path(tempfile.mkstemp(suffix=".mp3")[1])
    try:
        await edge_tts.Communicate(text, voice).save(str(tmp))
        return tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
