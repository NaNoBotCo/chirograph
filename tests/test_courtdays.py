"""Court days, holidays and the two-zone clock."""
import datetime as dt

from chirograph import courtdays as cd
from chirograph import holidays as hol
from chirograph import tz

D = dt.date


def test_ca_2026_court_holidays_match_the_vendored_table():
    want = [D(2026, 1, 1), D(2026, 1, 19), D(2026, 2, 12), D(2026, 2, 16), D(2026, 3, 31), D(2026, 5, 25),
            D(2026, 6, 19), D(2026, 7, 3), D(2026, 9, 7), D(2026, 9, 25), D(2026, 11, 11), D(2026, 11, 26),
            D(2026, 11, 27), D(2026, 12, 25)]
    assert [r[0] for r in hol.closed_in(2026, "ca")] == want
    assert sorted(hol.load(2026, "ca").keys()) == want


def test_holiday_tables_name_this_project():
    assert hol.table(2026, "ca")["computed_by"] == "chirograph/holidays.py"


def test_court_days_skip_weekends_and_holidays():
    c = cd.Court("ca")
    d, skipped = c.add_court_days(D(2026, 9, 4), 1)          # Fri, then Sat, Sun, Labor Day
    assert d == D(2026, 9, 8)
    assert skipped == [(D(2026, 9, 7), "Labor Day")]


def test_after_rolls_only_with_a_roll_citation():
    r = cd.after("2026-09-17", 45, "rule 3.1385(b)", roll_cite="rule 1.10(b)", trigger_phrase="settled")
    assert r.date == D(2026, 11, 2)
    assert r.line == ("Due Mon Nov 2 2026 — settled Sep 17 + 45 days (rule 3.1385(b)) = Sun Nov 1; "
                      "Sun Nov 1 is a Sunday; rolls to Mon Nov 2 (rule 1.10(b)).")
    r2 = cd.after("2026-08-13", 30, "CCP §998(b)(2)", prefix="Lapses", trigger_phrase="made")
    assert r2.date == D(2026, 9, 12)                          # a Saturday, left where the count lands
    assert any("does not roll" in n and "Mon Sep 14 2026" in n for n in r2.notes)


def test_after_rolls_past_a_two_day_holiday():
    r = cd.after("2026-10-12", 45, "rule 3.1385(b)", roll_cite="rule 1.10(b)", trigger_phrase="settled")
    assert r.date == D(2026, 11, 30)                          # Thanksgiving, the day after, the weekend
    assert "Thanksgiving Day, a court holiday" in r.line


def test_year_is_printed_when_the_count_crosses_into_another_year():
    r = cd.after("2026-11-27", 45, "rule 3.1385(b)", roll_cite="rule 1.10(b)", trigger_phrase="settled")
    assert r.date == D(2027, 1, 11)
    assert "settled Nov 27 2026" in r.line and r.line.startswith("Due Mon Jan 11 2027")


def test_before_counts_court_days_back():
    r = cd.before("2026-11-02", 5, "rule 3.1385(e)", anchor_phrase="last day to request dismissal")
    assert r.date == D(2026, 10, 26)
    assert "− 5 court days (rule 3.1385(e))" in r.line


def test_dates_and_times_are_checked():
    for bad in ("17/09/2026", "Sept 17", ""):
        try:
            cd.parse_date(bad)
            assert False, bad
        except cd.RuleError:
            pass
    assert cd.parse_time("17:05") == (17, 5)
    assert cd.parse_time("") is None
    try:
        cd.parse_time("25:00")
        assert False
    except cd.RuleError:
        pass


def test_pacific_to_bangkok_is_14_hours_in_summer_and_15_in_winter():
    assert tz.offset_hours(D(2026, 7, 1), "10:00", "America/Los_Angeles", "Asia/Bangkok") == 14
    assert tz.offset_hours(D(2026, 12, 1), "10:00", "America/Los_Angeles", "Asia/Bangkok") == 15
    summer = tz.both(D(2026, 7, 1), "10:00", "America/Los_Angeles", "Asia/Bangkok")
    winter = tz.both(D(2026, 12, 1), "10:00", "America/Los_Angeles", "Asia/Bangkok")
    assert summer == "Wed Jul 1 2026 10:00 court time = Thu Jul 2 2026 00:00 in Asia/Bangkok."
    assert winter == "Tue Dec 1 2026 10:00 court time = Wed Dec 2 2026 01:00 in Asia/Bangkok."


def test_the_week_the_clocks_change_is_read_from_zoneinfo():
    # US clocks fall back Sun Nov 1 2026: Sat Oct 31 is +14, Mon Nov 2 is +15
    assert tz.offset_hours(D(2026, 10, 31), "09:00", "America/Los_Angeles", "Asia/Bangkok") == 14
    assert tz.offset_hours(D(2026, 11, 2), "09:00", "America/Los_Angeles", "Asia/Bangkok") == 15


def test_a_date_with_no_time_is_shown_at_the_end_of_the_court_day():
    line = tz.both(D(2026, 12, 1), "", "America/Los_Angeles", "Asia/Bangkok")
    assert line == "End of Tue Dec 1 2026 court time (23:59) = Wed Dec 2 2026 14:59 in Asia/Bangkok."
    assert tz.both(D(2026, 12, 1), "", "America/Los_Angeles", "") is None
    assert tz.both(D(2026, 12, 1), "", "America/Los_Angeles", "America/Los_Angeles") is None


def test_an_unknown_zone_is_named_in_the_line():
    assert "not a known time zone" in tz.both(D(2026, 12, 1), "", "America/Los_Angeles", "Mars/Olympus")


def test_utc_stamp_for_a_calendar_file():
    assert tz.utc_stamp(D(2026, 9, 24), "09:00", "America/Los_Angeles") == "20260924T160000Z"   # PDT
    assert tz.utc_stamp(D(2026, 12, 3), "09:00", "America/Los_Angeles") == "20261203T170000Z"   # PST
