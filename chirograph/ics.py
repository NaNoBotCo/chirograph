"""A calendar file (.ics) of the running clocks and the closing dates, the arithmetic in each event.

    chirograph ics [matter] [-o out/settlement.ics]

The .ics writer is vendored from Cursitor (cursitor/calendar_file.py), same author, MIT. A timed
event is written in UTC, worked out with zoneinfo from the court's zone, so a calendar app shows
it in the reader's own zone on either side of a clock change.
"""
import datetime as _dt

from . import brief as _brief
from . import tz as _tz


def _esc(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n"))


def _fold(line):
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def to_ics(matter_dir, today=None, now=None, rule_dir=None):
    """(ics text, number of events)."""
    m, today, views, rws, _its = _brief.items(matter_dir, today, rule_dir)
    court_tz = m.get("court_tz") or "America/Los_Angeles"
    now = now or _dt.datetime.utcnow()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Chirograph//settlement track//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    events = []
    for v in views:
        if v.running:
            desc = [v.clock.line] + ["Note: " + n for n in v.clock.notes]
            if v.clock.both:
                desc.append(v.clock.both)
            for f in v.flags:
                desc.append("FLAG: " + f)
            events.append(("offer-%s" % v.id, v.clock.date, v.clock.time,
                           "[%s] Offer %s lapses" % (v.status, v.id), desc, v.status == "OPEN"))
    for r in rws:
        if not r.date or r.finished:
            continue
        t = r.task
        desc = [t["line"]] + ["Note: " + n for n in (t.get("notes") or [])]
        if r.both:
            desc.append(r.both)
        desc.append("State: %s%s" % (r.shown, ("; next %s: no evidence on this disk" % r.next_state) if r.next_state else ""))
        for f in r.flags:
            desc.append("FLAG: " + f)
        events.append(("closing-%s" % t["id"], r.date, t.get("time") or "", "[%s] %s" % (r.shown, t["title"]), desc,
                       t["kind"] == "hearing"))
    for uid, date, time_str, summary, desc, confirmed in events:
        lines.append("BEGIN:VEVENT")
        lines.append("UID:%s@chirograph" % _esc(uid).replace(" ", "-"))
        lines.append("DTSTAMP:" + stamp)
        if time_str:
            start = _tz.utc_stamp(date, time_str, court_tz)
            end_dt = _tz.moment(date, time_str, court_tz).astimezone(_dt.timezone.utc) + _dt.timedelta(minutes=60)
            lines.append("DTSTART:" + start)
            lines.append("DTEND:" + end_dt.strftime("%Y%m%dT%H%M%SZ"))
        else:
            lines.append("DTSTART;VALUE=DATE:" + date.strftime("%Y%m%d"))
            lines.append("DTEND;VALUE=DATE:" + (date + _dt.timedelta(days=1)).strftime("%Y%m%d"))
        lines.append("SUMMARY:" + _esc(summary))
        lines.append("DESCRIPTION:" + _esc("\n".join(desc)))
        lines.append("STATUS:" + ("CONFIRMED" if confirmed else "TENTATIVE"))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(ln) for ln in lines) + "\r\n", len(events)
