"""The closing list: what is left to do after a settlement is signed, each date with its arithmetic.

    chirograph closing build --signed 2026-09-17 --payment-amount 120000 --payment-days 21 \\
        --payment-cite "Agreement §1" --instrument "Quitclaim deed" --instrument-sign-days 14 \\
        --hearing "2026-09-28 08:30 Case management conference"
    chirograph closing list
    chirograph closing done notice --state SERVED --evidence "evidence/2026-09-17 notice sent.txt"

Each task carries a chain of states, BUILT → SIGNED → SERVED → FILED → DONE for a court paper.
A state is entered only with `--evidence` naming a file on disk: a receipt, a sent message saved
as .txt, a conformed copy. A hearing stays ON CALENDAR until an order or the court's own page,
saved to disk, shows it is off.
"""
import datetime as _dt
import os

from . import courtdays as cd
from . import matter as _matter
from . import offers as _offers
from . import rules as _rules
from . import tz as _tz

FILE = "closing.json"
PAPER = ["BUILT", "SIGNED", "SERVED", "FILED", "DONE"]
CHAINS = {
    "notice": PAPER,
    "dismissal": PAPER,
    "retain": ["BUILT", "SIGNED", "FILED", "DONE"],
    "payment": ["DONE"],
    "instrument": ["BUILT", "SIGNED", "SERVED", "DONE"],
    "wire": ["BUILT", "SERVED", "DONE"],
    "tax": ["BUILT", "SIGNED", "SERVED", "DONE"],
    "lis_pendens": ["BUILT", "SIGNED", "FILED", "DONE"],
    "hearing": ["OFF CALENDAR"],
}
STATE_HELP = {
    "BUILT": "the paper exists as a file",
    "SIGNED": "signed (and notarised where the task says so)",
    "SERVED": "sent to the other side, or dispatched",
    "FILED": "accepted by the court or the recorder",
    "DONE": "finished: entered, received or delivered",
    "OFF CALENDAR": "an order or the court's page shows the hearing is off",
}
NO_EVIDENCE = "no evidence on this disk"


def load(matter_dir):
    data = _matter.read_json(matter_dir, FILE, {"facts": {}, "tasks": []})
    data.setdefault("facts", {})
    data.setdefault("tasks", [])
    return data


def save(matter_dir, data):
    return _matter.write_json(matter_dir, FILE, data)


# --------------------------------------------------------------------------- building

def _task(tid, kind, title, date=None, time="", line="", notes=None, rule=None, extra=None):
    t = {"id": tid, "kind": kind, "title": title, "date": date.isoformat() if date else "", "time": time or "",
         "line": line, "notes": list(notes or []), "rule": rule or "", "chain": list(CHAINS[kind]), "states": {}}
    if extra:
        t.update(extra)
    return t


def _dated(signed, spec, court, default_cite, prefix="Due", trigger_phrase="signed"):
    """A date from a fact: {"date": ...} as given, or {"days": n, "unit": ..., "cite": ...} counted from signing.

    Returns (date or None, line, notes).
    """
    spec = spec or {}
    cite = spec.get("cite") or default_cite
    if spec.get("date"):
        d = cd.parse_date(spec["date"])
        return d, "%s %s — date stated in %s." % (prefix, cd.fmt_full(d), cite), []
    if spec.get("days") is not None and spec.get("days") != "":
        after = spec.get("after_date") or signed
        r = cd.after(after, int(spec["days"]), cite, court, unit=spec.get("unit", "calendar"),
                     roll_cite=(cite if spec.get("roll") else None), prefix=prefix,
                     trigger_phrase=spec.get("trigger_phrase") or trigger_phrase)
        notes = list(r.notes)
        if notes:
            notes.append("The agreement's own counting clause decides whether this date moves.")
        return r.date, r.line, notes
    return None, "No date in the closing facts.", []


def build_tasks(facts, matter, rule_dir=None):
    """The task list from the closing facts. Pure: nothing is read from or written to disk."""
    court = _rules.court(rule_dir)
    table = _rules.settlement(rule_dir)
    roll_cite = table["counting"]["roll_cite"]
    cur = matter.get("currency") or "$"
    if not facts.get("signed"):
        raise cd.RuleError("the closing facts need the date the settlement was signed (--signed YYYY-MM-DD)")
    signed = cd.parse_date(facts["signed"])
    tasks = []
    hearings = facts.get("hearings") or []

    # 1. notice of settlement
    r_notice = _rules.rule("ca.notice_of_settlement", rule_dir)
    conditional = bool(facts.get("conditional"))
    what = "Notice of conditional settlement" if conditional else "Notice of settlement of the entire case"
    line = "Due %s — settled %s; written notice is filed and served immediately (%s)." % (
        cd.fmt_full(signed), cd.fmt(signed, signed.year, weekday=False), r_notice["cite"])
    notes = []
    r_oral = _rules.rule("ca.oral_notice_window", rule_dir)
    for h in hearings:
        hd = cd.parse_date(h["date"])
        if signed <= hd <= signed + _dt.timedelta(days=int(r_oral["days"])):
            notes.append("%s on %s falls within %d days of settlement: the rule also calls for oral notice at once (%s)." % (
                h.get("title", "A hearing"), cd.fmt_full(hd), r_oral["days"], r_oral["cite"]))
    r_neutral = _rules.rule("ca.neutral_notice", rule_dir)
    for h in hearings:
        if (h.get("kind") or "") in ("adr", "mediation", "arbitration"):
            hd = cd.parse_date(h["date"])
            by = hd - _dt.timedelta(days=int(r_neutral["days"]))
            notes.append("Notify the neutral of the settlement by %s — session %s − %d days (%s)." % (
                cd.fmt_full(by), cd.fmt(hd, by.year), r_neutral["days"], r_neutral["cite"]))
    if conditional:
        r_cn = _rules.rule("ca.conditional_notice", rule_dir)
        notes.append("A conditional notice names the date by which the dismissal is to be filed (%s)." % r_cn["cite"])
    tasks.append(_task("notice", "notice", what, signed, "", line, notes, r_notice["id"]))

    # 2. performance dates from the agreement
    last_performance = signed
    pay = facts.get("payment") or {}
    if pay:
        d, line, notes = _dated(signed, pay, court, "the agreement")
        title = "Payment of %s%s" % (_offers.money(pay.get("amount"), cur) if pay.get("amount") is not None else "the settlement amount",
                                     (" by %s" % pay["payor"]) if pay.get("payor") else "")
        if pay.get("method"):
            title += " (%s)" % pay["method"]
        tasks.append(_task("payment", "payment", title, d, pay.get("time", ""), line, notes))
        if d and d > last_performance:
            last_performance = d
    wire = facts.get("wire") or {}
    if wire:
        d, line, notes = _dated(signed, wire, court, "the agreement")
        tasks.append(_task("wire", "wire", "Wire instructions to the paying side", d, "", line, notes))
    tax = facts.get("tax_form") or {}
    if tax:
        d, line, notes = _dated(signed, tax, court, "the agreement")
        tasks.append(_task("tax", "tax", "%s to the paying side" % (tax.get("title") or "Taxpayer form (W-9 or the form the agreement names)"),
                           d, "", line, notes))
    for n, ins in enumerate(facts.get("instruments") or [], 1):
        base = "instrument" if n == 1 else "instrument%d" % n
        title = ins.get("title") or "Instrument"
        how = "before a notary or, for a signer abroad, a consular officer" if ins.get("signer_abroad") else "before a notary"
        d, line, notes = _dated(signed, ins.get("sign") or {}, court, ins.get("cite") or "the agreement")
        tasks.append(_task(base + "-sign", "instrument", "%s signed %s" % (title, how), d, "", line, notes,
                           extra={"chain": ["BUILT", "SIGNED"]}))
        if ins.get("dispatch"):
            d2, line2, notes2 = _dated(signed, ins["dispatch"], court, ins.get("cite") or "the agreement")
            tasks.append(_task(base + "-dispatch", "instrument", "%s dispatched by tracked courier" % title, d2, "", line2, notes2,
                               extra={"chain": ["SERVED", "DONE"]}))
            d = d2 or d
        if ins.get("outside"):
            d3, line3, notes3 = _dated(signed, ins["outside"], court, ins.get("cite") or "the agreement", prefix="Outside date")
            tasks.append(_task(base + "-outside", "instrument", "%s: outside date for delivery" % title, d3, "", line3, notes3,
                               extra={"chain": ["DONE"]}))
            d = d3 or d
        if d and d > last_performance:
            last_performance = d
    lp = facts.get("lis_pendens") or {}
    if lp:
        d, line, notes = _dated(signed, lp, court, "the agreement")
        tasks.append(_task("lis-pendens", "lis_pendens", "Withdrawal of the lis pendens (the recorded notice of the pending case), recorded",
                           d, "", line, notes))
        if d and d > last_performance:
            last_performance = d

    # 3. dismissal
    r_dis = _rules.rule("ca.dismissal", rule_dir)
    day45 = signed + _dt.timedelta(days=int(r_dis["days"]))
    r_more = _rules.rule("ca.more_time", rule_dir)
    if conditional:
        r_cd = _rules.rule("ca.conditional_dismissal", rule_dir)
        if not facts.get("dismissal_date"):
            raise cd.RuleError("a conditional settlement needs the dismissal date named in the notice (--dismissal-date)")
        dd = cd.parse_date(facts["dismissal_date"])
        line = "Due %s — the dismissal date named in the notice of conditional settlement (%s)." % (
            cd.fmt_full(dd), _rules.rule("ca.conditional_notice", rule_dir)["cite"])
        court_date = cd.after(dd, r_cd["days"], r_cd["cite"], court, roll_cite=roll_cite, prefix="Court's date",
                              trigger_phrase="dismissal date")
        notes = ["If no request is on file, the court dismisses the case: %s" % court_date.line]
        r_h = _rules.rule("ca.conditional_hearings", rule_dir)
        notes.append("On the filing of the conditional notice the court is to vacate hearings that need a party's appearance (%s). "
                     "Each hearing below stays ON CALENDAR here until an order or the court's page is saved as evidence." % r_h["cite"])
        tasks.append(_task("dismissal", "dismissal", "Request for dismissal of the entire case", dd, "", line, notes, r_cd["id"]))
        dismissal_date = dd
    else:
        res = cd.after(signed, r_dis["days"], r_dis["cite"], court, roll_cite=roll_cite, trigger_phrase="settled",
                       rule_id=r_dis["id"])
        notes = list(res.notes)
        more = cd.before(res.date, r_more["days"], r_more["cite"], court, unit=r_more["unit"],
                         prefix="Last day", anchor_phrase="last day to request dismissal")
        notes.append("If the case cannot be dismissed in time, a notice and declaration asking for more time: %s" % more.line)
        if last_performance > day45:
            r_cn = _rules.rule("ca.conditional_notice", rule_dir)
            notes.append("A term in the closing facts runs to %s, past day 45 (%s). Terms not to be performed within 45 days "
                         "are the case for a notice of conditional settlement (%s); the facts say this settlement is not conditional." % (
                             cd.fmt_full(last_performance), cd.fmt_full(day45), r_cn["cite"]))
        tasks.append(_task("dismissal", "dismissal", "Request for dismissal of the entire case", res.date, "", res.line, notes, r_dis["id"]))
        dismissal_date = res.date

    # 4. retained jurisdiction
    if facts.get("retain_jurisdiction"):
        r_ret = _rules.rule("ca.retain_jurisdiction", rule_dir)
        line = "Due %s — on file before or with the request for dismissal; the court may dismiss without prejudice and retain jurisdiction when the parties stipulate in writing or orally before the court (%s)." % (
            cd.fmt_full(dismissal_date), r_ret["cite"])
        tasks.append(_task("retain", "retain", "Stipulation for the court to retain jurisdiction to enforce the settlement",
                           dismissal_date, "", line, [], r_ret["id"]))

    # 5. hearings still on calendar
    for n, h in enumerate(hearings, 1):
        hd = cd.parse_date(h["date"])
        cd.parse_time(h.get("time"))
        src = h.get("order") or ""
        line = "%s%s — %s. Stays ON CALENDAR until an order or the court's page, saved to disk, shows it is off." % (
            cd.fmt_full(hd), (" %s court time" % h["time"]) if h.get("time") else "",
            ("set by %s" % src) if src else "no order or notice named for this hearing")
        tasks.append(_task("hearing-%d" % n, "hearing", h.get("title") or "Hearing", hd, h.get("time", ""), line, [],
                           extra={"order": src, "hearing_kind": h.get("kind") or "hearing"}))
    return tasks


def build(matter_dir, facts_update=None, rule_dir=None):
    """Merge new facts into closing.json, rebuild the tasks, and carry each task's states across."""
    data = load(matter_dir)
    facts = dict(data.get("facts") or {})
    for k, v in (facts_update or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(facts.get(k), dict):
            merged = dict(facts[k])
            merged.update({kk: vv for kk, vv in v.items() if vv is not None})
            facts[k] = merged
        else:
            facts[k] = v
    m = _matter.load(matter_dir)
    tasks = build_tasks(facts, m, rule_dir)
    old = {t["id"]: t for t in data.get("tasks") or []}
    for t in tasks:
        if t["id"] in old:
            t["states"] = old[t["id"]].get("states", {})
    data["facts"] = facts
    data["tasks"] = tasks
    data["matter"] = m.get("name", "")
    save(matter_dir, data)
    return data


# --------------------------------------------------------------------------- states

def current_state(task):
    """The furthest state in the chain that has a record, or ''."""
    cur = ""
    for st in task.get("chain", []):
        if st in (task.get("states") or {}):
            cur = st
    return cur


def advance(matter_dir, task_id, evidence, state=None, on=None):
    """Enter a state on a task. Returns (ok, message). Nothing changes without a file on disk."""
    data = load(matter_dir)
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if task is None:
        raise cd.RuleError("no task %r; `chirograph closing list` shows the ids" % task_id)
    chain = task["chain"]
    cur = current_state(task)
    if state:
        state = state.strip().upper().replace("_", " ").replace("-", " ")
        if state == "OFF":
            state = "OFF CALENDAR"
        if state not in chain:
            raise cd.RuleError("%s moves through: %s" % (task_id, " → ".join(chain)))
    else:
        idx = chain.index(cur) + 1 if cur else 0
        if idx >= len(chain):
            return False, "%s is already %s." % (task_id, cur)
        state = chain[idx]
    if cur and chain.index(state) < chain.index(cur):
        return False, "%s is already %s; %s comes before it." % (task_id, cur, state)
    shown = cur or ("ON CALENDAR" if task["kind"] == "hearing" else "not started")
    if not evidence:
        return False, "%s: %s; %s stays %s. Name the file with --evidence." % (task_id, NO_EVIDENCE, task_id, shown)
    if not _matter.on_disk(matter_dir, evidence):
        return False, "%s: %s: %s; %s stays %s." % (task_id, NO_EVIDENCE, evidence, task_id, shown)
    day = cd.parse_date(on) if on else _dt.date.today()
    task.setdefault("states", {})[state] = {"evidence": _matter.relative(matter_dir, evidence), "on": day.isoformat()}
    save(matter_dir, data)
    _matter.done_line(matter_dir, "%s — %s: %s (evidence: %s)" % (task["title"], task_id, state,
                                                                 _matter.relative(matter_dir, evidence)), day)
    return True, "%s is %s (evidence: %s)." % (task_id, state, _matter.relative(matter_dir, evidence))


# --------------------------------------------------------------------------- listing

class Row(object):
    def __init__(self, task, state, next_state, flags, both):
        self.task = task
        self.state = state
        self.next_state = next_state
        self.flags = flags
        self.both = both

    @property
    def id(self):
        return self.task["id"]

    @property
    def date(self):
        return cd.parse_date(self.task["date"]) if self.task.get("date") else None

    @property
    def finished(self):
        return bool(self.state) and self.state == self.task["chain"][-1]

    @property
    def shown(self):
        if self.task["kind"] == "hearing":
            return self.state or "ON CALENDAR"
        return self.state or "not started"

    def as_dict(self):
        t = dict(self.task)
        t.update({"state_now": self.shown, "next_state": self.next_state, "flags": self.flags, "both": self.both,
                  "finished": self.finished})
        return t


def rows(matter_dir):
    m = _matter.load(matter_dir)
    court_tz = m.get("court_tz") or "America/Los_Angeles"
    reader_tz = m.get("reader_tz") or ""
    out = []
    for t in load(matter_dir)["tasks"]:
        flags = []
        for st, rec in (t.get("states") or {}).items():
            if not _matter.on_disk(matter_dir, rec.get("evidence")):
                flags.append("%s names evidence that is not on this disk: %s" % (st, rec.get("evidence")))
        cur = current_state(t)
        chain = t["chain"]
        nxt = ""
        if not cur:
            nxt = chain[0]
        elif chain.index(cur) + 1 < len(chain):
            nxt = chain[chain.index(cur) + 1]
        if t["kind"] == "hearing" and t.get("order") and not _matter.on_disk(matter_dir, t["order"]):
            flags.append("the order or notice named for this hearing is not on this disk: %s" % t["order"])
        both = None
        if t.get("date"):
            both = _tz.both(cd.parse_date(t["date"]), t.get("time") or "", court_tz, reader_tz)
        out.append(Row(t, cur, nxt, flags, both))
    return m, out


def render(matter_dir, today=None):
    m, rws = rows(matter_dir)
    court_tz = m.get("court_tz") or "America/Los_Angeles"
    today = cd.parse_date(today) if today else _tz.today(court_tz)
    data = load(matter_dir)
    lines = ["CLOSING — %s (court date %s)" % (m.get("name", ""), cd.fmt_full(today))]
    signed = (data.get("facts") or {}).get("signed")
    if not rws:
        lines += ["", "No closing list yet. `chirograph closing build --signed YYYY-MM-DD ...` makes one."]
        return "\n".join(lines), rws
    lines.append("Signed %s. Court zone %s%s." % (cd.fmt_full(cd.parse_date(signed)), court_tz,
                                               ("; reader zone %s" % m["reader_tz"]) if m.get("reader_tz") else ""))
    lines.append("")
    for r in rws:
        t = r.task
        when = ""
        if r.date and not r.finished:
            delta = (r.date - today).days
            when = " · today" if delta == 0 else (" · in %d day%s" % (delta, "" if delta == 1 else "s") if delta > 0
                                                  else " · %d day%s past" % (-delta, "" if delta == -1 else "s"))
        lines.append("%s  [%s]  %s%s" % (t["id"], r.shown, t["title"], when))
        lines.append("    %s" % t["line"])
        if r.both:
            lines.append("    %s" % r.both)
        for n in t.get("notes") or []:
            lines.append("    Note: %s" % n)
        for st in t["chain"]:
            rec = (t.get("states") or {}).get(st)
            if rec:
                lines.append("    %s %s — evidence: %s" % (st, rec.get("on", ""), rec.get("evidence", "")))
        if r.next_state:
            lines.append("    %s: %s" % (r.next_state, NO_EVIDENCE))
        for f in r.flags:
            lines.append("    FLAG: %s" % f)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", rws
