"""The ladder: offers, statuses, positions and clocks."""
import datetime as dt
import json
import os

from chirograph import courtdays as cd
from chirograph import matter
from chirograph import offers

D = dt.date


def make(tmp_path, reader_tz="", trial=""):
    m = str(tmp_path / "doe")
    matter.scaffold(m, "Jane Doe", "Roe Holdings, LLC", "26CV000000", "Alameda", reader_tz=reader_tz, trial_date=trial)
    return m


def doc(m, rel, body="x"):
    p = os.path.join(m, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return rel


def view(m, oid, today):
    _m, _t, views = offers.evaluate(m, today)
    return [v for v in views if v.id == oid][0]


def test_new_matter_writes_the_settlement_files(tmp_path):
    m = make(tmp_path, reader_tz="Europe/London")
    for f in ("matter.json", "offers.json", "closing.json", "STATUS.md", "DONE.md", "muzzles.txt", "CLAUDE.md"):
        assert os.path.exists(os.path.join(m, f)), f
    data = matter.load(m)
    assert data["case_number"] == "26CV000000" and data["reader_tz"] == "Europe/London"
    assert data["court"] == "Superior Court of California, County of Alameda"
    assert matter.find(os.path.join(m, "offers")) == m


def test_offers_get_ids_and_sort_by_date(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000)
    offers.add(m, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", "240,000")
    rows = offers.load(m)["offers"]
    assert [o["id"] for o in rows] == ["O2", "O1"]            # ids in entry order, list in date order
    assert rows[0]["amount"] == 240000 and rows[0]["side"] == "plaintiff" and rows[1]["side"] == "defendant"


def test_a_mediators_proposal_is_from_neither_side(tmp_path):
    m = make(tmp_path)
    o = offers.add(m, "2026-09-09", "Pat Example", "both sides", "mediator", 120000)
    assert o["side"] == "neutral"
    assert offers.norm_kind("counter-offer") == "counter" and offers.norm_kind("§998") == "998"
    try:
        offers.norm_kind("handshake")
        assert False
    except cd.RuleError:
        pass


def test_statutory_offer_gets_the_30_day_clock_with_its_arithmetic(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"))
    v = view(m, "O1", "2026-08-28")
    assert v.status == "OPEN" and v.running
    assert v.clock.date == D(2026, 9, 11) and v.clock.source == "statute"
    assert v.clock.line == "Lapses Fri Sep 11 2026 — made Aug 12 + 30 days (CCP §998(b)(2)) = Fri Sep 11."


def test_a_statutory_clock_on_a_weekend_is_not_rolled(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-13", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"))
    v = view(m, "O1", "2026-08-28")
    assert v.clock.date == D(2026, 9, 12)
    assert any("a Saturday; this date does not roll" in n for n in v.clock.notes)


def test_service_extension_is_left_off_unless_asked_for(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, method="email", document=doc(m, "offers/a.txt"))
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 61000, method="email", document=doc(m, "offers/b.txt"), extend=True)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 62000, method="mail", document=doc(m, "offers/c.txt"), extend=True)
    plain, ext, mail = view(m, "O1", "2026-08-20"), view(m, "O2", "2026-08-20"), view(m, "O3", "2026-08-20")
    assert plain.clock.date == D(2026, 9, 11)
    assert any("does not add the 2 court days in CCP §1010.6(a)(3)(B)" in n and "from memory, not read" in n for n in plain.clock.notes)
    assert ext.clock.date == D(2026, 9, 15)
    assert "+ 2 court days e-service (CCP §1010.6(a)(3)(B)) = Tue Sep 15" in ext.clock.line
    assert any("entered with --extend" in n and "Poster" in n and "from memory, not read" in n for n in ext.clock.notes)
    assert mail.clock.date == D(2026, 9, 16) and "+ 5 days mail within California (CCP §1013(a))" in mail.clock.line


def test_trial_comes_first_when_it_is_sooner(tmp_path):
    m = make(tmp_path, trial="2026-08-31")
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"))
    v = view(m, "O1", "2026-08-20")
    assert v.clock.date == D(2026, 8, 31)
    assert "trial starts Mon Aug 31, which comes first (CCP §998(b)(2))" in v.clock.line
    offers.add(m, "2026-08-25", "Roe Holdings, LLC", "Jane Doe", "998", 70000, document=doc(m, "offers/p.txt"))
    late = view(m, "O2", "2026-08-26")
    assert any("fewer than 10 days before trial" in n for n in late.clock.notes)


def test_expiry_stated_in_the_offer_wins(tmp_path):
    m = make(tmp_path, reader_tz="Asia/Bangkok")
    offers.add(m, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", 240000, document=doc(m, "offers/l.txt"),
               expires="2026-08-17", expires_time="17:00")
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"),
               expires="2026-08-31")
    letter, stat = view(m, "O1", "2026-08-10"), view(m, "O2", "2026-08-20")
    assert letter.clock.source == "stated" and letter.clock.date == D(2026, 8, 17)
    assert letter.clock.line == "Lapses Mon Aug 17 2026 at 17:00 court time — expiry stated in the offer (offers/l.txt)."
    assert letter.clock.both == "Mon Aug 17 2026 17:00 court time = Tue Aug 18 2026 07:00 in Asia/Bangkok."
    assert stat.clock.date == D(2026, 8, 31)
    assert any("statute's clock computes a different day" in n and "Fri Sep 11 2026" in n for n in stat.clock.notes)


def test_a_letter_with_no_expiry_has_no_clock(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000, document=doc(m, "offers/c.txt"))
    v = view(m, "O1", "2027-01-01")
    assert v.clock is None and v.status == "OPEN" and not v.running
    text, _v = offers.render(m, "2027-01-01")
    assert "O1: no expiry stated and no rule supplies one." in text


def test_open_only_when_the_document_is_on_disk(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document="offers/not-here.txt")
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000)
    a, b = view(m, "O1", "2026-08-20"), view(m, "O2", "2026-08-20")
    assert a.status == "UNSOURCED" and "document not on this disk: offers/not-here.txt" in a.flags
    assert b.status == "UNSOURCED" and "no document named for this offer" in b.flags
    doc(m, "offers/not-here.txt")
    assert view(m, "O1", "2026-08-20").status == "OPEN"


def test_lapse_follows_from_the_date_and_the_offer_stays_in_the_file(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"))
    assert view(m, "O1", "2026-09-11").status == "OPEN"       # the last day
    v = view(m, "O1", "2026-09-12")
    assert v.status == "LAPSED" and not v.running
    stored = offers.load(m)["offers"]
    assert len(stored) == 1 and stored[0]["status"] == "open"  # nothing rewritten, nothing removed
    text, _v = offers.render(m, "2026-09-12")
    assert "Lapsed Fri Sep 11 2026 — made Aug 12 + 30 days" in text
    try:
        offers.decide(m, "O1", "lapsed")
        assert False
    except cd.RuleError as exc:
        assert "follows from the date" in str(exc)


def test_a_stated_time_of_day_counts_when_the_clock_is_read_with_a_time(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", 240000, document=doc(m, "offers/l.txt"),
               expires="2026-08-17", expires_time="17:00")
    from zoneinfo import ZoneInfo
    la = ZoneInfo("America/Los_Angeles")
    before = dt.datetime(2026, 8, 17, 16, 59, tzinfo=la)
    after = dt.datetime(2026, 8, 17, 17, 0, tzinfo=la)
    _m, _t, v1 = offers.evaluate(m, "2026-08-17", now=before)
    _m, _t, v2 = offers.evaluate(m, "2026-08-17", now=after)
    assert v1[0].status == "OPEN" and v2[0].status == "LAPSED"


def test_decisions_are_recorded_with_their_document(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000, document=doc(m, "offers/c.txt"))
    offers.decide(m, "O1", "rejected", "2026-09-02", doc(m, "offers/reply.txt"))
    v = view(m, "O1", "2026-09-03")
    assert v.status == "REJECTED" and v.flags == []
    offers.decide(m, "O1", "withdrawn", "2026-09-04")
    assert "no document named for the withdrawn decision" in view(m, "O1", "2026-09-05").flags
    try:
        offers.decide(m, "O9", "rejected")
        assert False
    except cd.RuleError:
        pass


def test_a_countered_statutory_offer_still_shows_its_clock(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/o.txt"))
    offers.add(m, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000, document=doc(m, "offers/c.txt"), answers="O1")
    offers.decide(m, "O1", "countered", "2026-08-26", "offers/c.txt", by="O2")
    v = view(m, "O1", "2026-08-28")
    assert v.status == "COUNTERED" and v.running
    text, _v = offers.render(m, "2026-08-28")
    assert "Marked COUNTERED. The clock is still shown" in text
    assert not view(m, "O1", "2026-09-12").running


def test_positions_gap_and_midpoint(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", 240000)
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000)
    offers.add(m, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000)
    offers.add(m, "2026-09-09", "Pat Example", "both sides", "mediator", 120000)
    _m, _t, views = offers.evaluate(m, "2026-09-10")
    pos = offers.positions(views)
    assert pos["plaintiff"].id == "O3" and pos["defendant"].id == "O2"
    assert pos["gap"] == 125000 and pos["midpoint"] == 122500
    text, _v = offers.render(m, "2026-09-10")
    assert "Gap $125,000 · midpoint $122,500" in text
    assert "Neutral (Pat Example): $120,000 — O4" in text


def test_accepted_offer_is_named_in_the_positions(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-09-09", "Pat Example", "both sides", "mediator", 120000, document=doc(m, "offers/p.txt"))
    offers.decide(m, "O1", "accepted", "2026-09-15", doc(m, "offers/yes.txt"))
    text, views = offers.render(m, "2026-09-21")
    assert "Accepted: $120,000 — O1, Tue Sep 15 2026" in text
    assert views[0].as_dict()["status_now"] == "ACCEPTED"


def test_money_and_amounts():
    assert offers.money(60000) == "$60,000" and offers.money(1234.5) == "$1,234.50" and offers.money(None) == "no amount"
    assert offers.parse_amount("$60,000.00") == 60000 and offers.parse_amount("") is None
    try:
        offers.parse_amount("sixty")
        assert False
    except cd.RuleError:
        pass


def test_answers_must_point_at_an_offer_in_the_ladder(tmp_path):
    m = make(tmp_path)
    try:
        offers.add(m, "2026-08-26", "Jane Doe", "Roe Holdings, LLC", "counter", 185000, answers="O7")
        assert False
    except cd.RuleError:
        pass


def test_a_document_inside_the_matter_is_stored_relative(tmp_path):
    m = make(tmp_path)
    p = os.path.join(m, doc(m, "offers/o.txt"))
    o = offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=p)
    assert o["document"] == os.path.join("offers", "o.txt")
    json.dumps(view(m, "O1", "2026-08-20").as_dict())          # the view is plain data
