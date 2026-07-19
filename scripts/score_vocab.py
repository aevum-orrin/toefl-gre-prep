#!/usr/bin/env python3
"""Machine-checkable completeness score (0-100) for a vocab deck + the vocab-srs app.

This is the METER for the completeness loop (docs/vocab-loop.md): each iteration runs this,
fixes the lowest-scoring dimension, and re-runs. Stop at >=95 or after 10 iterations. The
score must be reproducible from data + a running server — never a subjective judgement.

Dimensions (max points):
  D1 发音 Pronunciation   18   ipa_us 7 · ipa_uk 5 · any-phonetic 2 · live TTS sample 4
  D2 释义与例句 Senses     30   gloss_en 5 · pos 4 · def_en 6 · def_zh 5 · example 6 · colloc>=2 4
  D3 词根词缀词源          17   resolved (has etymology OR cached useful=false) 14 · 3-field 3
  D4 结构一致性            10   schema 3 · no-dup 2 · no empty-shell sense 3 · no mojibake 2
  D5 学习元数据            10   tier 3 · tpo_hf>=1500 2 · verb exchange 3 · freq|bnc 2
  D6 App 功能 (live)       15   read APIs 4 · write+undo round-trip 2 · frontend e2e 6 · latency 3

Live checks (D6, and the TTS item of D1) need a running server via --url. NEVER point
--allow-write or --e2e at the real 8003 you study on: they grade words. Use a throwaway
server started on a temp PREP_DATA_DIR (see docs/vocab-loop.md for the exact command).

Usage:
  .venv/bin/python scripts/score_vocab.py toefl                     # offline data only
  .venv/bin/python scripts/score_vocab.py toefl --url http://127.0.0.1:8097 --allow-write --e2e
Writes data/vocab_score_<deck>.json (gitignored) and prints a per-item table.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DECKS = {"toefl": REPO / "toefl" / "vocab" / "toefl_vocab.json",
         "gre": REPO / "gre" / "vocab" / "gre_vocab.json"}
CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")


def _get(url: str, timeout: float = 15):
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except Exception:
        return 0, b"", time.time() - t0


def _post(url: str, body: dict, timeout: float = 15) -> int:
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception:
        return 0


class Scorecard:
    def __init__(self):
        self.dims: dict[str, dict] = {}

    def add(self, dim, name, pts, frac, note=""):
        got = round(pts * max(0.0, min(1.0, frac)), 2)
        d = self.dims.setdefault(dim, {"items": [], "got": 0.0, "max": 0.0})
        d["items"].append({"name": name, "pts": pts, "got": got, "note": note})
        d["got"] = round(d["got"] + got, 2)
        d["max"] += pts

    @property
    def total(self):
        return round(sum(d["got"] for d in self.dims.values()), 1)


def score(deck, url, allow_write, e2e, node):
    words = json.loads(DECKS[deck].read_text(encoding="utf-8"))
    n = len(words)
    senses = [s for w in words for s in (w.get("senses") or [])]
    ns = max(1, len(senses))
    sc = Scorecard()

    # ---------- D1 发音 ----------
    sc.add("D1 发音", "ipa_us", 7, sum(1 for w in words if w.get("ipa_us")) / n)
    sc.add("D1 发音", "ipa_uk", 5, sum(1 for w in words if w.get("ipa_uk")) / n)
    none_ph = sum(1 for w in words
                  if not w.get("ipa_us") and not w.get("ipa_uk") and not w.get("phonetic"))
    sc.add("D1 发音", "any-phonetic", 2, 1 - none_ph / n, f"{none_ph} words with no phonetic")
    if url:
        # bounded: 6 samples × 8 s cap, so a compute node with no outbound internet (edge-tts
        # 502s there) fails fast instead of hanging the whole score. Run the loop on a LOGIN
        # node if this scores 0 — TTS synthesis needs outbound internet.
        sample = random.Random(7).sample([w["term"] for w in words], 6)
        okc = sum(1 for t in sample
                  if _get(f"{url}/api/tts?text={urllib.parse.quote(t)}&slot=usM", 8)[0] == 200)
        sc.add("D1 发音", "tts-live (6 samples)", 4, okc / 6,
               "" if okc else "all failed — likely a compute node with no outbound internet")
    else:
        sc.add("D1 发音", "tts-live", 4, 0, "SKIPPED: no --url")

    # ---------- D2 释义与例句 ----------
    sc.add("D2 释义例句", "gloss_en", 5, sum(1 for w in words if w.get("gloss_en")) / n)
    sc.add("D2 释义例句", "sense.pos", 4, sum(1 for s in senses if (s.get("pos") or "").strip()) / ns)
    sc.add("D2 释义例句", "sense.def_en", 6, sum(1 for s in senses if s.get("def_en")) / ns)
    sc.add("D2 释义例句", "sense.def_zh", 5, sum(1 for s in senses if s.get("def_zh")) / ns)
    sc.add("D2 释义例句", "sense.example", 6, sum(1 for s in senses if s.get("examples")) / ns)
    sc.add("D2 释义例句", "sense.colloc>=2", 4,
           sum(1 for s in senses if len(s.get("collocations") or []) >= 2) / ns)

    # ---------- D3 词根词缀词源 ----------
    have = sum(1 for w in words if w.get("etymology"))
    not_useful = 0
    cdir = CACHE / "enrich_etym" / deck
    if cdir.exists():
        for f in cdir.iterdir():
            try:
                if not json.loads(f.read_text()).get("useful"):
                    not_useful += 1
            except Exception:
                pass
    sc.add("D3 词源", "resolved (etymology or judged-none)", 14, (have + not_useful) / n,
           f"{have} have + {not_useful} judged-not-useful / {n}")
    et = [w["etymology"] for w in words if w.get("etymology")]
    full = sum(1 for e in et if e.get("breakdown") and e.get("story") and e.get("origin"))
    sc.add("D3 词源", "3-field fullness", 3, full / max(1, len(et)))

    # ---------- D4 结构一致性 ----------
    schema_ok = sum(1 for w in words if w.get("term") and w.get("senses") and w.get("tier"))
    sc.add("D4 结构", "schema (term/senses/tier)", 3, schema_ok / n)
    sc.add("D4 结构", "no-duplicate-terms", 2, 1.0 if len({w["term"] for w in words}) == n else 0.0)
    shell = sum(1 for s in senses if not (s.get("pos") or "").strip()
                and not s.get("def_en") and not s.get("def_zh") and not s.get("examples"))
    sc.add("D4 结构", "no-empty-shell-senses", 3, 1 - shell / ns, f"{shell} shell senses")
    moji = sum(1 for w in words if "�" in json.dumps(w, ensure_ascii=False))
    sc.add("D4 结构", "no-mojibake", 2, 1 - moji / n)

    # ---------- D5 学习元数据 ----------
    sc.add("D5 元数据", "tier", 3, sum(1 for w in words if w.get("tier")) / n)
    sc.add("D5 元数据", "tpo_hf>=1500", 2,
           1.0 if sum(1 for w in words if w.get("tpo_hf")) >= 1500 else 0.0)
    verbs = [w for w in words if any((s.get("pos") or "") == "verb" for s in w.get("senses") or [])]
    sc.add("D5 元数据", "verb-exchange", 3,
           (sum(1 for w in verbs if w.get("exchange")) / len(verbs)) if verbs else 1.0)
    sc.add("D5 元数据", "freq|bnc", 2, sum(1 for w in words if w.get("frq") or w.get("bnc")) / n)

    # ---------- D6 App 功能 (live) ----------
    if url:
        st, _, t_page = _get(url + "/", 15)
        st2, b2, t_next = _get(f"{url}/api/next?deck={deck}&new_per_day=100000", 15)
        api_ok = (st == 200) + (st2 == 200 and b"term" in b2) \
            + (_get(f"{url}/api/search?deck={deck}&q=sub")[0] == 200) \
            + (_get(f"{url}/api/entry?deck={deck}&term=" + urllib.parse.quote(words[0]["term"]))[0] == 200)
        sc.add("D6 App", "read-APIs (4)", 4, api_ok / 4)
        if allow_write:
            term = json.loads(b2).get("term") if (st2 == 200 and b2) else words[0]["term"]
            ok = _post(f"{url}/api/review", {"deck": deck, "term": term, "grade": "good"}) == 200
            ok2 = _post(f"{url}/api/undo", {"deck": deck}) == 200
            sc.add("D6 App", "write+undo round-trip", 2, (ok + ok2) / 2)
        else:
            sc.add("D6 App", "write+undo", 2, 0, "SKIPPED: no --allow-write")
        if e2e and node:
            try:
                r = subprocess.run(
                    [node, str(REPO / "tools/vocab-srs/test_lookup.mjs"),
                     str(REPO / "tools/vocab-srs/static/index.html")],
                    env={**os.environ, "VOCAB_URL": url},
                    capture_output=True, text=True, timeout=300)
                passed = "ALL LOOKUP + SHORTCUT TESTS PASSED" in r.stdout
                tail = (r.stdout.strip().splitlines() or ["no output"])[-1][:80]
            except Exception as ex:
                passed, tail = False, str(ex)[:80]
            sc.add("D6 App", "frontend-e2e", 6, 1.0 if passed else 0.0, "" if passed else tail)
        else:
            sc.add("D6 App", "frontend-e2e", 6, 0, "SKIPPED: need --e2e + node")
        sc.add("D6 App", "latency (page<1s, next<0.5s)", 3,
               (t_page < 1) * 0.5 + (t_next < 0.5) * 0.5)
    else:
        sc.add("D6 App", "live-checks", 15, 0, "SKIPPED: no --url")

    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", nargs="?", default="toefl", choices=list(DECKS))
    ap.add_argument("--url", default=None, help="throwaway server base URL for live D6/TTS checks")
    ap.add_argument("--allow-write", action="store_true", help="THROWAWAY server only: review+undo")
    ap.add_argument("--e2e", action="store_true", help="run tools/vocab-srs/test_lookup.mjs")
    ap.add_argument("--node", default=os.environ.get("NODE_BIN") or "node")
    args = ap.parse_args()

    node = shutil.which(args.node) or (args.node if Path(args.node).exists() else None)
    sc = score(args.deck, args.url, args.allow_write, args.e2e, node)

    print(f"\n===== {args.deck.upper()} completeness =====")
    for dim, v in sc.dims.items():
        print(f"\n{dim}   {v['got']:.1f} / {v['max']:.0f}")
        for it in v["items"]:
            note = f"   <- {it['note']}" if it["note"] else ""
            print(f"   {it['name']:<32} {it['got']:>6.2f} / {it['pts']}{note}")
    print(f"\nTOTAL: {sc.total} / 100     (loop target: >= 95)\n")

    out = REPO / "data" / f"vocab_score_{args.deck}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"deck": args.deck, "total": sc.total, "ts": time.strftime("%F %T"),
                               "dims": sc.dims}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"json -> {out}")
    return sc.total


if __name__ == "__main__":
    main()
