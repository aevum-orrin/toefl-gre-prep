#!/usr/bin/env python3
"""Convert the raw TPO PDF/DOCX files (extracted from the user's archives on scratch) into
plain-text staging files that Opus subagents then parse into structured question items.

For every TPO folder it finds, it categorises the files and dumps text to:
  $LANG_PREP_CACHE/official-real/tpo_txt/<TPO>/{reading_q,reading_a,listening_q,
    listening_transcript,listening_a,speaking_q,speaking_model,writing_q,writing_model}.txt

Reading/Listening are the priority (same task types as 2026). Text is English (passages,
questions) plus Chinese answer keys/explanations in the *_a files.

Usage:  python scripts/convert_tpo.py            # all TPOs
        python scripts/convert_tpo.py --only TPO66,TPO74
"""
from __future__ import annotations

import argparse
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pypdf import PdfReader

CACHE = Path(os.environ.get("LANG_PREP_CACHE")
             or "/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache")
RAW_ROOT = CACHE / "official-real" / "raw"
OUT = CACHE / "official-real" / "tpo_txt"


def pdf_text(p: Path) -> str:
    try:
        r = PdfReader(str(p))
        return "\n".join((pg.extract_text() or "") for pg in r.pages)
    except Exception as e:
        return f"[pdf read error: {e}]"


def docx_text(p: Path) -> str:
    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml")
        # strip tags, keep paragraph breaks
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        root = ET.fromstring(xml)
        paras = []
        for para in root.iter(f"{ns}p"):
            texts = [node.text for node in para.iter(f"{ns}t") if node.text]
            paras.append("".join(texts))
        return "\n".join(paras)
    except Exception as e:
        return f"[docx read error: {e}]"


def any_text(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        return pdf_text(p)
    if p.suffix.lower() == ".docx":
        return docx_text(p)
    return ""


def categorise(name: str) -> str | None:
    """Map a filename to a staging key, or None to ignore."""
    n = name.lower()
    is_ans = ("答案" in name) or ("解析" in name) or ("范文" in name)
    if "阅读" in name:
        return "reading_a" if is_ans else "reading_q"
    if "听力" in name:
        if "原文" in name:
            return "listening_transcript"
        return "listening_a" if is_ans else "listening_q"
    if "口语" in name:
        return "speaking_model" if ("范文" in name or "解析" in name) else "speaking_q"
    if "写作" in name:
        return "writing_model" if ("范文" in name or "解析" in name) else "writing_q"
    return None


def tpo_folders() -> list[Path]:
    # the actual per-TPO folders (TPO54, TPO66, "TuoF 55", ...) live in a dir named
    # exactly "【趴趴托福】TPO54-75" nested a few levels down inside the extracted archive.
    cands = list(RAW_ROOT.glob("**/【趴趴托福】TPO54-75"))
    if not cands:
        return []
    return [d for d in cands[0].iterdir() if d.is_dir()]


def norm_tpo(folder_name: str) -> str:
    m = re.search(r"(\d+)", folder_name)
    return f"TPO{m.group(1)}" if m else re.sub(r"\s+", "", folder_name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated TPO tags e.g. TPO66,TPO74")
    args = ap.parse_args()
    only = {x.strip().upper() for x in args.only.split(",")} if args.only else None

    folders = tpo_folders()
    if not folders:
        print(f"no TPO folders under {RAW}")
        return
    done = 0
    for f in sorted(folders):
        tag = norm_tpo(f.name)
        if only and tag not in only:
            continue
        buckets: dict[str, list[str]] = {}
        for p in f.rglob("*"):
            if p.suffix.lower() not in (".pdf", ".docx"):
                continue
            key = categorise(p.name)
            if not key:
                continue
            buckets.setdefault(key, []).append(any_text(p))
        if not buckets:
            continue
        d = OUT / tag
        d.mkdir(parents=True, exist_ok=True)
        for key, texts in buckets.items():
            (d / f"{key}.txt").write_text("\n\n".join(texts), encoding="utf-8")
        done += 1
        print(f"  {tag}: {', '.join(sorted(buckets))}")
    print(f"converted {done} TPOs -> {OUT}")


if __name__ == "__main__":
    main()
