#!/usr/bin/env python3
"""Build TOEFL/GRE vocab decks from the ECDICT open dictionary.

ECDICT (github skywind3000/ECDICT) CSV columns:
    word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio

We filter rows whose `tag` field contains 'toefl' / 'gre' and emit a rich
backbone entry. ECDICT's own `pos` column is often empty, so we recover parts of
speech from the leading token of each definition / translation line
("n. ...", "vt. ...", "aux. ...") and group them into per-POS `senses` — this is
exactly the hierarchy the UI expands (one dropdown per POS). Example sentences
and collocations are filled later by scripts/enrich_vocab.py; here they start
empty.

Reads ECDICT from the scratch cache, writes candidate decks to scratch/build so
size/quality can be inspected before promoting into the repo.
"""
import csv, json, re, sys
from pathlib import Path
from collections import Counter, OrderedDict

CACHE = Path("/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
SRC = CACHE / "raw" / "ecdict.csv"
OUT = CACHE / "build"
OUT.mkdir(parents=True, exist_ok=True)

WORD_RE = re.compile(r"^[a-z][a-z'\-]{1,}$")  # single lowercase headword, len>=2

# Which ECDICT exam tags make up each deck. TOEFL/GRE proper are small-ish (~7k), so we widen
# each deck to the neighbouring academic-exam lists (IELTS, 考研/ky) to reach the comprehensive
# ~10k the user wants (incl. harder / rarer words). Every card still shows its tags, so the source
# of each word stays visible. Counts: toefl∪ielts∪ky ≈ 9927, gre∪ky ≈ 10526.
DECK_TAGS = {
    "toefl": {"toefl", "ielts", "ky"},
    "gre": {"gre", "ky"},
}

# leading part-of-speech token -> display name (covers EN WordNet + ZH CN-dict styles)
POS_MAP = {
    "n": "noun", "v": "verb", "vt": "verb", "vi": "verb", "vbl": "verb",
    "adj": "adjective", "a": "adjective", "j": "adjective", "s": "adjective",
    "adv": "adverb", "ad": "adverb", "r": "adverb",
    "aux": "auxiliary", "modal": "auxiliary",
    "prep": "preposition", "conj": "conjunction", "pron": "pronoun",
    "art": "article", "det": "determiner", "num": "numeral",
    "int": "interjection", "interj": "interjection", "abbr": "abbreviation",
}
POS_ORDER = ["noun", "verb", "adjective", "adverb", "auxiliary", "pronoun",
             "preposition", "conjunction", "article", "determiner", "numeral",
             "interjection", "abbreviation", ""]

_DOMAIN = re.compile(r"^\[[^\]]*\]\s*")          # "[计] ", "[网络] "
_POSTOK = re.compile(r"^([a-zA-Z]{1,6})\.\s+")   # "n. ", "vt. ", "aux. "


def _lines(s):
    """ECDICT stores multi-sense fields with literal '\\n' separators."""
    s = (s or "").replace("\\n", "\n")
    return [x.strip() for x in s.split("\n") if x.strip()]


def _int(s, d=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return d


def _split_pos(line):
    """('n. a container' | 'vt. 装罐') -> (display_pos, text). Domain tags -> ('', text)."""
    line = line.strip()
    m = _DOMAIN.match(line)
    if m:
        return "", line[m.end():].strip()
    m = _POSTOK.match(line)
    if m:
        tok = m.group(1).lower()
        return POS_MAP.get(tok, ""), line[m.end():].strip()
    return "", line


def _senses(def_lines, tr_lines):
    """Group EN definitions + ZH translations by recovered POS, EN order first."""
    en, zh, order = OrderedDict(), OrderedDict(), []

    def add(store, lines):
        for ln in lines:
            pos, txt = _split_pos(ln)
            if not txt:
                continue
            store.setdefault(pos, []).append(txt)
            if pos not in order:
                order.append(pos)

    add(en, def_lines)
    add(zh, tr_lines)
    order.sort(key=lambda p: POS_ORDER.index(p) if p in POS_ORDER else len(POS_ORDER))
    return [
        {"pos": p, "def_en": en.get(p, []), "def_zh": zh.get(p, []),
         "examples": [], "collocations": []}
        for p in order
    ]


def _exchange(s):
    out = {}
    for part in (s or "").split("/"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k and v:
                out[k] = v
    return out


def build():
    csv.field_size_limit(sys.maxsize)
    decks = {"toefl": [], "gre": []}
    tag_counts = Counter()
    total = 0
    with open(SRC, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            tags = set((row.get("tag") or "").split())
            tag_counts.update(tags)
            if not any(tags & wanted for wanted in DECK_TAGS.values()):
                continue
            word = (row.get("word") or "").strip()
            if not WORD_RE.match(word):
                continue
            tr = _lines(row.get("translation"))
            de = _lines(row.get("definition"))
            if not tr and not de:
                continue
            entry = {
                "term": word,
                "phonetic": (row.get("phonetic") or "").strip(),
                "senses": _senses(de, tr),
                "collins": _int(row.get("collins")),
                "oxford": _int(row.get("oxford")),
                "bnc": _int(row.get("bnc")),
                "frq": _int(row.get("frq")),
                "tags": sorted(tags),
                "exchange": _exchange(row.get("exchange")),
            }
            for deck, wanted in DECK_TAGS.items():
                if tags & wanted:
                    decks[deck].append(entry)

    def freq_key(e):
        f = e["frq"] or e["bnc"] or 0
        return (f == 0, f)  # ranked words first (ascending), unranked last

    for deck in decks.values():
        deck.sort(key=freq_key)
    return decks, tag_counts, total


def main():
    decks, tag_counts, total = build()
    for deck, items in decks.items():
        path = OUT / f"{deck}_backbone.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1))
        print(f"{deck}: {len(items):>6} words  ->  {path.name}  ({path.stat().st_size/1e6:.1f} MB)")

    print(f"\nscanned {total} ECDICT rows.  exam-tag counts (accurate):")
    for t in ("toefl", "gre", "ielts", "ky", "cet6"):
        print(f"  {t:6}: {tag_counts.get(t, 0)}")

    for probe in ("utilize", "abandon", "run"):
        hit = next((e for e in decks["toefl"] if e["term"] == probe), None) \
            or next((e for e in decks["gre"] if e["term"] == probe), None)
        if hit:
            print(f"\nsample: {probe}")
            print(json.dumps(hit, ensure_ascii=False, indent=2))
            break


if __name__ == "__main__":
    main()
