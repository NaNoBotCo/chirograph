#!/usr/bin/env python3
"""Writes docs/, the public page: the desk window showing the example matter.

    python3 scripts/make_site.py

Reads examples/doe-v-roe with the day fixed at 2026-09-21, puts what the desk would show into
desk/index.html as DEMO (the state and the terms check of each agreement file), and copies the
files in the example's out/ folder into docs/samples/. The page calls no server.
"""
import datetime
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chirograph import desk, terms  # noqa: E402

SITE = "https://nanobotco.github.io/chirograph/"
KIT = "https://github.com/NaNoBotCo/chirograph"
EXAMPLE = os.path.join(ROOT, "examples", "doe-v-roe")
TODAY = "2026-09-21"

HEAD = """<title>Chirograph</title>
<meta name="description" content="A settlement desk: the offer ladder with its CCP 998 clocks, a terms check of an agreement, a closing list that moves on evidence, a mediation statement. California state court. A kit for a Mac, shown here on a made-up matter.">
<link rel="canonical" href="{site}">
<meta property="og:type" content="website"><meta property="og:site_name" content="NaNoBotCo">
<meta property="og:title" content="Chirograph · ไคโรกราฟ">
<meta property="og:description" content="A settlement desk: offers, clocks, terms, closing. · โต๊ะงานยอมความ">
<meta property="og:url" content="{site}">
<meta property="og:image" content="{site}card.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="A sheet cut in two along a wavy line through the word Chirograph.">
<meta property="og:locale" content="en_US"><meta property="og:locale:alternate" content="th_TH">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{site}card.jpg">
<link rel="alternate" type="text/plain" href="{site}llms.txt" title="llms.txt">"""

LLMS = """# Chirograph · ไคโรกราฟ

A settlement desk for a civil case in California state court, in English and Thai. A kit for a Mac (Python 3.9). This page shows it on a fictional matter, Jane Doe v. Roe Holdings, LLC, with the day fixed at 21 September 2026.

- Offer ladder: each offer with its date, amount, terms and the file that made it; each side's last position, the gap and the midpoint; an offer with no document on disk shows UNSOURCED.
- Clocks with their arithmetic: a Code of Civil Procedure section 998 offer with no stated expiry gets the 30-day statutory clock; each date prints in court time and in the reader's time zone.
- Terms check: reads an agreement against a list of 31 terms (payment, release, Civil Code section 1542 waiver, dismissal, lis pendens, deed and notary, tax forms, confidentiality, CCP section 664.6 and more); each is quoted with page and line, or marked "not found in this text".
- Release reader: lists who each release clause names; told that the release runs to one name, it flags any other.
- Closing list: notice of settlement, dismissal, payment, deed, hearings on calendar; a task moves from BUILT to SIGNED, SERVED, FILED and DONE only with a file on disk as evidence.
- Mediation statement as text and PDF, checked against a per-matter muzzle list; a brief; a calendar file.
- The rule table carries, for each entry, where and when it was read.

The kit gives dates and document text.

Kit: {kit}
Sibling: Cursitor, a litigation desk for Claude Code, https://nanobotco.github.io/cursitor/

Text CC BY 4.0, code MIT.
"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{site}</loc><lastmod>{day}</lastmod></url>
</urlset>
"""


def main():
    docs = os.path.join(ROOT, "docs")
    state = desk.state(EXAMPLE, TODAY)
    checks = {}
    for rel in state["agreements"]:
        checks[rel], _code = terms.check(os.path.join(EXAMPLE, rel))
    out = os.path.join(EXAMPLE, "out")
    names = sorted(f for f in os.listdir(out) if not f.startswith("."))
    demo = {"kit": KIT, "state": state, "terms": checks, "samples": names}

    def clean(text):
        for real in (os.path.realpath(EXAMPLE), EXAMPLE, os.path.realpath(ROOT), ROOT):
            text = text.replace(real + os.sep, "").replace(real, "chirograph")
        return text

    blob = clean(json.dumps(demo, ensure_ascii=False)).replace("</", "<\\/")
    with open(os.path.join(ROOT, "desk", "index.html"), encoding="utf-8") as fh:
        page = fh.read()
    for old, new in (("<title>Chirograph desk</title>", HEAD.format(site=SITE)),
                     ("var DEMO = null;", "var DEMO = %s;" % blob),
                     ('var TOKEN = "{{TOKEN}}";', 'var TOKEN = "";')):
        if page.count(old) != 1:
            raise SystemExit("desk/index.html no longer has the line: %s" % old)
        page = page.replace(old, new)

    samples = os.path.join(docs, "samples")
    if os.path.isdir(samples):
        shutil.rmtree(samples)
    os.makedirs(samples)
    texts = [blob]
    for n in names:
        src = os.path.join(out, n)
        if n.endswith((".txt", ".ics")):
            with open(src, encoding="utf-8") as fh:
                body = clean(fh.read())
            texts.append(body)
            with open(os.path.join(samples, n), "w", encoding="utf-8") as fh:
                fh.write(body)
        else:
            shutil.copyfile(src, os.path.join(samples, n))
    for body in texts:
        for bad in ("/Users/", "/private/", "/var/folders", "/tmp/"):
            if bad in body:
                raise SystemExit("a path from this computer is in the page data: %s" % bad)
    day = datetime.date.today().isoformat()
    for name, body in (("index.html", page), ("llms.txt", LLMS.format(kit=KIT)),
                       ("sitemap.xml", SITEMAP.format(site=SITE, day=day))):
        with open(os.path.join(docs, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    print("wrote %s" % docs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
