#!/usr/bin/env python3
"""Mark TOEFL deck words that appear in the real TPO high-frequency list (真题词频信号).

Input: $REAL_DATA_ROOT/tpo_txt/_vocab/tpo_hf_words.txt — text dump of the user's uploaded
【核桃原创】TPO高频词.pdf (≈2400 unique headwords drawn from actual TPO tests). That
exam-attested signal beats generic BNC/COCA rank for a 2-week sprint, so:

  1. every deck word found in the list gets `tpo_hf: true`;
  2. list words missing from the deck are added from full ECDICT (same schema as
     build_vocab.py), tagged tpo_hf + tier via order_vocab rules;
  3. the deck is re-sorted (tier, not tpo_hf, freq) — TPO-attested words first within
     each tier. vocab-srs introduces cards in file order, so this changes study order only.

Proper nouns (TitleCase headwords in the PDF: Mediterranean, Socrates…) are dropped.

Usage:  source env.sh && python scripts/tpo_hf_vocab.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from build_vocab import _exchange, _lines, _senses, _int          # noqa: E402
from order_vocab import _freq, _tier                              # noqa: E402

CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
HF_TXT = CACHE / "official-real" / "tpo_txt" / "_vocab" / "tpo_hf_words.txt"
ECDICT = CACHE / "raw" / "ecdict.csv"
DECK = REPO / "toefl" / "vocab" / "toefl_vocab.json"

IPA = "ɪəɜːʊæɒʌθðʃʒŋɔɑˈˌ'"


def parse_headwords(txt: str) -> list[str]:
    """Headword lines look like '[index] word phonetic…'. Keep lowercase words only —
    TitleCase headwords in this PDF are proper nouns (place/person names)."""
    words: list[str] = []
    for line in txt.splitlines():
        m = re.match(r"^(?:\d+\s+)?([A-Za-z][a-z]+(?:-[a-z]+)?)\s+(\S.*)$", line.strip())
        if not m:
            continue
        w, rest = m.groups()
        pre_cjk = re.split(r"[一-鿿]", rest)[0]
        if not re.search(f"[{IPA}]", pre_cjk):
            continue
        if w[0].isupper():
            continue
        words.append(w.lower())
    seen: set[str] = set()
    return [w for w in words if not (w in seen or seen.add(w))]


def suffix_lemma(w: str, deckset: set[str]) -> str | None:
    for suf, reps in [("ies", ["y"]), ("ically", ["ic", "y"]), ("ally", ["al", ""]),
                      ("ility", ["le", "ility"]), ("es", ["", "e"]), ("s", [""]),
                      ("ied", ["y"]), ("ed", ["", "e"]), ("ing", ["", "e"]),
                      ("ly", [""]), ("ier", ["y"]), ("al", ["", "e"]), ("er", ["", "e"])]:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            for r in reps:
                c = w[: -len(suf)] + r
                if c in deckset:
                    return c
    return None


def main() -> None:
    deck = json.loads(DECK.read_text(encoding="utf-8"))
    deckset = {x["term"].lower() for x in deck}
    hf = parse_headwords(HF_TXT.read_text(encoding="utf-8"))
    print(f"TPO high-frequency headwords (proper nouns dropped): {len(hf)}")

    # inflected form -> deck lemma, from the deck's own ECDICT exchange tables
    form2lemma: dict[str, str] = {}
    for x in deck:
        for v in (x.get("exchange") or {}).values():
            for f in str(v).split("/"):
                f = f.strip().lower()
                if f and f not in deckset:
                    form2lemma.setdefault(f, x["term"].lower())

    matched: set[str] = set()
    missing: list[str] = []
    for w in hf:
        lem = w if w in deckset else form2lemma.get(w) or suffix_lemma(w, deckset)
        (matched.add(lem) if lem else missing.append(w))
    print(f"matched deck lemmas: {len(matched)}   missing from deck: {len(missing)}")

    # full-ECDICT rows for missing words (adds them) and their 0:-lemmas (maps them back)
    csv.field_size_limit(sys.maxsize)
    want = set(missing)
    rows: dict[str, dict] = {}
    with open(ECDICT, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w = row["word"].strip()
            if w.lower() in want and w == w.lower() and w not in rows:
                rows[w] = row

    added, still_missing = [], []
    for w in missing:
        row = rows.get(w)
        if row is None:
            still_missing.append(w)
            continue
        base = (_exchange(row.get("exchange")) or {}).get("0", "").strip().lower()
        if base and base in deckset:          # inflected form of an existing word
            matched.add(base)
            continue
        tr, de = _lines(row.get("translation")), _lines(row.get("definition"))
        if not tr and not de:
            still_missing.append(w)
            continue
        if "人名" in (row.get("translation") or "")[:40]:
            continue
        entry = {
            "term": w,
            "phonetic": (row.get("phonetic") or "").strip(),
            "senses": _senses(de, tr),
            "collins": _int(row.get("collins")),
            "oxford": _int(row.get("oxford")),
            "bnc": _int(row.get("bnc")),
            "frq": _int(row.get("frq")),
            "tags": sorted(set((row.get("tag") or "").split()) | {"tpo"}),
            "exchange": _exchange(row.get("exchange")),
        }
        entry["tier"] = _tier(entry)
        added.append(entry)

    for x in deck:
        if x["term"].lower() in matched:
            x["tpo_hf"] = True
    for e in added:
        e["tpo_hf"] = True
    deck += added

    deck.sort(key=lambda w: (w.get("tier", 2), not w.get("tpo_hf"), _freq(w)))
    DECK.write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")

    n_hf = sum(1 for x in deck if x.get("tpo_hf"))
    from collections import Counter
    tiers = Counter(x["tier"] for x in deck)
    print(f"deck now {len(deck)} words ({len(added)} added); tpo_hf={n_hf}; tiers={dict(tiers)}")
    if still_missing:
        print(f"unresolvable ({len(still_missing)}): {still_missing[:20]}…")


if __name__ == "__main__":
    main()
