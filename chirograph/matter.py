"""A matter folder: find it, read it, scaffold a new one.

    chirograph new-matter <dir> --plaintiff "Jane Doe" --defendant "Roe Holdings, LLC"
                          --case-no 26CV000000 --county Alameda --reader-tz Europe/London

Layout follows Cursitor's matter folder, so one folder can serve both tools.
"""
import datetime as _dt
import json
import os

FOLDERS = ("offers", "agreements", "evidence", "received", "out")


def find(start=None):
    """The matter folder: `start` if it has matter.json, else the nearest parent that does."""
    d = os.path.abspath(start or os.getcwd())
    if os.path.isfile(d):
        d = os.path.dirname(d)
    while True:
        if os.path.exists(os.path.join(d, "matter.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def require(start=None):
    m = find(start)
    if not m:
        raise SystemExit("no matter.json in %s or any folder above it; `chirograph new-matter` makes one"
                         % os.path.abspath(start or os.getcwd()))
    return m


def load(matter_dir):
    with open(os.path.join(matter_dir, "matter.json"), encoding="utf-8") as fh:
        return json.load(fh)


def read_json(matter_dir, name, default):
    p = os.path.join(matter_dir, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(matter_dir, name, data):
    p = os.path.join(matter_dir, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return p


def resolve(matter_dir, rel):
    """A path named in a matter file: absolute as given, otherwise inside the matter folder."""
    if not rel:
        return None
    rel = os.path.expanduser(rel)
    return rel if os.path.isabs(rel) else os.path.join(matter_dir, rel)


def on_disk(matter_dir, rel):
    p = resolve(matter_dir, rel)
    return bool(p) and os.path.isfile(p)


def relative(matter_dir, path):
    """How a path is stored in a matter file: relative to the matter folder when it sits inside it.

    A relative path is read as relative to the matter folder first, then to the working folder.
    """
    if not path:
        return path
    path = os.path.expanduser(path)
    root = os.path.abspath(matter_dir)
    if not os.path.isabs(path):
        if os.path.exists(os.path.join(root, path)) or not os.path.exists(path):
            return os.path.normpath(path)
    ap = os.path.abspath(path)
    if ap == root or ap.startswith(root + os.sep):
        return os.path.relpath(ap, root)
    return ap


def side_of(matter, name):
    """'plaintiff', 'defendant' or None for a party name, matched without regard to case or punctuation."""
    def norm(s):
        return "".join(c for c in (s or "").casefold() if c.isalnum())
    n = norm(name)
    if not n:
        return None
    for side, names in (matter.get("parties") or {}).items():
        for full in names:
            f = norm(full)
            if n == f or (len(n) >= 4 and (n in f or f in n)):
                return side
    return None


def done_line(matter_dir, text, on=None):
    """Append a dated line to DONE.md, the ledger."""
    p = os.path.join(matter_dir, "DONE.md")
    stamp = (on or _dt.date.today()).isoformat()
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (stamp, text))


CLAUDE_MD = """# Matter rules for Claude — {name}

Boot order for a session on the settlement track:
1. STATUS.md — the narrative. Append-only. The last dated block wins.
2. DONE.md — the ledger. A dated line means done. A line without a date, or an unclear one, means not done.
3. offers.json — the ladder. `chirograph offer list` prints it with each running clock.
4. closing.json — the closing list. `chirograph closing list` prints each task, its date and its state.

Working rules for this matter:
- An offer is OPEN only when the document that made it is on disk and named in the offer. Otherwise it shows UNSOURCED.
- A date goes out with its arithmetic, in one line. `chirograph offer list` and `chirograph closing list` write the lines.
- A closing task moves from one state to the next (BUILT, SIGNED, SERVED, FILED, DONE) only with a file on disk that shows it: a receipt, a sent message saved as .txt, a conformed copy. Without the file the task stays in its state.
- A hearing stays ON CALENDAR until an order or the court's own page, saved to disk, shows it is off.
- When a term or a document is not in the text that was read, say "not found in this text" or "not on this disk".
- muzzles.txt lists words and topics that stay out of a mediation statement. `chirograph statement build` checks the statement against it.
- Decisions about offers belong to the person: the amount, the terms, whether to accept. Print the ladder and the clocks; do not choose.
"""

STATUS_MD = """# STATUS — {name}

Append a dated block for each working session. The last block wins.

## {today}

Matter folder created. No offer entered yet.
"""

DONE_MD = """# DONE — {name}

One line per finished item, starting with its date (YYYY-MM-DD). No date means not done.

{today} Matter folder created.
"""

MUZZLES = """# One entry per line: a word, a phrase or a regular expression (case does not count).
# `chirograph statement build` exits 1 when the statement contains any of them.
# Lines starting with # are notes. The entries below are examples; replace them with the matter's own.
"""


def scaffold(dest, plaintiff="", defendant="", case_no="", county="", court="", reader_tz=None,
             court_tz="America/Los_Angeles", name=None, trial_date="", currency="$"):
    dest = os.path.abspath(dest)
    if os.path.exists(os.path.join(dest, "matter.json")):
        raise SystemExit("a matter is already at %s" % dest)
    os.makedirs(dest, exist_ok=True)
    for f in FOLDERS:
        os.makedirs(os.path.join(dest, f), exist_ok=True)
    today = _dt.date.today().isoformat()
    name = name or ("%s v. %s" % (plaintiff.split(",")[0] or "Plaintiff", defendant.split(",")[0] or "Defendant"))
    court = court or ("Superior Court of California, County of %s" % county if county else "")
    matter = {
        "name": name,
        "jurisdiction": "ca",
        "court": court,
        "court_tz": court_tz,
        "reader_tz": reader_tz or "",
        "case_number": case_no,
        "trial_date": trial_date or "",
        "currency": currency,
        "parties": {"plaintiff": [plaintiff] if plaintiff else [], "defendant": [defendant] if defendant else []},
        "identifiers": [x for x in (case_no, plaintiff, defendant.split(",")[0]) if x],
    }
    files = {
        "matter.json": json.dumps(matter, indent=2, ensure_ascii=False) + "\n",
        "offers.json": json.dumps({"matter": name, "offers": []}, indent=2) + "\n",
        "closing.json": json.dumps({"matter": name, "facts": {}, "tasks": []}, indent=2) + "\n",
        "STATUS.md": STATUS_MD.format(name=name, today=today),
        "DONE.md": DONE_MD.format(name=name, today=today),
        "muzzles.txt": MUZZLES,
        "CLAUDE.md": CLAUDE_MD.format(name=name),
    }
    for rel, body in files.items():
        with open(os.path.join(dest, rel), "w", encoding="utf-8") as fh:
            fh.write(body)
    return dest
