#!/usr/bin/env python3
"""Rebuild examples/doe-v-roe from nothing.

    python3 scripts/make_example.py

The matter is fictional: Jane Doe v. Roe Holdings, LLC, Case No. 26CV000000. The names, the
amounts, the dates and the documents in it are made up for the example.
"""
import datetime as _dt
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chirograph import brief, closing, ics, matter, offers, statement, terms  # noqa: E402

DEST = os.path.join(ROOT, "examples", "doe-v-roe")

AGREEMENT = """SETTLEMENT AGREEMENT AND RELEASE

This Settlement Agreement and Release ("Agreement") is made as of September 17, 2026
("Effective Date") by and between Jane Doe ("Doe"), on the one hand, and Roe Holdings, LLC,
a California limited liability company ("Roe Holdings"), and Richard Roe, an individual
("Mr. Roe"), on the other hand. Doe, Roe Holdings and Mr. Roe are each a "Party" and
together the "Parties".

RECITALS

A. Doe filed a complaint against Roe Holdings in the Superior Court of California, County of
Alameda, Case No. 26CV000000 (the "Action"). Roe Holdings filed a cross-complaint against Doe.

B. Doe recorded a lis pendens against the parcel described in Exhibit A.

1. Settlement Payment. Roe Holdings shall pay Doe the sum of $120,000 (the "Settlement
Payment") by wire transfer within twenty-one (21) calendar days after the Effective Date.
Within seven (7) days after the Effective Date, Doe shall send wire instructions and a
completed IRS Form W-9 to counsel for Roe Holdings.

2. Release by Doe. Upon receipt of the Settlement Payment, Doe releases and forever
discharges Roe Holdings and Mr. Roe, and their respective officers, members, agents and
insurers, from all claims, demands and causes of action arising out of the Action.

3. Release by Roe Holdings. Roe Holdings releases and forever discharges Doe, and her
heirs and assigns, from all claims, demands and causes of action arising out of the Action.

4. Unknown Claims. Each Party waives the protection of California Civil Code section 1542.

5. Dismissal. Within five (5) court days after receipt of the Settlement Payment, Doe shall
file a request for dismissal of the complaint with prejudice, and Roe Holdings shall file a
request for dismissal of the cross-complaint with prejudice.

6. Quitclaim Deed. Within fourteen (14) days after the Effective Date, Doe shall sign a
quitclaim deed for the parcel described in Exhibit A before a notary public or, if she is
outside the United States, a consular officer, and shall send the signed deed to counsel
for Roe Holdings by tracked courier. The outside date for delivery of the deed is
twenty-eight (28) days after the Effective Date.

7. Lis Pendens. Within ten (10) days after receipt of the Settlement Payment, Doe shall
record a withdrawal of the lis pendens with the county recorder.

8. Enforcement. The Parties stipulate that the Court shall retain jurisdiction under Code of
Civil Procedure section 664.6 to enforce this Agreement. Each Party shall bear its own
attorneys' fees and costs.

9. Taxes. No Party makes a representation about the tax treatment of the Settlement Payment.

10. General. This Agreement is the entire agreement of the Parties. It is governed by the
laws of the State of California. It may be signed in counterparts and by electronic
signature. Time is of the essence.
"""

DOCS = {
    "offers/2026-08-03 demand letter.txt":
        "August 3, 2026\n\nTo counsel for Roe Holdings, LLC:\n\nJane Doe offers to settle Case No. 26CV000000 for $240,000, paid within 30 days, with a release of Roe Holdings, LLC only. This offer is open until 5:00 p.m. Pacific time on August 17, 2026.\n\nJane Doe\n",
    "offers/2026-08-12 offer to compromise.txt":
        "OFFER TO COMPROMISE (CODE CIV. PROC. § 998)\n\nServed by email August 12, 2026.\n\nDefendant Roe Holdings, LLC offers to allow judgment to be taken against it and in favor of plaintiff Jane Doe in the sum of $60,000, each side to bear its own costs.\n\nAcceptance: plaintiff may accept by signing the statement below.\n",
    "offers/2026-08-26 counter letter.txt":
        "August 26, 2026\n\nTo counsel for Roe Holdings, LLC:\n\nJane Doe counters at $185,000, paid within 30 days, with mutual releases.\n\nJane Doe\n",
    "offers/2026-09-02 reply.txt":
        "September 2, 2026\n\nTo Jane Doe:\n\nRoe Holdings, LLC does not accept the August 26 counter.\n\nCounsel for Roe Holdings, LLC\n",
    "offers/2026-09-09 mediator's proposal.txt":
        "September 9, 2026\n\nMediator's proposal, to both sides: $120,000, paid within 21 days; mutual releases; a quitclaim deed from Jane Doe for the parcel; dismissal of the complaint and the cross-complaint with prejudice. Each side answers the mediator in confidence by noon Pacific time on September 16, 2026.\n",
    "offers/2026-09-15 acceptance.txt":
        "September 15, 2026\n\nFrom the mediator, to both sides: both sides accepted the September 9 proposal.\n",
    "received/2026-08-20 notice of case management conference.txt":
        "NOTICE OF CASE MANAGEMENT CONFERENCE\n\nCase No. 26CV000000. A case management conference is set for September 24, 2026 at 9:00 a.m. in Department 0.\n",
    "evidence/2026-09-17 notice of settlement - built.txt":
        "Notice of settlement of entire case, form filled in September 17, 2026. File: out/notice-of-settlement.pdf (example entry; the PDF is not part of this example).\n",
    "evidence/2026-09-17 notice of settlement - signed.txt":
        "Notice of settlement signed by Jane Doe, September 17, 2026 (example entry).\n",
    "evidence/2026-09-18 notice of settlement - sent mail.txt":
        "Sent September 18, 2026, 9:12 a.m. Pacific time. To: counsel for Roe Holdings, LLC. Attached: notice of settlement, proof of electronic service (example entry).\n",
    "evidence/2026-09-21 wire instructions - sent mail.txt":
        "Sent September 21, 2026. To: counsel for Roe Holdings, LLC. Attached: wire instructions, IRS Form W-9 (example entry).\n",
}

MUZZLES = """# One entry per line: a word, a phrase or a regular expression (case does not count).
# `chirograph statement build` exits 1 when the statement contains any of them.
# Lines starting with # are notes. These are example entries: words about motive,
# bargaining pressure and hardship, which this matter's statement leaves out.
# stylecheck: allow-start
leverage
hardship
cannot afford
\\bpunish
revenge
# stylecheck: allow-end
"""

STATEMENT = {
    "title": "MEDIATION STATEMENT",
    "for_party": "Plaintiff Jane Doe",
    "header_note": "Prepared for the mediation session. Fictional example.",
    "mediator": "Pat Example",
    "session": {"date": "2026-09-09", "time": "09:30", "place": "by video"},
    "parties": [
        "Plaintiff Jane Doe sold a business to defendant Roe Holdings, LLC in 2024 and took back a note secured by a parcel in Alameda County.",
        "Defendant Roe Holdings, LLC is a California limited liability company. Richard Roe is its managing member and is not a party to the case."
    ],
    "posture": [
        "The complaint was filed in the Superior Court of California, County of Alameda, Case No. 26CV000000. Roe Holdings filed a cross-complaint. A case management conference is set for September 24, 2026. No trial date is set."
    ],
    "facts": [
        "The note called for twelve quarterly payments. Roe Holdings made seven and stopped in 2025.",
        "Roe Holdings says the business records it received at closing overstated two customer accounts, and it claims an offset."
    ],
    "claims": [
        {"claim": "Breach of the note", "basis": "Five unpaid quarterly payments", "amount": 150000},
        {"claim": "Interest", "basis": "Contract rate from each due date", "amount": 21500},
        {"claim": "Costs of suit", "basis": "Filing and service fees to date", "amount": 1850}
    ],
    "claims_note": "Roe Holdings' cross-complaint claims an offset of $70,000.",
    "terms_sought": [
        "One payment by wire within 30 days of signing.",
        "A release that runs to Roe Holdings, LLC.",
        "Dismissal of the complaint and the cross-complaint with prejudice after payment.",
        "The court to retain jurisdiction to enforce the settlement under Code of Civil Procedure section 664.6."
    ],
    "signer": {"name": "Jane Doe", "role": "Plaintiff, self-represented", "date": "September 4, 2026"}
}

CLOSING_FACTS = {
    "signed": "2026-09-17",
    "agreement": "agreements/2026-09-17 settlement agreement.txt",
    "conditional": False,
    "payment": {"amount": 120000, "payor": "Roe Holdings, LLC", "method": "wire", "days": 21, "cite": "Agreement §1"},
    "wire": {"days": 7, "cite": "Agreement §1"},
    "tax_form": {"title": "IRS Form W-9", "days": 7, "cite": "Agreement §1"},
    "instruments": [{
        "title": "Quitclaim deed", "signer_abroad": True, "cite": "Agreement §6",
        "sign": {"days": 14, "cite": "Agreement §6"},
        "dispatch": {"days": 14, "cite": "Agreement §6"},
        "outside": {"days": 28, "cite": "Agreement §6"}
    }],
    "lis_pendens": {"days": 10, "after_date": "2026-10-08", "trigger_phrase": "payment due", "cite": "Agreement §7"},
    "retain_jurisdiction": True,
    "hearings": [{"date": "2026-09-24", "time": "09:00", "title": "Case management conference", "kind": "hearing",
                  "order": "received/2026-08-20 notice of case management conference.txt"}]
}


def write(rel, body):
    p = os.path.join(DEST, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return p


def agreement_pdf(path):
    """The same agreement as a PDF, so the example shows a page:line cite from a PDF too."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path, pagesize=LETTER)
    c.setTitle("Settlement Agreement and Release (fictional example)")
    y = 720
    c.setFont("Times-Roman", 11)
    for line in AGREEMENT.splitlines():
        if y < 72:
            c.showPage()
            c.setFont("Times-Roman", 11)
            y = 720
        c.drawString(72, y, line)
        y -= 15
    c.save()


def main():
    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    matter.scaffold(DEST, "Jane Doe", "Roe Holdings, LLC", "26CV000000", "Alameda", reader_tz="Europe/London")
    for rel, body in DOCS.items():
        write(rel, body)
    write("muzzles.txt", MUZZLES)
    write("agreements/2026-09-17 settlement agreement.txt", AGREEMENT)
    agreement_pdf(os.path.join(DEST, "agreements", "2026-09-17 settlement agreement.pdf"))
    with open(os.path.join(DEST, "statement.json"), "w", encoding="utf-8") as fh:
        json.dump(STATEMENT, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    # fixed dates in the two ledgers, so a rebuild writes the same files
    for name in ("STATUS.md", "DONE.md"):
        p = os.path.join(DEST, name)
        with open(p, encoding="utf-8") as fh:
            body = fh.read()
        body = body.replace(_dt.date.today().isoformat(), "2026-08-03")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)

    # the ladder
    offers.add(DEST, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", 240000,
               "Paid within 30 days; release of Roe Holdings, LLC only.", "email",
               "offers/2026-08-03 demand letter.txt", expires="2026-08-17", expires_time="17:00")
    offers.add(DEST, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000,
               "Judgment for the sum; each side bears its own costs.", "email",
               "offers/2026-08-12 offer to compromise.txt")
    offers.add(DEST, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000,
               "Paid within 30 days; mutual releases.", "email", "offers/2026-08-26 counter letter.txt", answers="O2")
    out = os.path.join(DEST, "out")
    os.makedirs(out, exist_ok=True)
    text, _v = offers.render(DEST, "2026-08-28")
    write("out/ladder 2026-08-28.txt", text + "\n")

    # the mediation statement, as of the day before the session
    code, msgs, _files = statement.build(DEST, today="2026-09-08")
    assert code == 0, msgs

    offers.decide(DEST, "O3", "rejected", "2026-09-02", "offers/2026-09-02 reply.txt")
    offers.add(DEST, "2026-09-09", "Pat Example (mediator)", "both sides", "mediator", 120000,
               "Paid within 21 days; mutual releases; quitclaim deed; dismissal of both pleadings with prejudice.",
               "email", "offers/2026-09-09 mediator's proposal.txt", expires="2026-09-16", expires_time="12:00")
    offers.decide(DEST, "O4", "accepted", "2026-09-15", "offers/2026-09-15 acceptance.txt")

    # the agreement, read against the term list
    result, code = terms.check(os.path.join(DEST, "agreements", "2026-09-17 settlement agreement.pdf"),
                               release_only="Roe Holdings, LLC", expect_none=["confidentiality", "non_disparagement"])
    write("out/terms check.txt", terms.render(result) + "\n\nExit code %d.\n" % code)

    # the closing list
    closing.build(DEST, CLOSING_FACTS)
    for task, state, ev, on in [
        ("notice", "BUILT", "evidence/2026-09-17 notice of settlement - built.txt", "2026-09-17"),
        ("notice", "SIGNED", "evidence/2026-09-17 notice of settlement - signed.txt", "2026-09-17"),
        ("notice", "SERVED", "evidence/2026-09-18 notice of settlement - sent mail.txt", "2026-09-18"),
        ("wire", "BUILT", "evidence/2026-09-21 wire instructions - sent mail.txt", "2026-09-21"),
        ("wire", "SERVED", "evidence/2026-09-21 wire instructions - sent mail.txt", "2026-09-21"),
    ]:
        ok, msg = closing.advance(DEST, task, ev, state, on)
        assert ok, msg
    text, _r = closing.render(DEST, "2026-09-21")
    write("out/closing list 2026-09-21.txt", text)
    text, _v = offers.render(DEST, "2026-09-21")
    write("out/ladder 2026-09-21.txt", text + "\n")
    write("out/brief 2026-09-21.txt", brief.brief(DEST, "2026-09-21"))
    ics_text, n = ics.to_ics(DEST, "2026-09-21", now=_dt.datetime(2026, 9, 21, 16, 0, 0))
    with open(os.path.join(out, "settlement.ics"), "w", encoding="utf-8", newline="") as fh:
        fh.write(ics_text)
    print("Built %s" % DEST)
    print("  4 offers, %d closing tasks, %d calendar events, terms check exit %d" % (
        len(closing.load(DEST)["tasks"]), n, code))


if __name__ == "__main__":
    main()
