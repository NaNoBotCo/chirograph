"""Court-day counting and a date that carries its arithmetic.

Vendored and cut down from Cursitor (cursitor/deadlines.py), same author, MIT. A result is one
line: the date, then the steps that produced it, each with its citation.

    Due Mon Nov 2 2026 — settled Sep 17 + 45 days (Cal. Rules of Court, rule 3.1385(b)) = Sun Nov 1;
    Nov 1 is a Sunday; rolls to Mon Nov 2 (rule 1.10(b)).
"""
import datetime as _dt

from . import holidays as _hol

ONE = _dt.timedelta(days=1)


class RuleError(ValueError):
    pass


# --------------------------------------------------------------------------- formatting

def fmt(d, ref_year=None, weekday=True):
    """'Fri Sep 4' — the year is added when it differs from ref_year."""
    s = ("%s %s %d" % (d.strftime("%a"), d.strftime("%b"), d.day)) if weekday else \
        ("%s %d" % (d.strftime("%b"), d.day))
    if ref_year is not None and d.year != ref_year:
        s += " %d" % d.year
    return s


def fmt_full(d):
    return "%s %s %d %d" % (d.strftime("%a"), d.strftime("%b"), d.day, d.year)


def parse_date(s):
    if isinstance(s, _dt.datetime):
        return s.date()
    if isinstance(s, _dt.date):
        return s
    try:
        return _dt.date.fromisoformat(str(s).strip())
    except ValueError:
        raise RuleError("dates are written YYYY-MM-DD; got %r" % s)


def parse_time(s):
    """'17:00' -> (17, 0). Empty -> None."""
    if not s:
        return None
    try:
        hh, mm = [int(x) for x in str(s).strip().split(":")[:2]]
        if not (0 <= hh < 24 and 0 <= mm < 60):
            raise ValueError
        return hh, mm
    except ValueError:
        raise RuleError("times are written HH:MM on a 24-hour clock; got %r" % s)


# --------------------------------------------------------------------------- the court calendar

class Court:
    """Which days a court is open. `holidays` is the table key ('ca' or 'federal')."""

    def __init__(self, holidays="ca", extra_closed=None, table_dir=None):
        self.holidays = holidays
        self.extra = dict(extra_closed or {})
        self.table_dir = table_dir

    def holiday(self, d):
        name = self.extra.get(d)
        if name:
            return name
        return _hol.holiday_name(d, self.holidays, self.table_dir)

    def is_court_day(self, d):
        return d.weekday() < 5 and not self.holiday(d)

    def why_closed(self, d):
        h = self.holiday(d)
        if h:
            return h
        if d.weekday() == 5:
            return "a Saturday"
        if d.weekday() == 6:
            return "a Sunday"
        return None

    def add_court_days(self, start, n):
        """Count n court days after `start` (n<0 counts before). Returns (date, named holidays skipped)."""
        step = ONE if n >= 0 else -ONE
        d, left, skipped = start, abs(n), []
        while left:
            d += step
            if self.is_court_day(d):
                left -= 1
            else:
                h = self.holiday(d)
                if h:
                    skipped.append((d, h))
        return d, skipped

    def roll(self, d, backward=False):
        """Next court day on or after d (or on or before, counting backward). Returns (date, skipped)."""
        step = -ONE if backward else ONE
        skipped = []
        while not self.is_court_day(d):
            skipped.append((d, self.why_closed(d)))
            d += step
        return d, skipped


def skips_text(skipped, ref_year):
    named = sorted((d, n) for d, n in skipped if n and not n.startswith("a S"))
    if not named:
        return ""
    parts = ["%s %s" % (fmt(d, ref_year), n) for d, n in named]
    return ", skipping " + (parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1])


def roll_text(d, rolled, skipped, cite, ref_year, backward=False):
    first = skipped[0]
    reason = first[1]
    what = ("%s is %s" % (fmt(d, ref_year), reason)) if reason.startswith("a ") else \
           ("%s is %s, a court holiday" % (fmt(d, ref_year), reason))
    later = [(x, n) for x, n in skipped[1:] if n and not n.startswith("a S")]
    past = (", and %s" % " and ".join("%s is %s" % (fmt(x, ref_year), n) for x, n in later)) if later else ""
    verb = "moves earlier to" if backward else "rolls to"
    return "%s%s; %s %s (%s)" % (what, past, verb, fmt(rolled, ref_year), cite)


# --------------------------------------------------------------------------- results

class Result(object):
    def __init__(self, date, line, steps, rule_id=None, notes=None, trigger=None, time=None):
        self.date = date
        self.line = line
        self.steps = steps
        self.rule_id = rule_id
        self.notes = notes or []
        self.trigger = trigger
        self.time = time

    def as_dict(self):
        return {"date": self.date.isoformat() if self.date else None, "line": self.line,
                "rule": self.rule_id, "notes": self.notes, "time": self.time,
                "trigger": self.trigger.isoformat() if self.trigger else None}

    def __repr__(self):
        return "<Result %s>" % self.line


def after(trigger, n, cite, court=None, unit="calendar", roll_cite=None, prefix="Due",
          trigger_phrase="served", rule_id=None, notes=None):
    """A date n days after a trigger. With roll_cite, a last day on a closed day rolls forward.

    Without roll_cite the date stays where the count lands and a closed day is named in a note.
    """
    court = court or Court("ca")
    trigger = parse_date(trigger)
    r = _after(trigger, n, cite, court, unit, roll_cite, prefix, trigger_phrase, rule_id, notes, None)
    if trigger.year != r.date.year:
        # print the year on the dates that fall outside the due date's year
        r = _after(trigger, n, cite, court, unit, roll_cite, prefix, trigger_phrase, rule_id, notes, r.date.year)
    return r


def _after(trigger, n, cite, court, unit, roll_cite, prefix, trigger_phrase, rule_id, notes, ry):
    frags = []
    if unit == "court":
        base, skipped = court.add_court_days(trigger, int(n))
        frags.append("%s %s + %d court days (%s)%s = %s" % (
            trigger_phrase, fmt(trigger, ry, weekday=False), n, cite, skips_text(skipped, ry), fmt(base, ry)))
    else:
        base = trigger + _dt.timedelta(days=int(n))
        frags.append("%s %s + %d days (%s) = %s" % (
            trigger_phrase, fmt(trigger, ry, weekday=False), n, cite, fmt(base, ry)))
    d = base
    extra = []
    if not court.is_court_day(d):
        rolled, sk = court.roll(d)
        if roll_cite:
            frags.append(roll_text(d, rolled, sk, roll_cite, ry))
            d = rolled
        else:
            why = court.why_closed(d)
            extra.append("%s is %s; this date does not roll. The next court day is %s." % (
                fmt_full(d), why if why.startswith("a ") else why + ", a court holiday", fmt_full(rolled)))
    line = "%s %s — %s." % (prefix, fmt_full(d), "; ".join(frags))
    return Result(d, line, frags, rule_id, list(notes or []) + extra, trigger)


def before(anchor, n, cite, court=None, unit="court", prefix="Due", anchor_phrase="hearing",
           roll_cite="CCP §12c", rule_id=None, notes=None):
    """A date n days before an anchor. A result on a closed day moves to the court day before."""
    court = court or Court("ca")
    anchor = parse_date(anchor)
    ry = anchor.year
    frags = []
    if unit == "court":
        d, skipped = court.add_court_days(anchor, -int(n))
        frags.append("%s %s − %d court days (%s)%s = %s" % (
            anchor_phrase, fmt(anchor, ry), n, cite, skips_text(skipped, ry), fmt(d, ry)))
    else:
        d = anchor - _dt.timedelta(days=int(n))
        frags.append("%s %s − %d days (%s) = %s" % (anchor_phrase, fmt(anchor, ry), n, cite, fmt(d, ry)))
        if not court.is_court_day(d):
            rolled, sk = court.roll(d, backward=True)
            frags.append(roll_text(d, rolled, sk, roll_cite, ry, backward=True))
            d = rolled
    line = "%s %s — %s." % (prefix, fmt_full(d), "; ".join(frags))
    return Result(d, line, frags, rule_id, list(notes or []), anchor)
