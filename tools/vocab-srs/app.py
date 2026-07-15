"""vocab-srs: local SM-2 spaced-repetition trainer over big ECDICT-backed decks.

Deck JSON schema (built by scripts/build_vocab.py, enriched by scripts/enrich_vocab.py):
  [{term, phonetic, gloss_en,
    senses:[{pos, def_en[], def_zh[], examples[], collocations[]}],
    collins, oxford, bnc, frq, tags[], exchange{}}]

TOEFL and GRE are two decks (~10k words each) sharing one engine. Scheduling state
persists per deck in data/srs/<deck>.json (gitignored) and is joined to word
content by term.

Card flow (user-specified):
  Enter on FIRST sight        -> known cold, never shown again
  Enter later (no Again ever) -> strong pass + ONE confirmation appearance, then gone
  Enter after any Again       -> refused forever (sticky-Again), counted as "good"
  1/2/3 grades                -> SM-2 day intervals scaled by `prof`, a reward-EMA
                                 proficiency over the card's whole grade history
Ordering: today's Again lapses (once ≥RECENT_GAP other cards passed) → unseen new words
(deck order) → ordinary due reviews. Never-seen words always precede already-seen ones.

Run:  source ../../env.sh && uvicorn app:app --reload --port 8003
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import tempfile
from collections import deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prep_core import SRS, install_idle_shutdown

try:                                     # optional: server-side neural TTS (free MS endpoint)
    import edge_tts
except ImportError:                      # app still works; frontend falls back to browser TTS
    edge_tts = None

HERE = Path(__file__).parent
REPO = HERE.parents[1]
# User records live on scratch (PREP_DATA_DIR, set by env.sh); falls back to home/data for dev.
DATA_DIR = Path(os.environ.get("PREP_DATA_DIR") or REPO / "data") / "srs"

DECK_FILES = {
    "toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
    "gre": REPO / "gre" / "vocab" / "gre_vocab.json",
    # topical scene vocab (listening scenarios, academic subjects, phrase patterns) parsed
    # from the user's uploaded real prep material; built by scripts/fold_scene_vocab.py
    "scenes": REPO / "toefl" / "vocab" / "scene_vocab.json",
}

# Three buttons after Space: 1 Again (repeat in <1 day), 2 Hard (fuzzy), 3 Good (fine).
# "easy" is kept only for backward-compat; the 4th button is gone — a word you know cold
# is handled by Enter-before-reveal (graduate-forever) instead. Values are SM-2 grades.
GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}
DEFAULT_NEW_PER_DAY = 100000  # effectively unlimited: a 2-week sprint needs to blast whole deck

GRADUATED_DUE = "9999-12-31"  # a card marked "known" gets a due so far out it never returns
# A word you once graded "Again" has proven it does not stick. Enter (graduate-forever) is
# therefore REFUSED for it later on — feeling confident today is exactly the short-term
# illusion that makes a word vanish before it is really learned; it is graded "good" instead
# and keeps coming back on the normal expanding schedule. Persisted per deck in <deck>.flags.json.
_FLAGS: dict[str, dict[str, dict]] = {}
# Spacing-effect guard: a just-graded word (esp. "Again", which is due today) must NOT pop
# right back — at least this many other cards are shown in between (memory-research-style
# lag; in-memory only, resets on restart which is harmless).
RECENT_GAP = 15
_RECENT: dict[str, deque] = {}
_CARD_FIELDS = ("ease", "interval", "reps", "due", "prof")
# Per-deck undo/redo stacks (single-user, single-process app). Each record captures a card's
# state before+after an action so Left=undo restores it and Right=redo re-applies it.
_UNDO: dict[str, list[dict]] = {}
_REDO: dict[str, list[dict]] = {}

CONTENT: dict[str, dict[str, dict]] = {}    # deck -> term -> full entry
ORDER: dict[str, list[str]] = {}            # deck -> terms, frequency-sorted
SRS_BY_DECK: dict[str, SRS] = {}


def _gloss(w: dict) -> str:
    """Short gloss stored on the SRS card (fallback only; UI serves from CONTENT)."""
    senses = w.get("senses") or [{}]
    zh = senses[0].get("def_zh") or []
    en = senses[0].get("def_en") or []
    return (zh[0] if zh else (en[0] if en else "")) or ""


def _flags_path(deck: str) -> Path:
    return DATA_DIR / f"{deck}.flags.json"


def _flags(deck: str) -> dict[str, dict]:
    return _FLAGS.setdefault(deck, {})


def _flags_save(deck: str) -> None:
    p = _flags_path(deck)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_FLAGS.get(deck, {}), ensure_ascii=False), encoding="utf-8")


def _term_flags(deck: str, term: str) -> dict:
    return _flags(deck).get(term) or {}


def _term_flags_snap(deck: str, term: str) -> dict | None:
    f = _flags(deck).get(term)
    return dict(f) if f else None


def _term_flags_set(deck: str, term: str, snap: dict | None) -> None:
    if snap:
        _flags(deck)[term] = dict(snap)
    else:
        _flags(deck).pop(term, None)
    _flags_save(deck)


def _load_deck(deck: str) -> None:
    path = DECK_FILES[deck]
    words = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    CONTENT[deck] = {w["term"]: w for w in words}
    ORDER[deck] = [w["term"] for w in words]
    srs = SRS(DATA_DIR / f"{deck}.json")
    for w in words:                          # idempotent: add new terms, keep schedules
        srs.add(w["term"], _gloss(w))
    srs.save()
    SRS_BY_DECK[deck] = srs
    fp = _flags_path(deck)
    _FLAGS[deck] = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}


for _d in DECK_FILES:
    _load_deck(_d)

app = FastAPI(title="Vocab SRS")
# Auto-exit after a long idle stretch so a server forgotten on one shared login node
# frees its port/resources instead of lingering (see prep_core.serverutil).
install_idle_shutdown(app)


class Review(BaseModel):
    deck: str
    term: str
    grade: str                               # again | hard | good | easy


# Personal notes: ONE file for all decks, keyed by term, so a note written while
# studying TOEFL is still there when the same word shows up in the GRE deck.
# Lives with the rest of the user records on scratch ($PREP_DATA_DIR/notes/).
NOTES_PATH = (Path(os.environ.get("PREP_DATA_DIR") or REPO / "data")) / "notes" / "vocab_notes.json"


def _notes_load() -> dict:
    if NOTES_PATH.exists():
        return json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    return {}


def _touch(deck: str, term: str) -> None:
    _RECENT.setdefault(deck, deque(maxlen=RECENT_GAP)).append(term)


def _intro_path(deck: str) -> Path:
    return DATA_DIR / f"{deck}.intro.json"


def _intro_today(deck: str) -> int:
    p = _intro_path(deck)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return data.get(date.today().isoformat(), 0)


def _intro_adjust(deck: str, delta: int) -> None:
    p = _intro_path(deck)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    k = date.today().isoformat()
    data[k] = max(0, data.get(k, 0) + delta)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def _intro_bump(deck: str) -> None:
    _intro_adjust(deck, 1)


def _snap(card) -> dict:
    return {k: getattr(card, k) for k in _CARD_FIELDS}


def _restore(card, snap: dict) -> None:
    for k, v in snap.items():
        setattr(card, k, v)


def _record(deck: str, term: str, before: dict, after: dict, intro_delta: int,
            action: str = "grade", flags_before: dict | None = None,
            flags_after: dict | None = None) -> None:
    """Push an undoable server action. `action` tells the UI what screen to return to when
    undone: a graded card comes back REVEALED (so you can re-grade it), a graduated one comes
    back on its front (Enter is pressed before the reveal). The term's flag entry (sticky-Again,
    Enter-confirmation streak) is snapshotted whole so undo/redo restore it verbatim."""
    _UNDO.setdefault(deck, []).append(
        {"term": term, "before": before, "after": after, "intro_delta": intro_delta,
         "action": action, "flags_before": flags_before, "flags_after": flags_after})
    _REDO[deck] = []  # any fresh action invalidates the redo chain


def _payload(deck: str, term: str, stats: dict, extra: dict | None = None) -> dict:
    """Build a next-card-style response body for a given term (used by /next and /undo)."""
    srs = SRS_BY_DECK[deck]
    card = srs.cards[term]
    kind = "new" if not card.due else "review"
    entry = CONTENT[deck].get(term, {"term": term})
    return {"done": False, "kind": kind, "reps": card.reps, "prof": round(card.prof, 2),
            **entry, **stats,
            "sticky": bool(_term_flags(deck, term).get("again")), **(extra or {})}


def _stats(deck: str, new_per_day: int = DEFAULT_NEW_PER_DAY) -> dict:
    srs = SRS_BY_DECK[deck]
    today = date.today()
    reviews = [c for c in srs.cards.values() if c.due and c.is_due(today)]  # due!="" => seen before
    new_pool = [c for c in srs.cards.values() if not c.due]                 # due=="" => never seen
    new_left = max(0, new_per_day - _intro_today(deck))
    return {"deck": deck, "total": len(srs.cards), "due": len(reviews),
            "new": min(len(new_pool), new_left), "new_pool": len(new_pool),
            "learned": len(srs.cards) - len(new_pool)}


@app.get("/api/decks")
def decks():
    return [_stats(d) for d in DECK_FILES if d in SRS_BY_DECK and CONTENT[d]]


@app.get("/api/next")
def next_card(deck: str = "toefl", new_per_day: int = DEFAULT_NEW_PER_DAY):
    if deck not in SRS_BY_DECK:
        return {"error": f"unknown deck '{deck}'", "decks": list(SRS_BY_DECK)}
    srs = SRS_BY_DECK[deck]
    today = date.today()
    recent = set(_RECENT.get(deck) or ())
    all_due = [c for c in srs.cards.values() if c.due and c.is_due(today)]
    stats = _stats(deck, new_per_day)

    # Priority (user's rule: never-seen words strictly before already-seen ones):
    #   1. today's "Again" lapses whose RECENT_GAP has elapsed — the in-session learning
    #      queue; they MUST interleave soon or grading Again would be meaningless
    #   2. brand-new words (deck order = tiers/TPO-freq), while the daily cap allows
    #   3. ordinary due reviews (yesterday's hard/good, confirmation checks, …)
    # The spacing guard applies throughout: a word graded within the last RECENT_GAP cards
    # is never re-shown unless nothing else is left.
    lapsed = [c for c in all_due if c.interval == 0 and c.term not in recent]
    card, kind = None, None
    if lapsed:
        card, kind = random.choice(lapsed), "review"
    if card is None and stats["new"] > 0:
        for term in ORDER[deck]:             # highest-priority un-introduced word first
            c = srs.cards.get(term)
            if c and not c.due:
                card, kind = c, "new"
                break
    if card is None:
        reviews = [c for c in all_due if c.term not in recent]
        if reviews:
            card, kind = random.choice(reviews), "review"
    if card is None and all_due:
        # nothing but recently-shown cards left: show the least-recently graded one
        # instead of stalling the session
        age = {t: i for i, t in enumerate(_RECENT.get(deck) or ())}
        card, kind = min(all_due, key=lambda c: age.get(c.term, -1)), "review"
    if card is None:
        return {"done": True, **stats}

    entry = CONTENT[deck].get(card.term, {"term": card.term})
    return {"done": False, "kind": kind, "reps": card.reps, "prof": round(card.prof, 2),
            **entry, **stats,
            "sticky": bool(_term_flags(deck, card.term).get("again"))}


@app.post("/api/review")
def review(r: Review):
    srs = SRS_BY_DECK.get(r.deck)
    if srs is None or r.term not in srs.cards:
        return {"error": "unknown deck or term"}
    grade = GRADES.get(r.grade.lower())
    if grade is None:
        return {"error": f"bad grade '{r.grade}'; use {list(GRADES)}"}
    card = srs.cards[r.term]
    before = _snap(card)
    fb = _term_flags_snap(r.deck, r.term)
    was_new = not card.due
    srs.review(r.term, grade)
    tf = dict(fb or {})
    if r.grade.lower() == "again":       # "repeat in <1 day": make it due again today
        card.due = date.today().isoformat()
        card.interval = 0
        tf["again"] = True               # never graduate it via Enter later
    tf.pop("enter", None)                # any manual grade breaks an Enter-confirmation streak
    fa = tf or None
    if fa != fb:
        _term_flags_set(r.deck, r.term, fa)
    srs.save()
    if was_new:
        _intro_bump(r.deck)
    _touch(r.deck, r.term)
    _record(r.deck, r.term, before, _snap(card), 1 if was_new else 0, "grade", fb, fa)
    return {"term": card.term, "interval_days": card.interval, "due": card.due,
            "ease": round(card.ease, 2), "prof": round(card.prof, 2), **_stats(r.deck)}


class DeckTerm(BaseModel):
    deck: str
    term: str


def _graduate(card) -> None:
    card.reps = max(card.reps, 8)
    card.interval = 36500
    card.ease = max(card.ease, 2.6)
    card.due = GRADUATED_DUE
    card.prof = 1.0


@app.post("/api/known")
def known(r: DeckTerm):
    """Enter = "I know it". What it does depends on the card's history (the user's rule:
    only a word confirmed known on FIRST sight may vanish immediately):

    - never seen before        -> graduate forever, never shown again
    - ever graded "Again"      -> graduation refused forever; downgraded to a "good" review
                                  (sticky-Again: a word that once slipped keeps coming back)
    - seen, no Again history   -> 1st Enter: strong pass (grade "easy"), but the word WILL
                                  return once more for confirmation; 2nd consecutive Enter
                                  (no 1/2/3 in between) -> graduate forever."""
    srs = SRS_BY_DECK.get(r.deck)
    if srs is None or r.term not in srs.cards:
        return {"error": "unknown deck or term"}
    card = srs.cards[r.term]
    before = _snap(card)
    fb = _term_flags_snap(r.deck, r.term)
    tf = dict(fb or {})
    was_new = not card.due
    blocked = bool(tf.get("again"))
    confirm = False
    if blocked:
        srs.review(r.term, GRADES["good"])
    elif was_new or tf.get("enter"):     # first-sight Enter, or the confirmation Enter
        _graduate(card)
        tf.pop("enter", None)
    else:                                # first Enter on an already-studied word
        tf["enter"] = True
        srs.review(r.term, GRADES["easy"])
        confirm = True
    fa = tf or None
    if fa != fb:
        _term_flags_set(r.deck, r.term, fa)
    srs.save()
    if was_new:
        _intro_bump(r.deck)
    _touch(r.deck, r.term)
    _record(r.deck, r.term, before, _snap(card), 1 if was_new else 0, "known", fb, fa)
    return {"term": card.term, "known": not blocked and not confirm, "blocked": blocked,
            "confirm": confirm, "due": card.due, "interval_days": card.interval,
            "prof": round(card.prof, 2), **_stats(r.deck)}


class DeckOnly(BaseModel):
    deck: str


@app.post("/api/undo")
def undo(r: DeckOnly):
    """Undo the last SERVER action (a grade or a graduate) and hand the card back.

    The UI drives the sequence: it also tracks the reveal step, which is pure UI state, so
    pressing ← after a grade lands you back on that word's answer screen (re-grade it), and
    pressing ← again lands you on its front. `action` tells the UI which screen to draw."""
    stack = _UNDO.get(r.deck) or []
    if not stack:
        return {"none": True, **_stats(r.deck)}
    rec = stack.pop()
    srs = SRS_BY_DECK[r.deck]
    _restore(srs.cards[rec["term"]], rec["before"])
    srs.save()
    if rec["intro_delta"]:
        _intro_adjust(r.deck, -rec["intro_delta"])
    if rec.get("flags_before") != rec.get("flags_after"):
        _term_flags_set(r.deck, rec["term"], rec.get("flags_before"))
    buf = _RECENT.get(r.deck)
    if buf and buf[-1] == rec["term"]:
        buf.pop()
    _REDO.setdefault(r.deck, []).append(rec)
    return _payload(r.deck, rec["term"], _stats(r.deck),
                    {"undone": True, "action": rec.get("action", "grade")})


@app.post("/api/redo")
def redo(r: DeckOnly):
    """Cancel the undo — re-apply the action."""
    stack = _REDO.get(r.deck) or []
    if not stack:
        return {"none": True, **_stats(r.deck)}
    rec = stack.pop()
    srs = SRS_BY_DECK[r.deck]
    _restore(srs.cards[rec["term"]], rec["after"])
    srs.save()
    if rec["intro_delta"]:
        _intro_adjust(r.deck, rec["intro_delta"])
    if rec.get("flags_before") != rec.get("flags_after"):
        _term_flags_set(r.deck, rec["term"], rec.get("flags_after"))
    _touch(r.deck, rec["term"])
    _UNDO.setdefault(r.deck, []).append(rec)
    return {"ok": True, "action": rec.get("action", "grade"), **_stats(r.deck)}


# Server-side pronunciation: free Microsoft Edge neural voices (edge-tts). The browser's own
# speechSynthesis is flaky (macOS Chrome "canceled" bug) and unavailable in VNC sessions, so
# the frontend prefers this endpoint and falls back to speechSynthesis only if it fails.
# mp3s are tiny (~6 KB/word) and cached forever on scratch: $LANG_PREP_CACHE/tts/<voice>/.
TTS_DIR = Path(os.environ.get("LANG_PREP_CACHE") or REPO / "data" / "cache") / "tts"
TTS_VOICES = {
    "usM": "en-US-AndrewNeural",   # relaxed US male (default auto-play)
    "usF": "en-US-AriaNeural",
    "ukM": "en-GB-RyanNeural",
    "ukF": "en-GB-SoniaNeural",
}


@app.get("/api/tts")
async def tts(text: str, slot: str = "usM"):
    text = " ".join(text.split())[:200]
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    if edge_tts is None:
        return JSONResponse({"error": "edge-tts not installed"}, status_code=501)
    voice = TTS_VOICES.get(slot, TTS_VOICES["usM"])
    stem = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "x"
    path = TTS_DIR / voice / f"{stem}_{hashlib.md5(text.encode()).hexdigest()[:8]}.mp3"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".part", dir=path.parent)
        os.close(fd)
        try:
            await edge_tts.Communicate(text, voice).save(tmp)
            os.replace(tmp, path)        # atomic: concurrent requests never see partial files
        except Exception as ex:
            Path(tmp).unlink(missing_ok=True)
            return JSONResponse({"error": f"tts failed: {str(ex)[:150]}"}, status_code=502)
    return FileResponse(path, media_type="audio/mpeg",
                        headers={"Cache-Control": "max-age=31536000, immutable"})


class Note(BaseModel):
    term: str
    md: str = ""


@app.get("/api/note")
def get_note(term: str):
    rec = _notes_load().get(term) or {}
    return {"term": term, "md": rec.get("md", ""), "updated": rec.get("updated", "")}


@app.post("/api/note")
def put_note(n: Note):
    data = _notes_load()
    if n.md.strip():
        data[n.term] = {"md": n.md, "updated": date.today().isoformat()}
    else:
        data.pop(n.term, None)              # emptying the box deletes the note
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "term": n.term, "has": bool(n.md.strip())}


@app.get("/api/search")
def search(deck: str, q: str, limit: int = 60):
    """Contiguous-substring lookup over the CURRENT deck only (e.g. q=sub ->
    subsequent, submarine...). Prefix matches first, then deck (frequency) order."""
    q = q.strip().lower()
    if deck not in CONTENT or len(q) < 2:
        return {"q": q, "hits": [], "total": 0}
    hits = []
    for term in ORDER[deck]:
        tl = term.lower()
        if q in tl:
            e = CONTENT[deck][term]
            senses = e.get("senses") or [{}]
            zh = (senses[0].get("def_zh") or [""])[0]
            hits.append({"term": term, "zh": zh, "tier": e.get("tier"),
                         "starts": tl.startswith(q)})
    hits.sort(key=lambda h: not h["starts"])  # stable: keeps freq order within groups
    return {"q": q, "hits": hits[:limit], "total": len(hits)}


@app.get("/api/entry")
def entry(deck: str, term: str):
    """Full card payload for a searched word, so the UI can open it as a study page.
    Grading it goes through the normal /api/review and thus counts toward today."""
    if deck not in CONTENT or term not in CONTENT[deck]:
        return {"error": "unknown deck or term"}
    return _payload(deck, term, _stats(deck))


@app.get("/")
def index():
    # no-cache: always revalidate, so a stale cached page can never run outdated JS
    return FileResponse(HERE / "static" / "index.html",
                        headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
