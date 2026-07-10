#!/usr/bin/env python3
"""Generate fresh Reading/Listening practice items with a FREE LLM (Groq/Gemini),
matching the exact 2026-TOEFL task schema, and drop them into the scratch rl_gen/
dir where scripts/merge_rl.py folds them into the canonical per-kind files.

This is the hands-off VOLUME top-up: a scheduled job (scripts/gen_cron.sh) calls it
for one task kind at a time, staggered through the day so no single API burst trips
the free-tier rate limit. High-quality seed items are still authored by Claude/Opus;
this just keeps the bank growing between sessions.

Every generated item is auto-scored MCQ (objective), so free-tier quality is fine.
Ids are unique per run (kind + short run tag + index); merge_rl dedups by id anyway.

Usage:
  python scripts/gen_bank.py academic_passage --n 6 --provider groq
  python scripts/gen_bank.py conversation --n 4
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "prep-core" / "src"))
from prep_core import load_env, make_provider  # noqa: E402

GEN = Path("/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache/rl_gen")

# The small real-question set can't span every field TOEFL draws on, so AI items must cover
# ALL of them. Each run targets a rotating domain (by day-of-year) so daily scheduled runs
# systematically sweep the whole taxonomy over ~a month, generating a deep batch per domain.
DOMAINS = [
    "cell biology", "genetics & heredity", "ecology & ecosystems", "evolution & natural selection",
    "botany & plant science", "zoology & animal behavior", "marine biology", "microbiology",
    "human physiology & anatomy", "neuroscience", "astronomy & cosmology", "planetary science",
    "geology & plate tectonics", "meteorology & climate", "oceanography", "chemistry",
    "physics & mechanics", "environmental science & conservation", "paleontology & fossils",
    "anthropology & human origins", "archaeology & ancient civilizations", "art history & painting",
    "architecture", "music history & theory", "literature & literary movements", "linguistics",
    "psychology & cognition", "sociology & social structures", "economics & markets",
    "business & management", "political science & government", "ancient history (Greece/Rome/Egypt)",
    "medieval history", "modern & world history", "US history", "philosophy & ethics",
    "education & learning", "technology & engineering", "medicine & public health",
    "agriculture & food science", "geography & cartography", "photography & film",
    "energy & materials science", "transportation & infrastructure",
]


def _domain_for(index: int) -> str:
    return DOMAINS[index % len(DOMAINS)]

# kind -> (section, body_field, n_questions, description used to steer the model)
KINDS = {
    "academic_passage": ("reading", "passage", 4,
        "a 320-450 word academic passage on a science/history/social-science topic "
        "(the kind of expository text used on the TOEFL reading section), factually accurate"),
    "daily_life": ("reading", "passage", 4,
        "a 200-320 word practical/campus text (notice, email, syllabus excerpt, review, "
        "instructions) of the everyday-reading type on the new TOEFL"),
    "complete_words": ("reading", "passage", 3,
        "a 150-220 word passage with THREE gaps written as '_____'; each question asks which "
        "word best completes one gap, testing academic vocabulary in context"),
    "academic_talk": ("listening", "transcript", 4,
        "a 300-450 word single-speaker academic lecture transcript (natural spoken style, "
        "with an example or aside), on a science/humanities topic"),
    "conversation": ("listening", "transcript", 4,
        "a two-speaker campus conversation transcript (student with an advisor, librarian, "
        "professor, or staff) of 300-450 words, natural spoken style, labelled speaker turns"),
    "announcement": ("listening", "transcript", 4,
        "a 150-250 word single-speaker announcement or short talk (campus notice, tour, "
        "orientation) in natural spoken style"),
    "choose_response": ("listening", "transcript", 1,
        "ONE short line of natural spoken English (a question, request, or remark); the single "
        "question is 'Choose the best response.' with four candidate replies, exactly one of "
        "which is the natural, cooperative continuation"),
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "q": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "answer": {"type": "integer"},
                                "explanation": {"type": "string"},
                            },
                            "required": ["q", "options", "answer", "explanation"],
                        },
                    },
                },
                "required": ["title", "body", "questions"],
            },
        }
    },
    "required": ["items"],
}


def _system(kind: str) -> str:
    _, _, nq, desc = KINDS[kind]
    return (
        "You are a professional TOEFL item writer producing practice questions for the 2026 "
        f"format. Generate distinct, high-quality items. For each item write {desc}. "
        f"Then write exactly {nq} multiple-choice question(s), each with 4 options, exactly one "
        "correct, and a one-sentence explanation of why the key is right and the others wrong. "
        "'answer' is the 0-based index of the correct option. Put the passage/lecture/line text "
        "in the 'body' field. Vary topics; do NOT reuse the titles listed as already-used. "
        "Return ONLY JSON per the schema."
    )


def _existing_titles(kind: str) -> list[str]:
    section, _, _, _ = KINDS[kind]
    titles: list[str] = []
    sdir = REPO / "toefl" / section
    for f in sdir.glob("*.json"):
        try:
            for it in json.loads(f.read_text(encoding="utf-8")):
                if it.get("kind") == kind and it.get("title"):
                    titles.append(it["title"])
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return titles


def _run_tag() -> str:
    """Filesystem-safe unique-ish tag from the wall clock (avoids id collisions across runs)."""
    return time.strftime("%m%d%H%M%S")


def generate(kind: str, n: int, provider: str | None, sleep: float,
             domain: str | None = None) -> None:
    if kind not in KINDS:
        print(f"unknown kind '{kind}'; choose from {list(KINDS)}")
        return
    section, field, nq, _ = KINDS[kind]
    prov = make_provider(provider)
    if prov is None:
        print("No LLM provider (set GEMINI_API_KEY / GROQ_API_KEY in .env).")
        return

    # Academic kinds get a domain focus (rotating daily) so the bank sweeps every TOEFL field;
    # campus/everyday kinds don't map to an academic domain, so they just stay varied.
    academic = kind in ("academic_passage", "academic_talk")
    focus = (domain or _domain_for(time.localtime().tm_yday)) if academic else None

    used = _existing_titles(kind)
    user = (
        f"Generate {n} NEW '{kind}' items. Already-used titles (avoid these and near-duplicates):\n"
        + json.dumps(used[-120:], ensure_ascii=False)
        + (f"\nAll items in this batch must be on the academic domain: **{focus}**. Vary the "
           "specific subtopics within that domain; be factually accurate and university-level."
           if focus else "")
        + "\nReturn JSON per the schema."
    )
    tag_msg = f" [domain: {focus}]" if focus else ""
    print(f"[{kind}] generating {n} via {prov.name}/{prov.model}; {len(used)} existing titles{tag_msg}")
    try:
        out = prov.complete_json(_system(kind), user, _SCHEMA)
    except Exception as ex:
        print(f"  FAILED ({type(ex).__name__}: {str(ex)[:100]})")
        return

    tag = _run_tag()
    items, kept = [], 0
    for i, raw in enumerate(out.get("items", [])):
        body = (raw.get("body") or "").strip()
        qs = raw.get("questions") or []
        if not body or not qs:
            continue
        clean_qs = []
        for q in qs:
            opts = q.get("options")
            if not q.get("q") or not isinstance(opts, list) or len(opts) < 2:
                continue
            if not isinstance(q.get("answer"), int) or not (0 <= q["answer"] < len(opts)):
                continue
            clean_qs.append({"q": q["q"], "options": opts,
                             "answer": q["answer"], "explanation": q.get("explanation", "")})
        if not clean_qs:
            continue
        items.append({
            "id": f"gen_{kind}_{tag}_{i:02d}",
            "kind": kind,
            "title": (raw.get("title") or f"{kind} {i}").strip(),
            field: body,
            "questions": clean_qs,
            "source": "ai",   # AI 练习题 (real ETS/TPO items are tagged "real")
        })
        kept += 1

    if not items:
        print("  nothing valid generated")
        return
    GEN.mkdir(parents=True, exist_ok=True)
    outfile = GEN / f"gen_{kind}_{tag}.json"
    outfile.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  wrote {kept} items -> {outfile.name} (run scripts/merge_rl.py to fold in)")
    time.sleep(sleep)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=list(KINDS))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--provider", default=None, help="gemini|groq|anthropic (default free-first)")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--domain", default=None,
                    help="academic-domain focus (default: rotate by day-of-year across all domains)")
    args = ap.parse_args()
    load_env(REPO / ".env")
    generate(args.kind, args.n, args.provider, args.sleep, args.domain)


if __name__ == "__main__":
    main()
