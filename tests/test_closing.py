"""The closing list: dates with arithmetic, states that move only with evidence on disk."""
import datetime as dt
import os

from chirograph import closing
from chirograph import courtdays as cd
from chirograph import matter

D = dt.date


def make(tmp_path, reader_tz=""):
    m = str(tmp_path / "doe")
    matter.scaffold(m, "Jane Doe", "Roe Holdings, LLC", "26CV000000", "Alameda", reader_tz=reader_tz)
    return m


def doc(m, rel, body="x"):
    p = os.path.join(m, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return rel


def task(m, tid):
    return [t for t in closing.load(m)["tasks"] if t["id"] == tid][0]


FACTS = {
    "signed": "2026-09-17",
    "payment": {"amount": 120000, "payor": "Roe Holdings, LLC", "days": 21, "cite": "Agreement §1"},
    "instruments": [{"title": "Quitclaim deed", "signer_abroad": True, "cite": "Agreement §6",
                     "sign": {"days": 14}, "dispatch": {"days": 14}, "outside": {"days": 28}}],
    "retain_jurisdiction": True,
    "hearings": [{"date": "2026-09-24", "time": "09:00", "title": "Case management conference", "order": "received/cmc.txt"}],
}


def test_the_closing_facts_need_a_signing_date(tmp_path):
    m = make(tmp_path)
    try:
        closing.build(m, {"payment": {"days": 5}})
        assert False
    except cd.RuleError as exc:
        assert "--signed" in str(exc)


def test_notice_of_settlement_is_due_the_day_the_case_settles(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    t = task(m, "notice")
    assert t["date"] == "2026-09-17" and t["chain"] == ["BUILT", "SIGNED", "SERVED", "FILED", "DONE"]
    assert t["line"] == ("Due Thu Sep 17 2026 — settled Sep 17; written notice is filed and served immediately "
                         "(Cal. Rules of Court, rule 3.1385(a)(1)).")


def test_oral_notice_note_when_a_hearing_is_within_10_days(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    assert any("within 10 days of settlement" in n and "oral notice" in n for n in task(m, "notice")["notes"])
    far = dict(FACTS, hearings=[{"date": "2026-09-28", "time": "09:00", "title": "Case management conference"}])
    closing.build(m, far)                                      # day 11
    assert not any("oral notice" in n for n in task(m, "notice")["notes"])


def test_a_neutral_gets_two_days_notice(tmp_path):
    m = make(tmp_path)
    closing.build(m, dict(FACTS, hearings=[{"date": "2026-10-06", "time": "09:30", "title": "Mediation session", "kind": "adr"}]))
    notes = task(m, "notice")["notes"]
    assert any(n.startswith("Notify the neutral of the settlement by Sun Oct 4 2026") and "rule 3.1385(a)(2)" in n for n in notes)


def test_dismissal_is_45_days_out_and_rolls_under_rule_1_10(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    t = task(m, "dismissal")
    assert t["date"] == "2026-11-02"
    assert t["line"] == ("Due Mon Nov 2 2026 — settled Sep 17 + 45 days (Cal. Rules of Court, rule 3.1385(b)) = Sun Nov 1; "
                         "Sun Nov 1 is a Sunday; rolls to Mon Nov 2 (Cal. Rules of Court, rule 1.10(b)).")
    assert any("asking for more time" in n and "Mon Oct 26 2026" in n and "rule 3.1385(e)" in n for n in t["notes"])


def test_dismissal_rolls_past_thanksgiving(tmp_path):
    m = make(tmp_path)
    closing.build(m, {"signed": "2026-10-12"})
    assert task(m, "dismissal")["date"] == "2026-11-30"


def test_a_term_past_day_45_is_flagged_when_the_settlement_is_not_conditional(tmp_path):
    m = make(tmp_path)
    closing.build(m, {"signed": "2026-09-17", "payment": {"amount": 5000, "days": 90, "cite": "Agreement §2"}})
    assert any("past day 45" in n and "rule 3.1385(c)(1)" in n for n in task(m, "dismissal")["notes"])
    closing.build(m, FACTS)
    assert not any("past day 45" in n for n in task(m, "dismissal")["notes"])


def test_conditional_settlement_uses_the_date_named_in_the_notice(tmp_path):
    m = make(tmp_path)
    try:
        closing.build(m, {"signed": "2026-09-17", "conditional": True})
        assert False
    except cd.RuleError as exc:
        assert "--dismissal-date" in str(exc)
    closing.build(m, {"signed": "2026-09-17", "conditional": True, "dismissal_date": "2027-03-01",
                      "hearings": FACTS["hearings"]})
    assert task(m, "notice")["title"] == "Notice of conditional settlement"
    t = task(m, "dismissal")
    assert t["date"] == "2027-03-01" and "rule 3.1385(c)(1)" in t["line"]
    assert any("Court's date Thu Apr 15 2027" in n and "rule 3.1385(c)(2)" in n for n in t["notes"])
    assert any("vacate hearings" in n and "stays ON CALENDAR" in n for n in t["notes"])


def test_payment_and_instrument_dates_carry_the_agreements_section(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    assert task(m, "payment")["line"] == "Due Thu Oct 8 2026 — signed Sep 17 + 21 days (Agreement §1) = Thu Oct 8."
    assert task(m, "payment")["title"] == "Payment of $120,000 by Roe Holdings, LLC"
    assert task(m, "instrument-sign")["date"] == "2026-10-01" and "consular officer" in task(m, "instrument-sign")["title"]
    assert task(m, "instrument-outside")["line"].startswith("Outside date Thu Oct 15 2026 — signed Sep 17 + 28 days (Agreement §6)")
    assert task(m, "retain")["rule"] == "ca.retain_jurisdiction" and "CCP §664.6(a)" in task(m, "retain")["line"]


def test_an_agreement_date_on_a_weekend_is_not_moved(tmp_path):
    m = make(tmp_path)
    closing.build(m, {"signed": "2026-09-17", "payment": {"days": 23, "cite": "Agreement §1"}})
    t = task(m, "payment")
    assert t["date"] == "2026-10-10"
    assert any("a Saturday; this date does not roll" in n for n in t["notes"])
    assert any("agreement's own counting clause" in n for n in t["notes"])


def test_a_state_is_entered_only_with_a_file_on_disk(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    ok, msg = closing.advance(m, "notice", None)
    assert not ok and "no evidence on this disk" in msg and "stays not started" in msg
    ok, msg = closing.advance(m, "notice", "evidence/nope.txt")
    assert not ok and msg == "notice: no evidence on this disk: evidence/nope.txt; notice stays not started."
    assert closing.current_state(task(m, "notice")) == ""
    ok, msg = closing.advance(m, "notice", doc(m, "evidence/built.txt"), on="2026-09-17")
    assert ok and msg == "notice is BUILT (evidence: evidence/built.txt)."
    assert task(m, "notice")["states"]["BUILT"] == {"evidence": "evidence/built.txt", "on": "2026-09-17"}


def test_states_move_forward_through_the_chain(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    ev = doc(m, "evidence/e.txt")
    for want in ("BUILT", "SIGNED", "SERVED"):
        ok, _msg = closing.advance(m, "notice", ev)
        assert ok and closing.current_state(task(m, "notice")) == want
    ok, msg = closing.advance(m, "notice", ev, "BUILT")
    assert not ok and "already SERVED" in msg
    ok, _msg = closing.advance(m, "notice", ev, "filed")
    assert ok and closing.current_state(task(m, "notice")) == "FILED"
    try:
        closing.advance(m, "notice", ev, "NOTARISED")
        assert False
    except cd.RuleError as exc:
        assert "BUILT → SIGNED → SERVED → FILED → DONE" in str(exc)
    try:
        closing.advance(m, "no-such-task", ev)
        assert False
    except cd.RuleError:
        pass
    ok, _msg = closing.advance(m, "notice", ev)
    ok, msg = closing.advance(m, "notice", ev)
    assert not ok and msg == "notice is already DONE."


def test_each_move_is_a_dated_line_in_the_ledger(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    closing.advance(m, "notice", doc(m, "evidence/sent.txt"), "SERVED", "2026-09-18")
    with open(os.path.join(m, "DONE.md"), encoding="utf-8") as fh:
        last = fh.read().strip().splitlines()[-1]
    assert last == "2026-09-18 Notice of settlement of the entire case — notice: SERVED (evidence: evidence/sent.txt)"


def test_a_hearing_stays_on_calendar_until_evidence_shows_it_off(tmp_path):
    m = make(tmp_path, reader_tz="Asia/Bangkok")
    closing.build(m, FACTS)
    _m, rws = closing.rows(m)
    h = [r for r in rws if r.id == "hearing-1"][0]
    assert h.shown == "ON CALENDAR" and not h.finished
    assert h.both == "Thu Sep 24 2026 09:00 court time = Thu Sep 24 2026 23:00 in Asia/Bangkok."
    assert any("not on this disk: received/cmc.txt" in f for f in h.flags)
    ok, msg = closing.advance(m, "hearing-1", "received/minute order.txt", "OFF")
    assert not ok and "hearing-1 stays ON CALENDAR" in msg
    ok, _msg = closing.advance(m, "hearing-1", doc(m, "received/minute order.txt"), "OFF")
    assert ok
    _m, rws = closing.rows(m)
    assert [r for r in rws if r.id == "hearing-1"][0].shown == "OFF CALENDAR"


def test_rebuilding_the_list_carries_the_states_across(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    closing.advance(m, "notice", doc(m, "evidence/built.txt"))
    closing.build(m, {"payment": {"days": 30}})               # one fact changes
    assert closing.current_state(task(m, "notice")) == "BUILT"
    assert task(m, "payment")["date"] == "2026-10-17"
    assert closing.load(m)["facts"]["payment"]["amount"] == 120000   # the other payment facts stay


def test_evidence_that_leaves_the_disk_is_flagged(tmp_path):
    m = make(tmp_path)
    closing.build(m, FACTS)
    closing.advance(m, "notice", doc(m, "evidence/built.txt"))
    os.remove(os.path.join(m, "evidence", "built.txt"))
    _m, rws = closing.rows(m)
    n = [r for r in rws if r.id == "notice"][0]
    assert n.flags == ["BUILT names evidence that is not on this disk: evidence/built.txt"]


def test_the_list_prints_both_zones_on_either_side_of_the_clock_change(tmp_path):
    m = make(tmp_path, reader_tz="Asia/Bangkok")
    closing.build(m, FACTS)
    text, _rows = closing.render(m, "2026-09-21")
    # payment Oct 8 is in daylight time (+14 h); dismissal Nov 2 is in standard time (+15 h)
    assert "End of Thu Oct 8 2026 court time (23:59) = Fri Oct 9 2026 13:59 in Asia/Bangkok." in text
    assert "End of Mon Nov 2 2026 court time (23:59) = Tue Nov 3 2026 14:59 in Asia/Bangkok." in text
    assert "FILED: no evidence on this disk" not in text and "BUILT: no evidence on this disk" in text
    assert "notice  [not started]  Notice of settlement of the entire case · 4 days past" in text


def test_an_empty_closing_list_says_how_to_build_one(tmp_path):
    m = make(tmp_path)
    text, rws = closing.render(m, "2026-09-21")
    assert rws == [] and "closing build --signed" in text
