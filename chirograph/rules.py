"""The rule tables: rules/ca_settlement.json (periods and citations) and rules/terms.json (agreement terms)."""
import json
import os

from . import courtdays as cd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULE_DIR = os.path.join(ROOT, "rules")

_CACHE = {}


def _load(name, rule_dir=None):
    path = os.path.join(rule_dir or RULE_DIR, name)
    if path in _CACHE:
        return _CACHE[path]
    if not os.path.exists(path):
        raise cd.RuleError("no rule table at %s" % path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _CACHE[path] = data
    return data


def settlement(rule_dir=None):
    t = _load("ca_settlement.json", rule_dir)
    if "_by_id" not in t:
        t["_by_id"] = {r["id"]: r for r in t["rules"]}
    return t


def terms(rule_dir=None):
    return _load("terms.json", rule_dir)


def rule(rule_id, rule_dir=None):
    t = settlement(rule_dir)
    r = t["_by_id"].get(rule_id)
    if not r:
        raise cd.RuleError("unknown rule %r; `chirograph rules` lists the table" % rule_id)
    return r


def court(rule_dir=None):
    return cd.Court(settlement(rule_dir).get("holidays", "ca"))


def method(name, rule_dir=None):
    """(key, row) for a service method, through the alias list. None -> personal delivery."""
    t = settlement(rule_dir)
    m = (name or "personal").strip().lower().replace(" ", "-")
    m = t.get("aliases", {}).get(m, m).replace("-", "_")
    if m not in t["methods"]:
        raise cd.RuleError("unknown service method %r; choose from: %s" % (name, ", ".join(sorted(t["methods"]))))
    return m, t["methods"][m]


def is_read(row):
    return str(row.get("verify", "")).startswith("read ")


def describe(rule_dir=None):
    """The table as text: one block per rule with its period, citation and verify status."""
    t = settlement(rule_dir)
    out = [t["name"], ""]
    for r in t["rules"]:
        unit = "court days" if r.get("unit") == "court" else "days"
        if r["direction"] == "none" or not r.get("days"):
            period = "no period" if r["direction"] == "none" else "at once"
        else:
            period = "%d %s %s %s" % (r["days"], unit, r["direction"], r["trigger"])
        out.append("%s — %s" % (r["id"], r["label"]))
        out.append("  %s · %s%s" % (r["cite"], period, " · optional" if r.get("optional") else ""))
        if r.get("authority"):
            out.append("  authority named: %s" % r["authority"])
        out.append("  verify: %s" % r["verify"])
        out.append("")
    out.append("Service methods")
    for key in sorted(t["methods"]):
        m = t["methods"][key]
        unit = "court days" if m.get("unit") == "court" else "days"
        out.append("  %-26s + %d %s (%s) · verify: %s" % (key, m["add"], unit, m["cite"], m["verify"]))
    c = t["counting"]
    out.append("")
    out.append("Counting: %s · verify: %s" % (c["roll_cite"], c["verify"]))
    out.append("  %s" % c["note"])
    return "\n".join(out)
