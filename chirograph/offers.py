"""The ladder: every offer and counter in date order, each side's last position, and the clocks.

    chirograph offer add --made 2026-08-12 --from "Roe Holdings, LLC" --to "Jane Doe" --kind 998 \\
        --amount 60000 --method email --document "offers/2026-08-12 offer to compromise.txt"
    chirograph offer list
    chirograph offer decide O2 rejected --on 2026-08-20 --document "offers/2026-08-20 reply.txt"

An offer shows OPEN only when the document that made it is on disk; otherwise UNSOURCED. A
statutory offer to compromise (CCP §998: a written offer to let judgment be entered on stated
terms, with cost consequences for the side that turns it down and then does no better) with no
stated expiry gets the clock in the rule table. A lapsed offer stays in the file, marked from
its date.
"""
import datetime as _dt
import os

from . import courtdays as cd
from . import matter as _matter
from . import rules as _rules
from . import tz as _tz

KINDS = {
    "letter": "letter",
    "998": "statutory offer (CCP §998)",
    "counter": "counter",
    "mediator": "mediator's proposal",
}
KIND_ALIASES = {"ccp998": "998", "§998": "998", "statutory": "998", "counteroffer": "counter",
                "counter-offer": "counter", "mediators-proposal": "mediator", "proposal": "mediator",
                "demand": "letter", "email": "letter"}
DECISIONS = ("rejected", "countered", "accepted", "withdrawn")
FILE = "offers.json"


def load(matter_dir):
    data = _matter.read_json(matter_dir, FILE, {"offers": []})
    data.setdefault("offers", [])
    return data


def save(matter_dir, data):
    return _matter.write_json(matter_dir, FILE, data)


def money(amount, currency="$"):
    if amount is None or amount == "":
        return "no amount"
    a = float(amount)
    if a == int(a):
        return "%s%s" % (currency, format(int(a), ","))
    return "%s%s" % (currency, format(a, ",.2f"))


def parse_amount(s):
    if s is None or s == "":
        return None
    try:
        v = float(str(s).replace(",", "").replace("$", "").strip())
    except ValueError:
        raise cd.RuleError("an amount is a number, like 60000 or 60,000.00; got %r" % s)
    return int(v) if v == int(v) else v


def norm_kind(kind):
    k = (kind or "letter").strip().lower()
    k = KIND_ALIASES.get(k, k)
    if k not in KINDS:
        raise cd.RuleError("kind is one of: %s" % ", ".join(sorted(KINDS)))
    return k


def next_id(data):
    n = 0
    for o in data["offers"]:
        try:
            n = max(n, int(str(o.get("id", "O0"))[1:]))
        except ValueError:
            pass
    return "O%d" % (n + 1)


def add(matter_dir, made, sender, to, kind="letter", amount=None, terms="", method=None, document="",
        expires=None, expires_time=None, answers=None, extend=False, side=None, offer_id=None, note=""):
    data = load(matter_dir)
    m = _matter.load(matter_dir)
    kind = norm_kind(kind)
    made = cd.parse_date(made)
    if expires:
        cd.parse_date(expires)
    cd.parse_time(expires_time)
    mkey = _rules.method(method)[0] if method else ""
    if side is None:
        side = "neutral" if kind == "mediator" else (_matter.side_of(m, sender) or "")
    if side not in ("plaintiff", "defendant", "neutral", ""):
        raise cd.RuleError("side is plaintiff, defendant or neutral")
    if answers and not any(o["id"] == answers for o in data["offers"]):
        raise cd.RuleError("no offer %s to answer" % answers)
    offer = {
        "id": offer_id or next_id(data),
        "made": made.isoformat(),
        "from": sender,
        "to": to,
        "side": side,
        "kind": kind,
        "amount": parse_amount(amount),
        "terms": terms or "",
        "method": mkey,
        "document": _matter.relative(matter_dir, document) if document else "",
        "expires": expires or "",
        "expires_time": expires_time or "",
        "extend_for_service": bool(extend),
        "answers": answers or "",
        "status": "open",
        "decided_on": "",
        "decision_document": "",
        "note": note or "",
    }
    if any(o["id"] == offer["id"] for o in data["offers"]):
        raise cd.RuleError("offer %s is already in the ladder" % offer["id"])
    data["offers"].append(offer)
    data["offers"].sort(key=lambda o: (o["made"], o["id"]))
    save(matter_dir, data)
    return offer


def decide(matter_dir, offer_id, decision, on=None, document="", by=""):
    decision = (decision or "").strip().lower()
    if decision not in DECISIONS:
        raise cd.RuleError("a decision is one of: %s. Lapse is not entered: it follows from the date." % ", ".join(DECISIONS))
    data = load(matter_dir)
    for o in data["offers"]:
        if o["id"] == offer_id:
            o["status"] = decision
            o["decided_on"] = cd.parse_date(on).isoformat() if on else _dt.date.today().isoformat()
            o["decision_document"] = _matter.relative(matter_dir, document) if document else ""
            if by:
                o["answered_by"] = by
            save(matter_dir, data)
            return o
    raise cd.RuleError("no offer %s; `chirograph offer list` shows the ladder" % offer_id)


# --------------------------------------------------------------------------- clocks

class Clock(object):
    def __init__(self, date, time, line, notes, source, both=None):
        self.date = date
        self.time = time
        self.line = line
        self.notes = notes
        self.source = source          # 'stated' or 'statute'
        self.both = both

    def passed(self, today, now=None, court_tz=None):
        """True when the clock has run out. A stated time of day counts when `now` is given."""
        if today > self.date:
            return True
        if today == self.date and self.time and now is not None and court_tz:
            return now >= _tz.moment(self.date, self.time, court_tz)
        return False


def clock(offer, matter, rule_dir=None):
    """The lapse clock of one offer, or None when the offer states no expiry and no rule supplies one."""
    court_tz = matter.get("court_tz") or "America/Los_Angeles"
    reader_tz = matter.get("reader_tz") or ""
    made = cd.parse_date(offer["made"])
    notes = []
    statutory = None
    if offer["kind"] == "998":
        statutory = _statutory_clock(offer, matter, rule_dir)
    if offer.get("expires"):
        d = cd.parse_date(offer["expires"])
        t = offer.get("expires_time") or ""
        src = offer.get("document") or "the offer"
        line = "Lapses %s%s — expiry stated in the offer (%s)." % (cd.fmt_full(d), (" at %s court time" % t) if t else "", src)
        if statutory is not None and statutory.date != d:
            notes.append("The statute's clock computes a different day: %s" % statutory.line)
        return Clock(d, t, line, notes, "stated", _tz.both(d, t, court_tz, reader_tz))
    if statutory is not None:
        statutory.both = _tz.both(statutory.date, statutory.time, court_tz, reader_tz)
        return statutory
    return None


def _statutory_clock(offer, matter, rule_dir=None):
    r = _rules.rule("ca.998_lapse", rule_dir)
    court = _rules.court(rule_dir)
    made = cd.parse_date(offer["made"])
    res = cd.after(made, r["days"], r["cite"], court, unit=r.get("unit", "calendar"), roll_cite=None,
                   prefix="Lapses", trigger_phrase="made", rule_id=r["id"])
    d, frags, notes = res.date, list(res.steps), list(res.notes)
    ry = d.year if made.year == d.year else None

    # an optional extension for the way the offer was served, applied only on instruction
    mkey = offer.get("method") or ""
    if mkey and mkey != "personal":
        _k, mrow = _rules.method(mkey, rule_dir)
        ext = _rules.rule("ca.998_service_extension", rule_dir)
        if int(mrow.get("add", 0)):
            if offer.get("extend_for_service"):
                if mrow.get("unit") == "court":
                    d2, sk = court.add_court_days(d, int(mrow["add"]))
                    frags.append("+ %d court days %s (%s)%s = %s" % (
                        mrow["add"], mrow["short"], mrow["cite"], cd.skips_text(sk, ry), cd.fmt(d2, ry)))
                else:
                    d2 = d + _dt.timedelta(days=int(mrow["add"]))
                    frags.append("+ %d days %s (%s) = %s" % (mrow["add"], mrow["short"], mrow["cite"], cd.fmt(d2, ry)))
                d = d2
                notes = [n for n in notes if "does not roll" not in n]
                if not court.is_court_day(d):
                    rolled, _sk = court.roll(d)
                    why = court.why_closed(d)
                    notes.append("%s is %s; this date does not roll. The next court day is %s." % (
                        cd.fmt_full(d), why if why.startswith("a ") else why + ", a court holiday", cd.fmt_full(rolled)))
                notes.append("The service extension is applied because the offer was entered with --extend. "
                             "Authority named in the rule table: %s (%s)." % (
                                 ext.get("authority", ext["cite"]), "read" if _rules.is_read(ext) else "from memory, not read"))
            else:
                notes.append("Served by %s. This date does not add the %d %s in %s; whether that extension reaches "
                             "the 30 days is a case-law question the rule table leaves open (%s). "
                             "`--extend` applies it." % (mrow["label"], mrow["add"],
                                                         "court days" if mrow.get("unit") == "court" else "days",
                                                         mrow["cite"], "read" if _rules.is_read(ext) else "from memory, not read"))

    # trial or arbitration comes first when it is sooner
    trial = matter.get("trial_date") or ""
    if trial:
        td = cd.parse_date(trial)
        win = _rules.rule("ca.998_service_window", rule_dir)
        last_service = td - _dt.timedelta(days=int(win["days"]))
        if made > last_service:
            notes.append("Made %s, fewer than %d days before trial %s (%s asks for not less than %d days)." % (
                cd.fmt_full(made), win["days"], cd.fmt_full(td), win["cite"], win["days"]))
        if td <= d:
            frags.append("trial starts %s, which comes first (%s)" % (cd.fmt(td, ry), r["cite"]))
            d = td
            notes = [n for n in notes if "does not roll" not in n]
            notes.append("The offer is deemed withdrawn if not accepted before trial starts.")
    line = "Lapses %s — %s." % (cd.fmt_full(d), "; ".join(frags))
    return Clock(d, "", line, notes, "statute")


# --------------------------------------------------------------------------- evaluation

class View(object):
    """One offer as it stands on a given day."""

    def __init__(self, offer, status, flags, clock_, running=False):
        self.offer = offer
        self.status = status
        self.flags = flags
        self.clock = clock_
        # the clock still counts: an open offer, or a statutory offer answered with a counter or a
        # rejection whose date has not passed (the rule table does not treat either as ending it)
        self.running = running

    @property
    def id(self):
        return self.offer["id"]

    def as_dict(self, currency="$"):
        o = dict(self.offer)
        o.update({"status_now": self.status, "flags": self.flags, "running": self.running,
                  "amount_text": money(o.get("amount"), currency),
                  "kind_text": KINDS.get(o["kind"], o["kind"]),
                  "clock": None if not self.clock else {
                      "date": self.clock.date.isoformat(), "time": self.clock.time, "line": self.clock.line,
                      "notes": self.clock.notes, "both": self.clock.both, "source": self.clock.source}})
        return o


def evaluate(matter_dir, today=None, now=None, rule_dir=None):
    m = _matter.load(matter_dir)
    court_tz = m.get("court_tz") or "America/Los_Angeles"
    today = cd.parse_date(today) if today else _tz.today(court_tz)
    out = []
    for o in load(matter_dir)["offers"]:
        flags = []
        c = clock(o, m, rule_dir)
        sourced = _matter.on_disk(matter_dir, o.get("document"))
        if not o.get("document"):
            flags.append("no document named for this offer")
        elif not sourced:
            flags.append("document not on this disk: %s" % o["document"])
        st = (o.get("status") or "open").lower()
        if st in DECISIONS:
            status = st.upper()
            if not o.get("decision_document"):
                flags.append("no document named for the %s decision" % st)
            elif not _matter.on_disk(matter_dir, o["decision_document"]):
                flags.append("decision document not on this disk: %s" % o["decision_document"])
        elif c is not None and c.passed(today, now, court_tz):
            status = "LAPSED"
        elif sourced:
            status = "OPEN"
        else:
            status = "UNSOURCED"
        if o.get("amount") is None:
            flags.append("no amount entered")
        passed = c is not None and c.passed(today, now, court_tz)
        running = c is not None and not passed and (
            status in ("OPEN", "UNSOURCED") or (o["kind"] == "998" and status in ("REJECTED", "COUNTERED")))
        out.append(View(o, status, flags, c, running))
    return m, today, out


def positions(views):
    """Each side's last offer with an amount, the gap between them and the midpoint."""
    last = {}
    for v in views:
        side = v.offer.get("side")
        if side in ("plaintiff", "defendant") and v.offer.get("amount") is not None:
            last[side] = v
    out = {"plaintiff": last.get("plaintiff"), "defendant": last.get("defendant"), "gap": None, "midpoint": None,
           "accepted": None}
    if last.get("plaintiff") and last.get("defendant"):
        a, b = float(last["plaintiff"].offer["amount"]), float(last["defendant"].offer["amount"])
        out["gap"] = abs(a - b)
        out["midpoint"] = (a + b) / 2.0
    for v in views:
        if v.status == "ACCEPTED":
            out["accepted"] = v
    return out


def render(matter_dir, today=None, now=None, rule_dir=None):
    m, today, views = evaluate(matter_dir, today, now, rule_dir)
    cur = m.get("currency") or "$"
    lines = ["OFFERS — %s (court date %s)" % (m.get("name", ""), cd.fmt_full(today)), ""]
    if not views:
        lines.append("No offer entered. `chirograph offer add` enters one.")
        return "\n".join(lines), views
    for v in views:
        o = v.offer
        made = cd.parse_date(o["made"])
        head = "%-4s %s   %s → %s   %s   %s   %s" % (
            o["id"], cd.fmt_full(made), o["from"], o["to"], KINDS[o["kind"]], money(o.get("amount"), cur), v.status)
        if o.get("decided_on") and v.status in [d.upper() for d in DECISIONS]:
            head += " %s" % cd.fmt_full(cd.parse_date(o["decided_on"]))
        lines.append(head)
        if o.get("answers"):
            lines.append("     Answers %s." % o["answers"])
        if o.get("terms"):
            lines.append("     Terms: %s" % o["terms"])
        if o.get("document"):
            lines.append("     Document: %s" % o["document"])
        if v.status == "LAPSED" and v.clock:
            lines.append("     " + v.clock.line.replace("Lapses", "Lapsed", 1))
        for f in v.flags:
            lines.append("     FLAG: %s" % f)
        lines.append("")
    pos = positions(views)
    lines.append("Positions")
    for side in ("plaintiff", "defendant"):
        v = pos[side]
        if v:
            lines.append("  %s (%s): %s — %s, %s (%s)" % (
                side.capitalize(), v.offer["from"], money(v.offer["amount"], cur), v.id,
                cd.fmt_full(cd.parse_date(v.offer["made"])), v.status))
        else:
            lines.append("  %s: no offer with an amount" % side.capitalize())
    if pos["gap"] is not None:
        lines.append("  Gap %s · midpoint %s" % (money(pos["gap"], cur), money(pos["midpoint"], cur)))
    for v in views:
        if v.offer.get("side") == "neutral" and v.offer.get("amount") is not None:
            lines.append("  Neutral (%s): %s — %s, %s (%s)" % (
                v.offer["from"], money(v.offer["amount"], cur), v.id, cd.fmt_full(cd.parse_date(v.offer["made"])), v.status))
    if pos["accepted"]:
        a = pos["accepted"]
        lines.append("  Accepted: %s — %s%s" % (money(a.offer.get("amount"), cur), a.id,
                                                 (", " + cd.fmt_full(cd.parse_date(a.offer["decided_on"]))) if a.offer.get("decided_on") else ""))
    lines.append("")
    running = [v for v in views if v.running]
    lines.append("Clocks running")
    if not running:
        lines.append("  None.")
    for v in running:
        lines.append("  %s: %s" % (v.id, v.clock.line))
        if v.clock.both:
            lines.append("      %s" % v.clock.both)
        for n in v.clock.notes:
            lines.append("      Note: %s" % n)
        if v.status in ("REJECTED", "COUNTERED"):
            lines.append("      Note: Marked %s. The clock is still shown: the rule table does not treat a counter or a "
                         "rejection as ending a statutory offer." % v.status)
    no_clock = [v for v in views if v.status in ("OPEN", "UNSOURCED") and not v.clock]
    for v in no_clock:
        lines.append("  %s: no expiry stated and no rule supplies one." % v.id)
    return "\n".join(lines), views
