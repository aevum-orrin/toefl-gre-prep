"""FastAPI app for the Vercel deployment of vocab-srs.

Same 12 endpoints and same study semantics as tools/vocab-srs/app.py; the differences are all
forced by serverless (see docs/superpowers/specs/2026-07-24-vocab-web-vercel-design.md):
  - deck + progress come from Postgres instead of memory/JSON files
  - the 15-card spacing buffer arrives as `exclude` from the client instead of a process global
  - undo/redo stacks live in a table instead of process globals
  - a passphrase cookie guards the public URL
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, sm2, store, tts
from .store import DEFAULT_NEW_PER_DAY

STATIC = Path(__file__).parent.parent / "static"

app = FastAPI(title="Vocab SRS (web)")
guard = Depends(auth.require)


class Review(BaseModel):
    deck: str
    term: str
    grade: str


class DeckTerm(BaseModel):
    deck: str
    term: str


class DeckOnly(BaseModel):
    deck: str


class Note(BaseModel):
    term: str
    md: str = ""


class Login(BaseModel):
    password: str


def _split(exclude: str | None) -> list[str]:
    return [t for t in (exclude or "").split(",") if t]


def _payload(deck: str, card: dict, kind: str, stats: dict, extra: dict | None = None) -> dict:
    """Merge the deck entry with the card's schedule — the shape the frontend expects."""
    entry = store.entry(deck, card["term"]) or {"term": card["term"]}
    flags = card.get("flags") or {}
    return {"done": False, "kind": kind, "reps": card["reps"], "prof": round(card["prof"], 2),
            **entry, **stats, "sticky": bool(flags.get("again")), **(extra or {})}


# ------------------------------------------------------------------ auth

@app.post("/api/login")
def login(body: Login, request: Request, response: Response):
    if not auth.check(body.password):
        return JSONResponse({"error": "wrong password"}, status_code=401)
    # Secure only over https (always true on Vercel, which terminates TLS and sets
    # x-forwarded-proto). Marking it secure on a plain-http local run would make the browser
    # discard the cookie, so the app would be untestable outside the deployment.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    response.set_cookie(auth.COOKIE, auth.make_cookie(), httponly=True,
                        secure=(proto == "https"),
                        samesite="lax", max_age=60 * 60 * 24 * 365)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    try:
        auth.require(request)
        return {"authed": True}
    except Exception:
        return {"authed": False}


# ------------------------------------------------------------------ study

@app.get("/api/decks", dependencies=[guard])
def decks():
    return [store.stats(d) for d in store.decks()]


@app.get("/api/next", dependencies=[guard])
def next_card(deck: str = "toefl", new_per_day: int = DEFAULT_NEW_PER_DAY,
              exclude: str | None = None):
    card, kind = store.pick_next(deck, new_per_day, _split(exclude))
    st = store.stats(deck, new_per_day)
    if card is None:
        return {"done": True, **st}
    return _payload(deck, card, kind, st)


@app.post("/api/review", dependencies=[guard])
def review(r: Review):
    card = store.get_card(r.deck, r.term)
    if card is None:
        return {"error": "unknown deck or term"}
    grade = sm2.GRADES.get(r.grade.lower())
    if grade is None:
        return {"error": f"bad grade '{r.grade}'; use {list(sm2.GRADES)}"}
    before, fb = sm2.snapshot(card), dict(card.get("flags") or {})
    was_new = not card["due"]
    sm2.review(card, grade)
    tf = dict(fb)
    if r.grade.lower() == "again":        # "repeat in <1 day": make it due again today
        card["due"] = date.today().isoformat()
        card["interval"] = 0
        tf["again"] = True                # sticky: never graduate it via Enter later
    tf.pop("enter", None)                 # any manual grade breaks an Enter-confirmation streak
    store.save_card(r.deck, card, tf)
    if was_new:
        store.intro_adjust(r.deck, 1)
    store.push_action(r.deck, {"term": r.term, "before": before, "after": sm2.snapshot(card),
                               "intro_delta": 1 if was_new else 0, "action": "grade",
                               "flags_before": fb or None, "flags_after": tf or None})
    return {"term": card["term"], "interval_days": card["interval"], "due": card["due"],
            "ease": round(card["ease"], 2), "prof": round(card["prof"], 2),
            **store.stats(r.deck)}


@app.post("/api/known", dependencies=[guard])
def known(r: DeckTerm):
    """Enter = "I know it", with the user's history-dependent rules:
    never seen -> graduate forever · ever graded Again -> refused (downgraded to a good review)
    · seen without Again -> one confirmation round, second consecutive Enter graduates."""
    card = store.get_card(r.deck, r.term)
    if card is None:
        return {"error": "unknown deck or term"}
    before, fb = sm2.snapshot(card), dict(card.get("flags") or {})
    tf = dict(fb)
    was_new = not card["due"]
    blocked = bool(tf.get("again"))
    confirm = False
    if blocked:
        sm2.review(card, sm2.GRADES["good"])
    elif was_new or tf.get("enter"):
        sm2.graduate(card)
        tf.pop("enter", None)
    else:
        tf["enter"] = True
        sm2.review(card, sm2.GRADES["easy"])
        confirm = True
    store.save_card(r.deck, card, tf)
    if was_new:
        store.intro_adjust(r.deck, 1)
    store.push_action(r.deck, {"term": r.term, "before": before, "after": sm2.snapshot(card),
                               "intro_delta": 1 if was_new else 0, "action": "known",
                               "flags_before": fb or None, "flags_after": tf or None})
    return {"term": card["term"], "known": not blocked and not confirm, "blocked": blocked,
            "confirm": confirm, "due": card["due"], "interval_days": card["interval"],
            "prof": round(card["prof"], 2), **store.stats(r.deck)}


@app.post("/api/undo", dependencies=[guard])
def undo(r: DeckOnly):
    rec = store.pop_undo(r.deck)
    if rec is None:
        return {"none": True, **store.stats(r.deck)}
    card = store.get_card(r.deck, rec["term"])
    sm2.restore(card, rec["before"])
    store.save_card(r.deck, card, rec.get("flags_before") or {})
    if rec.get("intro_delta"):
        store.intro_adjust(r.deck, -rec["intro_delta"])
    card["flags"] = rec.get("flags_before") or {}
    return _payload(r.deck, card, "new" if not card["due"] else "review", store.stats(r.deck),
                    {"undone": True, "action": rec.get("action", "grade")})


@app.post("/api/redo", dependencies=[guard])
def redo(r: DeckOnly):
    rec = store.pop_redo(r.deck)
    if rec is None:
        return {"none": True, **store.stats(r.deck)}
    card = store.get_card(r.deck, rec["term"])
    sm2.restore(card, rec["after"])
    store.save_card(r.deck, card, rec.get("flags_after") or {})
    if rec.get("intro_delta"):
        store.intro_adjust(r.deck, rec["intro_delta"])
    return {"ok": True, "action": rec.get("action", "grade"), **store.stats(r.deck)}


# ------------------------------------------------------------------ lookup / notes

@app.get("/api/search", dependencies=[guard])
def search(deck: str, q: str, limit: int = 60):
    return store.search(deck, q, limit)


@app.get("/api/entry", dependencies=[guard])
def entry(deck: str, term: str):
    card = store.get_card(deck, term)
    if card is None:
        return {"error": "unknown deck or term"}
    kind = "new" if not card["due"] else "review"
    return _payload(deck, card, kind, store.stats(deck))


@app.get("/api/note", dependencies=[guard])
def get_note(term: str):
    return store.get_note(term)


@app.post("/api/note", dependencies=[guard])
def put_note(n: Note):
    store.set_note(n.term, n.md)
    return {"ok": True, "term": n.term, "has": bool(n.md.strip())}


# ------------------------------------------------------------------ tts

@app.get("/api/tts", dependencies=[guard])
async def tts_route(text: str, slot: str = "usM"):
    text = " ".join(text.split())[:200]
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    voice = tts.VOICES.get(slot, tts.VOICES["usM"])
    key = tts.blob_key(text, voice)
    hit = await tts._blob_lookup(key)
    if hit:
        return RedirectResponse(hit, status_code=307)
    try:
        data = await tts.synthesize(text, voice)
    except Exception as ex:
        return JSONResponse({"error": f"tts failed: {str(ex)[:150]}"}, status_code=502)
    url = await tts._blob_put(key, data)
    if url:
        return RedirectResponse(url, status_code=307)
    return Response(data, media_type="audio/mpeg",
                    headers={"Cache-Control": "max-age=31536000, immutable"})


# ------------------------------------------------------------------ static

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/login")
def login_page():
    return FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-cache"})


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
