"""Read a PDF or a text file as pages of numbered lines, so a passage can be cited page:line.

A .txt file is one page unless it carries form feeds. A PDF is read with pypdf; a scanned PDF
with no text layer comes back empty and the caller says so.
"""
import os


def pages(path):
    """[[line, ...], ...] — one list of lines per page."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover
            raise SystemExit("reading a PDF needs pypdf: python3 -m pip install --user pypdf")
        reader = PdfReader(path)
        out = []
        for pg in reader.pages:
            text = pg.extract_text() or ""
            out.append([ln.rstrip() for ln in text.splitlines()])
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return from_text(text)


def from_text(text):
    return [[ln.rstrip() for ln in pg.splitlines()] for pg in text.split("\f")]


def char_count(pgs):
    return sum(len(ln) for pg in pgs for ln in pg)
