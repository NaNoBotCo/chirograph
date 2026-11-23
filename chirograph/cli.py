"""chirograph — the command line.

    chirograph new-matter <dir> --plaintiff ... --defendant ... --case-no ... --county ...
    chirograph offer add | list | decide
    chirograph terms check <agreement.pdf|txt>
    chirograph closing build | list | done
    chirograph statement new | build
    chirograph brief
    chirograph ics
    chirograph rules
    chirograph desk
"""
import argparse
import json
import os
import sys

from . import __version__
from . import brief as _brief
from . import closing as _closing
from . import courtdays as cd
from . import ics as _ics
from . import matter as _matter
from . import offers as _offers
from . import rules as _rules
from . import statement as _statement
from . import terms as _terms


def _matter_dir(args):
    return _matter.require(getattr(args, "matter", None))


# --------------------------------------------------------------------------- commands

def cmd_new_matter(a):
    dest = _matter.scaffold(a.dir, a.plaintiff or "", a.defendant or "", a.case_no or "", a.county or "",
                            a.court or "", a.reader_tz, a.court_tz, a.name, a.trial_date or "", a.currency)
    print("Matter folder: %s" % dest)
    print("Next: `chirograph offer add` enters the first offer.")
    return 0


def cmd_offer_add(a):
    m = _matter_dir(a)
    o = _offers.add(m, a.made, a.sender, a.to, a.kind, a.amount, a.terms or "", a.method, a.document or "",
                    a.expires, a.expires_time, a.answers, a.extend, a.side, a.id, a.note or "")
    mm = _matter.load(m)
    print("%s entered: %s → %s, %s, %s." % (o["id"], o["from"], o["to"], _offers.KINDS[o["kind"]],
                                         _offers.money(o["amount"], mm.get("currency") or "$")))
    if not o["document"]:
        print("FLAG: no document named. The offer shows UNSOURCED until --document names a file on disk.")
    elif not _matter.on_disk(m, o["document"]):
        print("FLAG: document not on this disk: %s. The offer shows UNSOURCED." % o["document"])
    c = _offers.clock(o, mm)
    if c:
        print(c.line)
        if c.both:
            print(c.both)
        for n in c.notes:
            print("Note: %s" % n)
    return 0


def cmd_offer_list(a):
    m = _matter_dir(a)
    if a.json:
        mm, today, views = _offers.evaluate(m, a.today)
        print(json.dumps({"today": today.isoformat(),
                          "offers": [v.as_dict(mm.get("currency") or "$") for v in views]}, indent=2, ensure_ascii=False))
        return 0
    text, _views = _offers.render(m, a.today)
    print(text)
    return 0


def cmd_offer_decide(a):
    m = _matter_dir(a)
    o = _offers.decide(m, a.id, a.decision, a.on, a.document or "", a.by or "")
    print("%s is %s as of %s." % (o["id"], o["status"].upper(), o["decided_on"]))
    if not o.get("decision_document"):
        print("FLAG: no document named for the decision (--document).")
    elif not _matter.on_disk(m, o["decision_document"]):
        print("FLAG: decision document not on this disk: %s" % o["decision_document"])
    return 0


def cmd_terms_check(a):
    path = a.file
    if not os.path.isfile(path):
        m = _matter.find(getattr(a, "matter", None))
        alt = _matter.resolve(m, path) if m else None
        if alt and os.path.isfile(alt):
            path = alt
        else:
            print("not on this disk: %s" % a.file)
            return 2
    expect = []
    for e in a.expect_none or []:
        expect.extend(x for x in e.split(",") if x.strip())
    result, code = _terms.check(path, release_only=a.release_only, expect_none=expect, strict=a.strict, by=a.by)
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_terms.render(result))
    return code


def _spec(days, date, cite, unit=None):
    if days is None and not date and not cite:
        return None
    s = {}
    if days is not None:
        s["days"] = int(days)
    if date:
        s["date"] = cd.parse_date(date).isoformat()
    if cite:
        s["cite"] = cite
    if unit:
        s["unit"] = unit
    return s


def cmd_closing_build(a):
    m = _matter_dir(a)
    upd = {}
    if a.facts:
        with open(a.facts, encoding="utf-8") as fh:
            upd.update(json.load(fh))
    if a.signed:
        upd["signed"] = cd.parse_date(a.signed).isoformat()
    if a.agreement:
        upd["agreement"] = _matter.relative(m, a.agreement)
    if a.conditional:
        upd["conditional"] = True
    if a.dismissal_date:
        upd["dismissal_date"] = cd.parse_date(a.dismissal_date).isoformat()
    pay = _spec(a.payment_days, a.payment_date, a.payment_cite, a.payment_unit) or {}
    if a.payment_amount is not None:
        pay["amount"] = _offers.parse_amount(a.payment_amount)
    if a.payor:
        pay["payor"] = a.payor
    if a.payment_method:
        pay["method"] = a.payment_method
    if pay:
        upd["payment"] = pay
    wire = _spec(a.wire_days, a.wire_date, a.wire_cite)
    if wire:
        upd["wire"] = wire
    tax = _spec(a.tax_days, a.tax_date, a.tax_cite) or {}
    if a.tax_form:
        tax["title"] = a.tax_form
    if tax:
        upd["tax_form"] = tax
    if a.instrument:
        ins = {"title": a.instrument, "signer_abroad": bool(a.signer_abroad), "cite": a.instrument_cite or ""}
        sign = _spec(a.instrument_sign_days, a.instrument_sign_date, a.instrument_cite)
        disp = _spec(a.instrument_dispatch_days, a.instrument_dispatch_date, a.instrument_cite)
        outside = _spec(a.instrument_outside_days, a.instrument_outside_date, a.instrument_cite)
        if sign:
            ins["sign"] = sign
        if disp:
            ins["dispatch"] = disp
        if outside:
            ins["outside"] = outside
        upd["instruments"] = [ins]
    lp = _spec(a.lis_pendens_days, a.lis_pendens_date, a.lis_pendens_cite)
    if lp:
        upd["lis_pendens"] = lp
    if a.retain:
        upd["retain_jurisdiction"] = True
    if a.hearing:
        hs = []
        for h in a.hearing:
            parts = h.split(None, 2)
            if len(parts) < 2:
                raise cd.RuleError('a hearing is written "YYYY-MM-DD HH:MM Title"; got %r' % h)
            date = cd.parse_date(parts[0]).isoformat()
            if ":" in parts[1]:
                cd.parse_time(parts[1])
                time, title = parts[1], (parts[2] if len(parts) > 2 else "Hearing")
            else:
                time, title = "", " ".join(parts[1:])
            hs.append({"date": date, "time": time, "title": title, "kind": "hearing", "order": ""})
        orders = a.hearing_order or []
        kinds = a.hearing_kind or []
        for i, h in enumerate(hs):
            if i < len(orders):
                h["order"] = _matter.relative(m, orders[i])
            if i < len(kinds):
                h["kind"] = kinds[i]
        upd["hearings"] = hs
    data = _closing.build(m, upd)
    print("Closing list built: %d task%s." % (len(data["tasks"]), "" if len(data["tasks"]) == 1 else "s"))
    text, _rows = _closing.render(m, a.today)
    print(text)
    return 0


def cmd_closing_list(a):
    m = _matter_dir(a)
    if a.json:
        mm, rws = _closing.rows(m)
        print(json.dumps({"facts": _closing.load(m)["facts"], "tasks": [r.as_dict() for r in rws]}, indent=2, ensure_ascii=False))
        return 0
    text, _rows = _closing.render(m, a.today)
    print(text)
    return 0


def cmd_closing_done(a):
    m = _matter_dir(a)
    ok, msg = _closing.advance(m, a.task, a.evidence, a.state, a.on)
    print(msg)
    return 0 if ok else 1


def cmd_statement_new(a):
    m = _matter_dir(a)
    print("Wrote %s. Fill it in, then `chirograph statement build`." % _statement.new(m))
    return 0


def cmd_statement_build(a):
    m = _matter_dir(a)
    code, msgs, _files = _statement.build(m, a.out, a.file, a.today)
    for line in msgs:
        print(line)
    return code


def cmd_brief(a):
    print(_brief.brief(_matter_dir(a), a.today), end="")
    return 0


def cmd_ics(a):
    m = _matter_dir(a)
    text, n = _ics.to_ics(m, a.today)
    out = a.output or os.path.join(m, "out", "settlement.ics")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print("Wrote %s (%d event%s)" % (out, n, "" if n == 1 else "s"))
    return 0


def cmd_rules(a):
    print(_rules.describe())
    return 0


def cmd_desk(a):
    from . import desk as _desk
    return _desk.serve(a.port, getattr(a, "matter", None), not a.no_open, a.today)


# --------------------------------------------------------------------------- parser

def build_parser():
    P = argparse.ArgumentParser(prog="chirograph", description="The settlement track: offers, terms, closing list, mediation statement.")
    P.add_argument("--version", action="version", version="chirograph " + __version__)
    S = P.add_subparsers(dest="cmd", metavar="<command>")

    p = S.add_parser("new-matter", help="scaffold a matter folder")
    p.add_argument("dir")
    p.add_argument("--plaintiff")
    p.add_argument("--defendant")
    p.add_argument("--case-no")
    p.add_argument("--county")
    p.add_argument("--court", help="the court's name, when not a California superior court")
    p.add_argument("--court-tz", default="America/Los_Angeles")
    p.add_argument("--reader-tz", help="the reader's time zone, like Europe/London")
    p.add_argument("--trial-date")
    p.add_argument("--currency", default="$")
    p.add_argument("--name")
    p.set_defaults(fn=cmd_new_matter)

    p = S.add_parser("offer", help="the ladder of offers")
    O = p.add_subparsers(dest="ocmd", metavar="<add|list|decide>")
    q = O.add_parser("add", help="enter an offer")
    q.add_argument("matter", nargs="?")
    q.add_argument("--made", required=True, help="the date the offer was made, YYYY-MM-DD")
    q.add_argument("--from", dest="sender", required=True)
    q.add_argument("--to", required=True)
    q.add_argument("--kind", default="letter", help="letter, 998, counter or mediator")
    q.add_argument("--amount")
    q.add_argument("--terms", help="the terms in one line")
    q.add_argument("--method", help="how it was served: email, mail, personal, overnight ...")
    q.add_argument("--document", help="the file that made the offer")
    q.add_argument("--expires", help="expiry stated in the offer, YYYY-MM-DD")
    q.add_argument("--expires-time", help="HH:MM court time")
    q.add_argument("--answers", help="the id of the offer this one answers")
    q.add_argument("--extend", action="store_true", help="add the service-method extension to a statutory offer's 30 days")
    q.add_argument("--side", help="plaintiff, defendant or neutral, when the sender's name is not a party's")
    q.add_argument("--id")
    q.add_argument("--note")
    q.set_defaults(fn=cmd_offer_add)
    q = O.add_parser("list", help="the ladder, the positions and the clocks")
    q.add_argument("matter", nargs="?")
    q.add_argument("--today")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=cmd_offer_list)
    q = O.add_parser("decide", help="mark an offer rejected, countered, accepted or withdrawn")
    q.add_argument("id")
    q.add_argument("decision")
    q.add_argument("matter", nargs="?")
    q.add_argument("--on")
    q.add_argument("--document", help="the file that shows the decision")
    q.add_argument("--by", help="the id of the counter that answered it")
    q.set_defaults(fn=cmd_offer_decide)

    p = S.add_parser("terms", help="read an agreement against the term list")
    T = p.add_subparsers(dest="tcmd", metavar="<check>")
    q = T.add_parser("check", help="FOUND with page:line, or not found in this text")
    q.add_argument("file")
    q.add_argument("--matter")
    q.add_argument("--release-only", metavar="NAME", help="exit 1 if the release names any other person or entity")
    q.add_argument("--by", metavar="NAME", help="with --release-only: read the clauses this party gives")
    q.add_argument("--strict", action="store_true", help="with --release-only: classes (heirs, insurers ...) also exit 1")
    q.add_argument("--expect-none", action="append", metavar="TERM[,TERM]", help="exit 1 if a term is FOUND")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=cmd_terms_check)

    p = S.add_parser("closing", help="the closing list after signing")
    C = p.add_subparsers(dest="ccmd", metavar="<build|list|done>")
    q = C.add_parser("build", help="build or rebuild the list from the closing facts")
    q.add_argument("matter", nargs="?")
    q.add_argument("--facts", help="a JSON file of closing facts")
    q.add_argument("--signed", help="the date the settlement was signed")
    q.add_argument("--agreement", help="the signed agreement file")
    q.add_argument("--conditional", action="store_true", help="a conditional settlement (terms run past 45 days)")
    q.add_argument("--dismissal-date", help="the dismissal date named in a notice of conditional settlement")
    q.add_argument("--payment-amount")
    q.add_argument("--payment-days", type=int)
    q.add_argument("--payment-date")
    q.add_argument("--payment-unit", choices=["calendar", "court"])
    q.add_argument("--payment-cite", help='where the agreement says it, like "Agreement §1"')
    q.add_argument("--payment-method")
    q.add_argument("--payor")
    q.add_argument("--wire-days", type=int)
    q.add_argument("--wire-date")
    q.add_argument("--wire-cite")
    q.add_argument("--tax-form", help='the form the agreement names, like "IRS Form W-9"')
    q.add_argument("--tax-days", type=int)
    q.add_argument("--tax-date")
    q.add_argument("--tax-cite")
    q.add_argument("--instrument", help='a deed or other instrument to sign, like "Quitclaim deed"')
    q.add_argument("--signer-abroad", action="store_true")
    q.add_argument("--instrument-cite")
    q.add_argument("--instrument-sign-days", type=int)
    q.add_argument("--instrument-sign-date")
    q.add_argument("--instrument-dispatch-days", type=int)
    q.add_argument("--instrument-dispatch-date")
    q.add_argument("--instrument-outside-days", type=int)
    q.add_argument("--instrument-outside-date")
    q.add_argument("--lis-pendens-days", type=int)
    q.add_argument("--lis-pendens-date")
    q.add_argument("--lis-pendens-cite")
    q.add_argument("--retain", action="store_true", help="the court is to retain jurisdiction (CCP §664.6)")
    q.add_argument("--hearing", action="append", metavar='"YYYY-MM-DD HH:MM Title"', help="a hearing still on calendar")
    q.add_argument("--hearing-order", action="append", metavar="FILE", help="the order or notice that set it, in the same order")
    q.add_argument("--hearing-kind", action="append", metavar="KIND", help="hearing or adr, in the same order")
    q.add_argument("--today")
    q.set_defaults(fn=cmd_closing_build)
    q = C.add_parser("list", help="each task, its date, its arithmetic and its state")
    q.add_argument("matter", nargs="?")
    q.add_argument("--today")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=cmd_closing_list)
    q = C.add_parser("done", help="enter a state on a task, with evidence")
    q.add_argument("task")
    q.add_argument("matter", nargs="?")
    q.add_argument("--state", help="BUILT, SIGNED, SERVED, FILED, DONE, or OFF for a hearing; default is the next one")
    q.add_argument("--evidence", help="a file on disk that shows it")
    q.add_argument("--on", help="the date it happened")
    q.set_defaults(fn=cmd_closing_done)

    p = S.add_parser("statement", help="the mediation statement")
    M = p.add_subparsers(dest="scmd", metavar="<new|build>")
    q = M.add_parser("new", help="write a blank statement.json")
    q.add_argument("matter", nargs="?")
    q.set_defaults(fn=cmd_statement_new)
    q = M.add_parser("build", help="statement.json to text and PDF, checked against muzzles.txt")
    q.add_argument("matter", nargs="?")
    q.add_argument("--file", help="a statement file other than statement.json")
    q.add_argument("--out", help="output folder (default: the matter's out/)")
    q.add_argument("--today")
    q.set_defaults(fn=cmd_statement_build)

    p = S.add_parser("brief", help="today, the next 7 days, clocks, tasks with no evidence, open offers")
    p.add_argument("matter", nargs="?")
    p.add_argument("--today")
    p.set_defaults(fn=cmd_brief)

    p = S.add_parser("ics", help="calendar file with the arithmetic in each event")
    p.add_argument("matter", nargs="?")
    p.add_argument("-o", "--output")
    p.add_argument("--today")
    p.set_defaults(fn=cmd_ics)

    p = S.add_parser("rules", help="the rule table with each rule's verify status")
    p.set_defaults(fn=cmd_rules)

    p = S.add_parser("desk", help="large-type local window")
    p.add_argument("--matter")
    p.add_argument("--port", type=int, default=8775)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--today", help="show the matter as of this court date")
    p.set_defaults(fn=cmd_desk)
    return P


def main(argv=None):
    P = build_parser()
    a = P.parse_args(argv)
    if not getattr(a, "fn", None):
        P.print_help()
        return 2
    try:
        return a.fn(a) or 0
    except cd.RuleError as exc:
        print("chirograph: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
