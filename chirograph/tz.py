"""One moment in two zones: the court's and the reader's.

zoneinfo carries the daylight-saving rules, so Los Angeles to Bangkok is 14 hours in summer and
15 in winter without a table here.
"""
import datetime as _dt

from . import courtdays as cd

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None


def zone(name):
    if ZoneInfo is None:
        raise cd.RuleError("time zones need Python 3.9 or later")
    try:
        return ZoneInfo(name)
    except Exception:
        raise cd.RuleError("%r is not a known time zone (write it like America/Los_Angeles)" % name)


def moment(date, time_str, court_tz):
    """The aware datetime of a court date and time. No time means 23:59 court time, the end of the day."""
    hm = cd.parse_time(time_str) or (23, 59)
    return _dt.datetime(date.year, date.month, date.day, hm[0], hm[1], tzinfo=zone(court_tz))


def offset_hours(date, time_str, court_tz, reader_tz):
    """Hours the reader's clock is ahead of the court's at that moment."""
    m = moment(date, time_str, court_tz)
    there = m.astimezone(zone(reader_tz))
    delta = there.utcoffset() - m.utcoffset()
    return delta.total_seconds() / 3600.0


def both(date, time_str, court_tz, reader_tz):
    """'Mon Sep 28 2026 08:30 court time (America/Los_Angeles) = Mon Sep 28 2026 16:30 in Europe/London.'

    Returns None when there is no reader zone or it equals the court's.
    """
    if not reader_tz or reader_tz == court_tz:
        return None
    try:
        m = moment(date, time_str, court_tz)
        there = m.astimezone(zone(reader_tz))
    except cd.RuleError as exc:
        return str(exc)
    if time_str:
        left = "%s %s court time" % (cd.fmt_full(date), m.strftime("%H:%M"))
    else:
        left = "End of %s court time (23:59)" % cd.fmt_full(date)
    return "%s = %s %s in %s." % (left, cd.fmt_full(there.date()), there.strftime("%H:%M"), reader_tz)


def today(court_tz, now=None):
    """Today's date on the court's calendar."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.astimezone(zone(court_tz)).date()


def utc_stamp(date, time_str, court_tz):
    """'20260928T153000Z' for an .ics DTSTART."""
    m = moment(date, time_str, court_tz).astimezone(_dt.timezone.utc)
    return m.strftime("%Y%m%dT%H%M%SZ")
