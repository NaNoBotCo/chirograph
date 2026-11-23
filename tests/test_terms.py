"""The terms check: FOUND with page:line, or not found in this text; and the release, read closely."""
import os

from chirograph import rules
from chirograph import terms

AGREEMENT = """SETTLEMENT AGREEMENT AND RELEASE

This Settlement Agreement and Release ("Agreement") is made as of September 17, 2026
("Effective Date") by and between Jane Doe ("Doe"), on the one hand, and Roe Holdings, LLC,
a California limited liability company ("Roe Holdings"), and Richard Roe, an individual
("Mr. Roe"), on the other hand.

1. Settlement Payment. Roe Holdings shall pay Doe the sum of $120,000 (the "Settlement
Payment") by wire transfer within twenty-one (21) calendar days after the Effective Date.

2. Release by Doe. Upon receipt of the Settlement Payment, Doe releases and forever
discharges Roe Holdings and Mr. Roe, and their respective officers, members, agents and
insurers, from all claims, demands and causes of action arising out of the Action.

3. Release by Roe Holdings. Roe Holdings releases and forever discharges Doe, and her
heirs and assigns, from all claims, demands and causes of action arising out of the Action.

4. Unknown Claims. Each Party waives the protection of California Civil Code section 1542.

5. Dismissal. Doe shall file a request for dismissal of the complaint with prejudice, and
Roe Holdings shall file a request for dismissal of the cross-complaint with prejudice.
\f6. Enforcement. The Parties stipulate that the Court shall retain jurisdiction under Code of
Civil Procedure section 664.6. Each Party shall bear its own attorneys' fees and costs.

7. General. This Agreement is the entire agreement of the Parties. It may be signed in
counterparts. Time is of the essence.
"""


def row(result, term_id):
    return [r for r in result["terms"] if r["id"] == term_id][0]


def test_found_terms_carry_a_page_and_line_and_the_passage():
    result, code = terms.check(text=AGREEMENT)
    assert code == 0
    pay = row(result, "payment_amount")
    assert pay["found"] and pay["hits"][0]["cite"] == "p. 1:8"
    assert "$120,000" in pay["hits"][0]["quote"]
    assert row(result, "waiver_1542")["hits"][0]["cite"] == "p. 1:18"
    assert row(result, "retained_jurisdiction")["hits"][0]["cite"] == "p. 2:1"      # after the form feed
    assert row(result, "time_essence")["found"] and row(result, "counterparts")["found"]


def test_terms_not_matched_print_as_not_found_in_this_text():
    result, _code = terms.check(text=AGREEMENT)
    for term_id in ("confidentiality", "non_disparagement", "lis_pendens", "cure", "liens"):
        assert not row(result, term_id)["found"], term_id
    out = terms.render(result)
    assert "Confidentiality — not found in this text" in out
    low = out.lower()
    assert " absent" not in low and "missing" not in low


def test_dismissal_reads_which_pleadings():
    result, _code = terms.check(text=AGREEMENT)
    assert row(result, "dismissal_complaint")["found"] and row(result, "dismissal_cross_complaint")["found"]
    assert row(result, "dismissal_with_prejudice")["found"] and not row(result, "dismissal_without_prejudice")["found"]
    only_cross = "The parties shall dismiss the cross-complaint with prejudice."
    r2, _c = terms.check(text=only_cross)
    assert row(r2, "dismissal_cross_complaint")["found"] and not row(r2, "dismissal_complaint")["found"]


def test_release_clauses_are_read_for_who_releases_whom():
    result, _code = terms.check(text=AGREEMENT)
    rel = result["release"]
    assert [d["name"] for d in rel["defined"]] == ["Jane Doe", "Roe Holdings, LLC", "Richard Roe"]
    assert len(rel["clauses"]) == 2
    first, second = rel["clauses"]
    assert first["releasing"] == ["Jane Doe"] and first["released"] == ["Roe Holdings, LLC", "Richard Roe"]
    assert set(first["classes"]) == {"officers", "members", "agents", "insurers"}
    assert second["releasing"] == ["Roe Holdings, LLC"] and second["released"] == ["Jane Doe"]
    assert first["cite"] == "p. 1:11"


def test_release_only_exits_1_and_names_the_other_released_party():
    result, code = terms.check(text=AGREEMENT, release_only="Roe Holdings, LLC")
    assert code == 1
    assert result["problems"] == ["--release-only Roe Holdings, LLC: the release also names Richard Roe."]
    by_alias, code2 = terms.check(text=AGREEMENT, release_only="roe holdings")
    assert code2 == 1 and "Richard Roe" in by_alias["problems"][0]


def test_release_only_passes_when_the_release_runs_to_one_party():
    one = AGREEMENT.replace("Roe Holdings and Mr. Roe, and their respective", "Roe Holdings, and its")
    result, code = terms.check(text=one, release_only="Roe Holdings, LLC")
    assert code == 0 and result["problems"] == []
    # the return release, given by the named party, does not count against it
    assert result["release"]["clauses"][1]["released"] == ["Jane Doe"]


def test_release_only_says_so_when_the_name_is_not_among_the_released():
    result, code = terms.check(text=AGREEMENT, release_only="Acme Widgets, Inc.")
    assert code == 1
    assert any("was not read among the released parties" in p for p in result["problems"])


def test_strict_counts_classes_too():
    one = AGREEMENT.replace("Roe Holdings and Mr. Roe, and their respective", "Roe Holdings, and its")
    result, code = terms.check(text=one, release_only="Roe Holdings, LLC", strict=True)
    assert code == 1 and any("classes" in p and "insurers" in p for p in result["problems"])


def test_by_reads_only_the_clauses_one_party_gives():
    result, code = terms.check(text=AGREEMENT, release_only="Richard Roe", by="Jane Doe")
    assert code == 1 and result["problems"] == ["--release-only Richard Roe: the release also names Roe Holdings, LLC."]


def test_a_heading_is_not_a_release_clause():
    text = 'Jane Doe ("Doe") and Acme Widgets, Inc. ("Acme") agree.\n\n2. Release by Doe. See Exhibit B, which sets out the release terms separately from this page.\n'
    result, _code = terms.check(text=text)
    assert result["release"]["clauses"] == []
    assert "A release clause with named parties: not found in this text" in terms.render(result)
    _r, code = terms.check(text=text, release_only="Acme")
    assert code == 1


def test_each_other_wording_releases_every_defined_party():
    text = '''MUTUAL RELEASE
Acme Widgets, Inc. ("Acme") and Beta Supply Co. ("Beta") and Carol Smith ("Smith") agree as follows.
1. Each Party hereby fully and forever releases and discharges each other Party, and its
successors and assigns, from any and all claims.
'''
    result, code = terms.check(text=text, release_only="Acme")
    rel = result["release"]
    assert [d["name"] for d in rel["defined"]] == ["Acme Widgets, Inc.", "Beta Supply Co.", "Carol Smith"]
    assert rel["clauses"][0]["each_other"] and rel["mutual"] is not None
    assert code == 1 and "Beta Supply Co.; Carol Smith" in result["problems"][0]


def test_group_terms_middle_initials_and_also_known_as():
    text = '''This Agreement is made by Jane Q. Example, also known as Jane Sample ("Example"), and Acme
Widgets, Inc. ("Acme") and its president Paul R. Person ("Person").
1. Example, for herself and her heirs, fully, finally, and forever releases Acme and Person, and
their agents and insurers (collectively, the "Acme Released Parties") from all claims.
2. On the Release Effective Date, Acme releases Example from all claims.
3. Person also releases the Acme Released Parties from all claims.
Page 3 of 9
'''
    result, _code = terms.check(text=text)
    rel = result["release"]
    names = {d["name"]: d["aliases"] for d in rel["defined"]}
    assert names == {"Jane Q. Example": ["Example", "Jane Sample"], "Acme Widgets, Inc.": ["Acme"], "Paul R. Person": ["Person"]}
    c1, c2, c3 = rel["clauses"]
    assert c1["releasing"] == ["Jane Q. Example"] and set(c1["released"]) == {"Acme Widgets, Inc.", "Paul R. Person"}
    assert c2["releasing"] == ["Acme Widgets, Inc."] and c2["released"] == ["Jane Q. Example"]
    assert set(c3["released"]) == {"Acme Widgets, Inc.", "Paul R. Person"} and "insurers" in c3["classes"]


def test_expect_none():
    _r, ok = terms.check(text=AGREEMENT, expect_none=["confidentiality", "non-disparagement"])
    assert ok == 0
    result, code = terms.check(text=AGREEMENT + "\n8. The terms of this Agreement are confidential.\n",
                               expect_none=["confidentiality"])
    assert code == 1 and result["problems"] == ["--expect-none confidentiality: FOUND at p. 2:7."]
    result, code = terms.check(text=AGREEMENT, expect_none=["moonlight"])
    assert code == 1 and "no such term" in result["problems"][0]


def test_a_pdf_is_read_by_page_and_line(tmp_path):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas
    p = str(tmp_path / "agreement.pdf")
    c = canvas.Canvas(p, pagesize=LETTER)
    for page in AGREEMENT.split("\f"):
        y = 720
        c.setFont("Times-Roman", 11)
        for line in page.splitlines():
            c.drawString(72, y, line)
            y -= 15
        c.showPage()
    c.save()
    result, code = terms.check(p, release_only="Roe Holdings, LLC")
    assert result["pages"] == 2 and result["file"] == "agreement.pdf"
    assert row(result, "retained_jurisdiction")["hits"][0]["page"] == 2
    assert code == 1 and "Richard Roe" in result["problems"][0]
    out = terms.render(result)
    assert out.startswith("TERMS — agreement.pdf (2 pages read")


def test_a_file_with_no_text_says_so(tmp_path):
    p = str(tmp_path / "blank.txt")
    open(p, "w").close()
    result, code = terms.check(p)
    assert code == 1 and "No text could be read" in result["problems"][0]


def test_the_term_table_is_complete_and_its_patterns_compile():
    import re
    table = rules.terms()
    ids = [t["id"] for t in table["terms"]]
    assert len(ids) == len(set(ids))
    want = {"payment_amount", "payment_payor", "payment_due", "payment_method", "release", "release_mutual",
            "waiver_1542", "dismissal_with_prejudice", "dismissal_without_prejudice", "dismissal_complaint",
            "dismissal_cross_complaint", "lis_pendens", "property_instrument", "notarisation", "recording",
            "tax_allocation", "tax_forms", "confidentiality", "non_disparagement", "retained_jurisdiction",
            "fees_costs", "liens", "cure", "time_essence", "counterparts", "e_signature", "integration", "governing_law"}
    assert want <= set(ids)
    for t in table["terms"]:
        assert t["group"] in table["groups"] and t["label"] and t["th"], t["id"]
        for pat in t["patterns"]:
            re.compile(pat, re.I)


def test_the_example_agreement_on_disk_fires_release_only():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(root, "examples", "doe-v-roe", "agreements", "2026-09-17 settlement agreement.txt")
    assert os.path.exists(p), "run scripts/make_example.py"
    result, code = terms.check(p, release_only="Roe Holdings, LLC", expect_none=["confidentiality", "non_disparagement"])
    assert code == 1 and result["problems"] == ["--release-only Roe Holdings, LLC: the release also names Richard Roe."]
    assert row(result, "lis_pendens")["found"] and row(result, "notarisation")["found"] and row(result, "recording")["found"]
