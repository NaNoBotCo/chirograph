"""A mediation statement from statement.json: plain text and a letter-format PDF.

    chirograph statement build [matter] [--out DIR] [--today YYYY-MM-DD]

statement.json carries the parts a person writes (parties, posture, facts, claims and damages,
terms sought). The offer history is pulled from offers.json when the statement is built. Before
a file is written the text is checked against muzzles.txt, the matter's list of words and topics
that stay out of the statement; a match exits 1 with line numbers.

The text file has one paragraph per line. The PDF is US Letter, Times 12, one-inch margins,
page numbers at the foot.
"""
import json
import os
import re

from . import courtdays as cd
from . import matter as _matter
from . import offers as _offers

FILE = "statement.json"

TEMPLATE = {
    "title": "MEDIATION STATEMENT",
    "for_party": "",
    "header_note": "",
    "mediator": "",
    "session": {"date": "", "time": "", "place": ""},
    "parties": [],
    "posture": [],
    "facts": [],
    "claims": [],
    "claims_note": "",
    "terms_sought": [],
    "closing": "",
    "signer": {"name": "", "role": ""},
}


def load(matter_dir, path=None):
    p = path or os.path.join(matter_dir, FILE)
    if not os.path.exists(p):
        raise SystemExit("no statement.json at %s; `chirograph statement new` writes a blank one" % p)
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    for k, v in TEMPLATE.items():
        data.setdefault(k, v)
    return data


def new(matter_dir):
    p = os.path.join(matter_dir, FILE)
    if os.path.exists(p):
        raise SystemExit("statement.json is already at %s" % p)
    _matter.write_json(matter_dir, FILE, TEMPLATE)
    return p


def _paras(v):
    if isinstance(v, str):
        return [x.strip() for x in v.split("\n") if x.strip()]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def blocks(matter_dir, data, today=None):
    """The statement as a list of blocks: ("title"|"head"|"para"|"table"|"sign", content)."""
    m = _matter.load(matter_dir)
    cur = m.get("currency") or "$"
    out = []
    if data.get("header_note"):
        out.append(("note", data["header_note"]))
    if m.get("court"):
        out.append(("center", m["court"].upper()))
    cap = m.get("name", "")
    if m.get("case_number"):
        cap += " — Case No. %s" % m["case_number"]
    out.append(("center", cap))
    title = data.get("title") or "MEDIATION STATEMENT"
    if data.get("for_party"):
        title = "%s OF %s" % (title, data["for_party"].upper())
    out.append(("title", title))
    ses = data.get("session") or {}
    bits = []
    if data.get("mediator"):
        bits.append("Mediator: %s" % data["mediator"])
    if ses.get("date"):
        d = cd.parse_date(ses["date"])
        when = "Session: %s" % cd.fmt_full(d)
        if ses.get("time"):
            when += " at %s court time" % ses["time"]
        if ses.get("place"):
            when += ", %s" % ses["place"]
        bits.append(when)
    for b in bits:
        out.append(("para", b))

    n = [0]

    def head(text):
        n[0] += 1
        out.append(("head", "%d. %s" % (n[0], text.upper())))

    if _paras(data.get("parties")):
        head("Parties")
        out.extend(("para", p) for p in _paras(data["parties"]))
    if _paras(data.get("posture")):
        head("Posture of the case")
        out.extend(("para", p) for p in _paras(data["posture"]))
    if _paras(data.get("facts")):
        head("Facts")
        out.extend(("para", p) for p in _paras(data["facts"]))
    claims = data.get("claims") or []
    if claims:
        head("Claims and damages")
        rows = [["Claim", "Basis", "Amount"]]
        total = 0.0
        counted = False
        for c in claims:
            amt = c.get("amount")
            if amt is not None and amt != "":
                total += float(_offers.parse_amount(amt))
                counted = True
            rows.append([c.get("claim", ""), c.get("basis", ""),
                         _offers.money(_offers.parse_amount(amt), cur) if amt not in (None, "") else "not stated"])
        if counted:
            rows.append(["Total of the stated amounts", "", _offers.money(total, cur)])
        out.append(("table", rows))
        if data.get("claims_note"):
            out.extend(("para", p) for p in _paras(data["claims_note"]))

    _m, _today, views = _offers.evaluate(matter_dir, today)
    head("Offer history")
    if views:
        rows = [["Date", "From → To", "Kind", "Amount", "Status"]]
        for v in views:
            o = v.offer
            rows.append([cd.fmt_full(cd.parse_date(o["made"])), "%s → %s" % (o["from"], o["to"]),
                         _offers.KINDS[o["kind"]], _offers.money(o.get("amount"), cur), v.status.lower()])
        out.append(("table", rows))
        pos = _offers.positions(views)
        if pos["gap"] is not None:
            out.append(("para", "Last positions: plaintiff %s, defendant %s. Gap %s." % (
                _offers.money(pos["plaintiff"].offer["amount"], cur), _offers.money(pos["defendant"].offer["amount"], cur),
                _offers.money(pos["gap"], cur))))
    else:
        out.append(("para", "No offer has been entered in the ladder."))
    if _paras(data.get("terms_sought")):
        head("Terms sought")
        for i, p in enumerate(_paras(data["terms_sought"]), 1):
            out.append(("para", "(%s) %s" % (chr(96 + i) if i <= 26 else i, p)))
    if _paras(data.get("closing")):
        out.extend(("para", p) for p in _paras(data["closing"]))
    signer = data.get("signer") or {}
    if signer.get("name"):
        out.append(("sign", [signer.get("date", ""), signer["name"], signer.get("role", "")]))
    return out


def to_text(blks):
    """Plain text, one paragraph per line; a table becomes one row per line."""
    lines = []
    for kind, content in blks:
        if kind in ("note", "center", "title"):
            lines.append(content)
            if kind == "title":
                lines.append("")
        elif kind == "head":
            lines.append("")
            lines.append(content)
        elif kind == "para":
            lines.append(content)
        elif kind == "table":
            for row in content:
                lines.append(" | ".join(str(c) for c in row))
        elif kind == "sign":
            lines.append("")
            if content[0]:
                lines.append("Dated: %s" % content[0])
            lines.append(content[1])
            if content[2]:
                lines.append(content[2])
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- muzzles

def muzzle_entries(matter_dir):
    p = os.path.join(matter_dir, "muzzles.txt")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            s = ln.strip()
            if s and not s.startswith("#"):
                out.append(s)
    return out


def muzzle_hits(text, entries):
    """[(line number, entry, the line)] for each muzzled word, phrase or pattern in the text."""
    rx = []
    for e in entries:
        try:
            rx.append((e, re.compile(e, re.I)))
        except re.error:
            rx.append((e, re.compile(re.escape(e), re.I)))
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for e, r in rx:
            if r.search(line):
                hits.append((n, e, line.strip()))
    return hits


# --------------------------------------------------------------------------- PDF

def to_pdf(blks, path, footer=""):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:  # pragma: no cover
        raise SystemExit("the PDF needs reportlab: python3 -m pip install --user reportlab")
    from xml.sax.saxutils import escape

    base = ParagraphStyle("base", fontName="Times-Roman", fontSize=12, leading=16, spaceAfter=8)
    center = ParagraphStyle("center", parent=base, alignment=TA_CENTER, spaceAfter=2)
    title = ParagraphStyle("title", parent=base, fontName="Times-Bold", alignment=TA_CENTER, spaceBefore=10, spaceAfter=12)
    note = ParagraphStyle("note", parent=base, fontName="Times-Italic", alignment=TA_CENTER, spaceAfter=10)
    head = ParagraphStyle("head", parent=base, fontName="Times-Bold", spaceBefore=10, spaceAfter=6, keepWithNext=1)
    cell = ParagraphStyle("cell", parent=base, fontSize=11, leading=14, spaceAfter=0)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Times-Bold")

    def arrow(s):
        # Times has no arrow glyph; the PDF prints "to"
        return escape(str(s)).replace("→", "to")

    flow = []
    for kind, content in blks:
        if kind == "note":
            flow.append(Paragraph(arrow(content), note))
        elif kind == "center":
            flow.append(Paragraph(arrow(content), center))
        elif kind == "title":
            flow.append(Paragraph(arrow(content), title))
        elif kind == "head":
            flow.append(Paragraph(arrow(content), head))
        elif kind == "para":
            flow.append(Paragraph(arrow(content), base))
        elif kind == "table":
            ncol = len(content[0])
            data = [[Paragraph(arrow(c), cellb if r == 0 else cell) for c in row] for r, row in enumerate(content)]
            width = 6.5 * inch
            if ncol == 3:
                widths = [1.9 * inch, 3.3 * inch, 1.3 * inch]
            elif ncol == 5:
                widths = [1.2 * inch, 2.1 * inch, 1.3 * inch, 1.0 * inch, 0.9 * inch]
            else:
                widths = [width / ncol] * ncol
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(t)
            flow.append(Spacer(1, 8))
        elif kind == "sign":
            flow.append(Spacer(1, 18))
            if content[0]:
                flow.append(Paragraph("Dated: %s" % arrow(content[0]), base))
            flow.append(Spacer(1, 22))
            flow.append(Paragraph("______________________________", base))
            flow.append(Paragraph(arrow(content[1]), base))
            if content[2]:
                flow.append(Paragraph(arrow(content[2]), base))

    def foot(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        label = ("%s — page %d" % (footer, doc.page)) if footer else ("Page %d" % doc.page)
        canvas.drawCentredString(LETTER[0] / 2.0, 0.6 * inch, label.replace("→", "to"))
        canvas.restoreState()

    doc = SimpleDocTemplate(path, pagesize=LETTER, leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
                            title=footer or "Mediation statement")
    doc.build(flow, onFirstPage=foot, onLaterPages=foot)
    return doc.page


def build(matter_dir, out_dir=None, path=None, today=None):
    """Write the statement. Returns (code, message lines, [files])."""
    data = load(matter_dir, path)
    m = _matter.load(matter_dir)
    blks = blocks(matter_dir, data, today)
    text = to_text(blks)
    entries = muzzle_entries(matter_dir)
    hits = muzzle_hits(text, entries)
    if hits:
        msgs = ["MUZZLED — the statement was not written. muzzles.txt lists these, and the text has them:"]
        for n, e, line in hits:
            msgs.append("  line %d: [%s] %s" % (n, e, line if len(line) <= 160 else line[:157] + "…"))
        return 1, msgs, []
    out_dir = out_dir or os.path.join(matter_dir, "out")
    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, "mediation-statement.txt")
    pdf_path = os.path.join(out_dir, "mediation-statement.pdf")
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    footer = "Mediation statement — %s" % m.get("name", "")
    pages = to_pdf(blks, pdf_path, footer)
    msgs = ["Wrote %s" % txt_path, "Wrote %s (%d page%s)" % (pdf_path, pages, "" if pages == 1 else "s"),
            "Checked against %d muzzle entr%s: none in the text." % (len(entries), "y" if len(entries) == 1 else "ies")]
    return 0, msgs, [txt_path, pdf_path]
