#!/usr/bin/env python3
"""doc-reader: extract plain text from office and web documents, stdlib-only.

Office Open XML files (docx, pptx, xlsx) are ZIPs of XML — readable with
zipfile + xml.etree, no python-docx, no LibreOffice, no network. Also reads
markdown, html (scripts/styles stripped), and plain text. Output is the text
content, ready for an agent to summarize, index, or compare without needing
the document tooling installed. PDF is delegated to pdftotext when available;
otherwise the tool reports the limitation honestly.

Usage:
    doc_reader.py report.docx [--json]
    doc_reader.py slides.pptx --json
    doc_reader.py book.xlsx | head -100
    doc_reader.py page.html notes.md README.pdf

Exit codes: 0 ok, 2 unsupported/missing/corrupt input.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if text:
            paras.append(text)
    return {"format": "docx", "paragraphs": len(paras), "text": "\n".join(paras)}


def read_pptx(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        slide_names = sorted(n for n in z.namelist()
                             if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        texts = []
        for name in slide_names:
            root = ElementTree.fromstring(z.read(name))
            slide_text = " ".join((t.text or "").strip()
                                  for t in root.iter(f"{A}t") if (t.text or "").strip())
            texts.append(slide_text)
    return {"format": "pptx", "slides": len(slide_names), "text": "\n".join(texts)}


def read_xlsx(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{SS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{SS}t")))
        sheet_names = sorted(n for n in z.namelist()
                             if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        lines = []
        for name in sheet_names:
            root = ElementTree.fromstring(z.read(name))
            for row in root.iter(f"{SS}row"):
                cells = []
                for c in row.iter(f"{SS}c"):
                    v = c.find(f"{SS}v")
                    if v is None or v.text is None:
                        continue
                    val = v.text
                    if c.get("t") == "s":
                        idx = int(val)
                        val = shared[idx] if idx < len(shared) else val
                    cells.append(val)
                if cells:
                    lines.append("\t".join(cells))
    return {"format": "xlsx", "sheets": len(sheet_names),
            "rows": len(lines), "text": "\n".join(lines)}


class TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def read_html_text(text: str) -> str:
    parser = TextHTMLParser()
    parser.feed(text)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(parser.parts))).strip()


def read_pdf(path: Path) -> dict:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return {"format": "pdf", "error": "pdftotext not installed (brew install poppler); "
                "PDF text extraction needs an external tool"}
    p = subprocess.run([pdftotext, str(path), "-"], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        return {"format": "pdf", "error": p.stderr.strip()[:200]}
    return {"format": "pdf", "text": p.stdout.strip()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    results = []
    errors = 0
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            print(f"missing: {f}", file=sys.stderr)
            errors += 1
            continue
        ext = p.suffix.lower()
        try:
            if ext == ".docx":
                r = read_docx(p)
            elif ext == ".pptx":
                r = read_pptx(p)
            elif ext == ".xlsx":
                r = read_xlsx(p)
            elif ext == ".pdf":
                r = read_pdf(p)
            elif ext in (".html", ".htm"):
                r = {"format": "html", "text": read_html_text(p.read_text(errors="replace"))}
            elif ext in (".md", ".markdown", ".txt"):
                r = {"format": ext.lstrip("."), "text": p.read_text(errors="replace")}
            else:
                print(f"unsupported format: {f} (docx/pptx/xlsx/pdf/html/md/txt)",
                      file=sys.stderr)
                errors += 1
                continue
        except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as exc:
            print(f"corrupt {f}: {exc}", file=sys.stderr)
            errors += 1
            continue
        if "error" in r:
            print(f"{f}: {r['error']}", file=sys.stderr)
            errors += 1
            continue
        r["file"] = str(p)
        results.append(r)

    if args.json:
        print(json.dumps(results[0] if len(results) == 1 else results, indent=2))
    else:
        for r in results:
            if len(results) > 1:
                print(f"--- {r['file']} ({r['format']}) ---")
            print(r["text"])
    return 2 if errors and not results else (1 if errors else 0)


if __name__ == "__main__":
    raise SystemExit(main())
