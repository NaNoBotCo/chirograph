"""The brief: today, the next 7 days, clocks running, tasks with no evidence, offers open.

    chirograph brief [matter] [--today YYYY-MM-DD]
"""
import datetime as _dt

from . import closing as _closing
from . import courtdays as cd
from . import offers as _offers
from . import tz as _tz


def items(matter_dir, today=None, rule_dir=None):
    """Dated things still running: [(date, time, label, line, both)]."""
    m, today, views = _offers.evaluate(matter_dir, today, rule_dir=rule_dir)
    out = []
    for v in views:
        if v.running:
            out.append((v.clock.date, v.clock.time, "Offer %s lapses (%s, %s)" % (
                v.id, _offers.money(v.offer.get("amount"), m.get("currency") or "$"), v.status), v.clock.line, v.clock.both))
    _m, rws = _closing.rows(matter_dir)
    for r in rws:
        if r.date and not r.finished:
            out.append((r.date, r.task.get("time") or "", "%s [%s]" % (r.task["title"], r.shown), r.task["line"], r.both))
    out.sort(key=lambda x: (x[0], x[1] or "99:99"))
    return m, today, views, rws, out


def brief(matter_dir, today=None, rule_dir=None):
    m, today, views, rws, its = items(matter_dir, today, rule_dir)
    court_tz = m.get("court_tz") or "America/Los_Angeles"
    cur = m.get("currency") or "$"
    lines = ["BRIEF — %s" % m.get("name", ""),
             "Court date %s (%s)%s" % (cd.fmt_full(today), court_tz,
                                       ("; reader zone %s" % m["reader_tz"]) if m.get("reader_tz") else ""), ""]

    def show(rows):
        for d, t, label, line, both in rows:
            lines.append("  %s%s — %s" % (cd.fmt_full(d), (" " + t) if t else "", label))
            lines.append("      %s" % line)
            if both:
                lines.append("      %s" % both)

    past = [x for x in its if x[0] < today]
    now = [x for x in its if x[0] == today]
    week = [x for x in its if today < x[0] <= today + _dt.timedelta(days=7)]
    if past:
        lines.append("Past its date, not finished")
        show(past)
        lines.append("")
    lines.append("Today")
    if now:
        show(now)
    else:
        lines.append("  Nothing dated today.")
    lines.append("")
    lines.append("Next 7 days")
    if week:
        show(week)
    else:
        lines.append("  Nothing dated in the next 7 days.")
    lines.append("")
    lines.append("Clocks running")
    running = [v for v in views if v.running]
    if running:
        for v in running:
            left = (v.clock.date - today).days
            lines.append("  %s (%s): %s day%s left. %s" % (v.id, _offers.money(v.offer.get("amount"), cur), left,
                                                       "" if left == 1 else "s", v.clock.line))
    else:
        lines.append("  None.")
    lines.append("")
    lines.append("Tasks with no evidence on this disk")
    waiting = [r for r in rws if not r.finished and r.task["kind"] != "hearing"]
    if waiting:
        for r in waiting:
            lines.append("  %s [%s] — next: %s%s" % (r.task["title"], r.shown, r.next_state,
                                                    (", due %s" % cd.fmt_full(r.date)) if r.date else ""))
    else:
        lines.append("  None.")
    on_cal = [r for r in rws if r.task["kind"] == "hearing" and not r.finished]
    if on_cal:
        lines.append("")
        lines.append("Hearings still ON CALENDAR")
        for r in on_cal:
            lines.append("  %s — %s%s" % (r.task["title"], cd.fmt_full(r.date), (" " + r.task["time"]) if r.task.get("time") else ""))
            if r.both:
                lines.append("      %s" % r.both)
    lines.append("")
    lines.append("Offers open")
    open_ = [v for v in views if v.status in ("OPEN", "UNSOURCED")]
    if open_:
        for v in open_:
            lines.append("  %s %s → %s  %s  %s" % (v.id, v.offer["from"], v.offer["to"],
                                                 _offers.money(v.offer.get("amount"), cur), v.status))
            for f in v.flags:
                lines.append("      FLAG: %s" % f)
    else:
        lines.append("  None.")
    flags = [(r.id, f) for r in rws for f in r.flags]
    if flags:
        lines.append("")
        lines.append("Flags")
        for tid, f in flags:
            lines.append("  %s: %s" % (tid, f))
    return "\n".join(lines) + "\n"
