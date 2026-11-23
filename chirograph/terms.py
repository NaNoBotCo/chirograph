"""Read a draft or signed agreement against the term list in rules/terms.json.

    chirograph terms check agreement.pdf [--release-only "Roe Holdings, LLC"] [--expect-none confidentiality]

For each term the result is FOUND, with the passage quoted and cited page:line, or "not found in
this text". The second wording is exact: the text on disk is what was read, and an agreement can
say a thing in words the patterns do not match.

The release passage gets a closer read: who is released, who releases, and which classes of
people (heirs, insurers, agents) ride along. `--release-only NAME` exits 1 and names any other
released person or entity.
"""
import os
import re

from . import pdftext as _pdf
from . import rules as _rules

NOT_FOUND = "not found in this text"
ENTITY = r"(?:LLC|L\.L\.C\.|Inc\.?|Incorporated|Corp\.?|Corporation|LLP|L\.L\.P\.|LP|L\.P\.|Ltd\.?|Co\.|Company|Trust|Bank|N\.A\.|PLC|P\.C\.|APC|Foundation|Association|Partners)"
ABBREV = r"(?:Mr|Mrs|Ms|Dr|Jr|Sr|St|Inc|Corp|Ltd|Co|No|L\.P|L\.L\.C|L\.L\.P|N\.A|P\.C)"
TOKEN = r"(?:" + ABBREV + r"\.|[A-Z]\.(?=\s+[A-Z])|[A-Z][A-Za-z'’\-]*)"
# a run of capitalised words; a comma joins only an entity suffix, and "and" does not join
NAME = TOKEN + r"(?:(?:\s+(?:of|the|de|van|von|&))?\s+" + TOKEN + r"|,\s+" + ENTITY + r"(?![A-Za-z]))*"
NAME_RE = re.compile(NAME)
DEFINED = re.compile(
    r"\(\s*(?:hereinafter,?\s+)?(?:(?:each|together|collectively|individually)[^()“”\"]{0,40}?)?(?:the\s+)?[“\"]([^”\"]{2,40})[”\"]"
    r"(?:\s*(?:or|and)\s*(?:the\s+)?[“\"]([^”\"]{2,40})[”\"])*\s*\)")
# verb forms only, lower case: a heading such as "Release by Doe." is not a release clause
RELEASE_VERB = re.compile(
    r"(?:\b(?:hereby|shall|will|does|do|agrees? to|fully|completely|forever|irrevocably|unconditionally|generally|and)\s+"
    r"(?:(?:fully|forever|completely|irrevocably|unconditionally|generally|finally)\s+(?:and\s+)?)*release\b"
    r"|\breleases\b|\brelease\s*,?\s+(?:and\s+)?(?:forever\s+)?(?:discharge|acquit))"
    r"(?:\s*,?\s*(?:acquits?|remises?|waives?))*(?:\s*,?\s*and\s+(?:forever\s+)?(?:discharges?|acquits?))*")
FROM = re.compile(r"\b(?:of\s+and\s+)?from\b", re.I)
SENTENCE_BREAK = re.compile(r"(?<!\b" + r")(?<!\b".join(["Mr", "Mrs", "Ms", "Dr", "Jr", "Sr", "St", "Inc", "Corp", "Ltd", "Co", "No"]) + r")\.\s+(?=[A-Z0-9(])")


class Hit(object):
    def __init__(self, page, line, quote):
        self.page = page
        self.line = line
        self.quote = quote

    @property
    def cite(self):
        return "p. %d:%d" % (self.page, self.line)

    def as_dict(self):
        return {"page": self.page, "line": self.line, "cite": self.cite, "quote": self.quote}


def _squash(s):
    return re.sub(r"\s+", " ", s).strip()


def _quote(lines, i, limit=240):
    text = _squash(" ".join(lines[i:i + 4]))
    if len(text) > limit:
        cut = text[:limit]
        text = cut[:cut.rfind(" ")] + " …" if " " in cut else cut + "…"
    return text


def find(pgs, patterns, max_hits=6):
    """Hits for any of the patterns. A window is a line joined with the two after it; a hit counts
    for the line the match starts on."""
    rx = [re.compile(p, re.I) for p in patterns]
    hits = []
    for pn, lines in enumerate(pgs, 1):
        for i, ln in enumerate(lines):
            if not ln.strip():
                continue
            window = ln + " " + " ".join(lines[i + 1:i + 3])
            for r in rx:
                m = r.search(window)
                if m and m.start() <= len(ln):
                    hits.append(Hit(pn, i + 1, _quote(lines, i)))
                    break
            if len(hits) >= max_hits:
                return hits
    return hits


# --------------------------------------------------------------------------- names

# words that mark a defined term, not a person or an entity: "Release Effective Date", "Released Parties"
GENERIC = {"date", "dates", "party", "parties", "agreement", "claims", "claim", "amount", "payment", "payments",
           "property", "action", "section", "sections", "period", "deadline", "documents", "document", "deed",
           "escrow", "notice", "order", "court", "release", "releases", "released", "releasees", "releasors",
           "signatories", "exhibit", "recitals", "code", "procedure", "instrument", "instruments", "funds",
           "page", "paragraph", "article", "interest", "proceeds", "closing", "term", "terms", "law", "state",
           "on", "upon", "effective", "in", "at", "for", "by", "to", "if", "as"}
AKA = re.compile(r",?\s*\(?(?:also known as|formerly known as|a/k/a|aka|f/k/a|fka|doing business as|d/b/a|dba)\s+(" + NAME + r")\)?\s*$")
PAGE_MARK = re.compile(r"^\s*(?:Page\s+)?\d+(?:\s+of\s+\d+)?\s*$", re.I)
GROUP_ALIAS = re.compile(r"\b(?:parties|releasees|releasors|persons|entities|signatories|defendants|plaintiffs)$", re.I)


def _norm(s):
    return "".join(c for c in (s or "").casefold() if c.isalnum())


def _clean_name(raw, not_names):
    """Trim a captured run of capitalised words down to a name, or return ''."""
    s = _squash(raw).strip(" ,;:.")
    s = re.sub(r"^(?:(?:By|And|Between|Among|Plaintiff|Defendant|Cross-Complainant|Cross-Defendant|Whereas|This|The|Each|Mr\.|Ms\.|Mrs\.|Dr\.)\s+)+", "", s)
    s = re.sub(r"\s+(?:and|of|the|&)$", "", s).strip(" ,;:.")
    # a heading in capitals that ran into the name: "MUTUAL RELEASE Acme Widgets"
    s = re.sub(r"^(?:[A-Z][A-Z'’\-]+\s+){2,}(?=[A-Z][a-z])", "", s)
    if re.search(r"\b(?:Inc|Corp|Ltd|Co|Jr|Sr)$", s):
        s += "."
    if not s or s in not_names or _norm(s) in {_norm(x) for x in not_names}:
        return ""
    words = s.replace(",", " ").split()
    if any(w.strip(".").lower() in GENERIC for w in words):
        return ""
    if len(words) < 2 and not re.search(ENTITY + r"$", s):
        return ""
    return s


def _flat(pgs):
    return re.sub(r"\s+", " ", "\n".join("\n".join(ln for ln in pg if not PAGE_MARK.match(ln)) for pg in pgs))


def parties(pgs, not_names):
    """Defined persons and entities: [(full name, [aliases])], read from `Name ("Alias")` forms."""
    flat = _flat(pgs)
    blocked = {_norm(x) for x in not_names}
    out, seen = [], set()
    for m in DEFINED.finditer(flat):
        aliases = [a for a in m.groups() if a]
        if all(_norm(a) in blocked or GROUP_ALIAS.search(a) for a in aliases):
            continue
        before = flat[max(0, m.start() - 240):m.start()].rstrip(" ,")
        # drop a trailing description: ", a California limited liability company", ", an individual"
        before = re.sub(r",?\s+an?\s+[A-Za-z][A-Za-z \-]{0,70}$", "", before).rstrip(" ,")
        # "Jane Doe, also known as Jane Example" puts the first name forward; the second becomes an alias
        aka = AKA.search(before)
        if aka:
            aliases.append(aka.group(1))
            before = before[:aka.start()].rstrip(" ,")
        name = ""
        for c in reversed(list(NAME_RE.finditer(before))):
            if c.end() != len(before):
                break
            name = _clean_name(c.group(0), not_names)
            break
        if not name:
            continue
        key = _norm(name)
        if key in seen:
            continue
        seen.add(key)
        out.append((name, [a for a in aliases if _norm(a) not in blocked]))
    return out


def groups(pgs, defined, not_names, classes):
    """Group terms such as "Released Parties": {alias: ([names], [classes])}, read from
    `A, B and their agents (collectively, the "Released Parties")`."""
    flat = _flat(pgs)
    out = {}
    for m in DEFINED.finditer(flat):
        for alias in [a for a in m.groups() if a]:
            if not GROUP_ALIAS.search(alias):
                continue
            before = flat[max(0, m.start() - 400):m.start()]
            stops = [x.end() for x in SENTENCE_BREAK.finditer(before)]
            before = before[stops[-1]:] if stops else before
            # read what follows the verb when the definition sits inside a release clause
            vms = list(RELEASE_VERB.finditer(before))
            if vms:
                before = before[vms[-1].end():]
            names, cls = _names_in(before, defined, not_names, classes, {})
            if names or cls:
                out[alias] = (names, cls)
    return out


def _names_in(segment, defined, not_names, classes, group_table=None):
    """Persons, entities and classes named in a stretch of text."""
    found, used = [], []
    seg = segment
    cls = []

    def claim(span, name):
        for a, b in used:
            if span[0] < b and span[1] > a:
                return
        used.append(span)
        if name and name not in found:
            found.append(name)

    # group terms first: "the Released Parties" stands for the names in its definition
    for alias in sorted(group_table or {}, key=len, reverse=True):
        for m in re.finditer(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", seg):
            names, gcls = group_table[alias]
            claim(m.span(), None)
            for n in names:
                if n not in found:
                    found.append(n)
            for c in gcls:
                if c not in cls:
                    cls.append(c)
    # defined parties by full name, then by alias (longest first so a short alias does not shadow)
    table = []
    for full, aliases in defined:
        table.append((full, full))
        for a in aliases:
            table.append((a, full))
    for label, full in sorted(table, key=lambda t: -len(t[0])):
        for m in re.finditer(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", seg):
            claim(m.span(), full)
    # other capitalised runs
    for m in NAME_RE.finditer(seg):
        name = _clean_name(m.group(0), not_names)
        if name:
            claim(m.span(), name)
    for c in classes:
        if c not in cls and re.search(r"\b" + re.escape(c) + r"\b", seg, re.I):
            cls.append(c)
    return found, cls


def _sentence(lines, i):
    """(first line, last line) of the sentence that line i sits in, by full stops at line ends."""
    j = i
    while (j > 0 and lines[j - 1].strip() and not PAGE_MARK.match(lines[j - 1])
           and not re.search(r"[.;:]\s*$", lines[j - 1]) and i - j < 8):
        j -= 1
    k = i
    while (k + 1 < len(lines) and lines[k + 1].strip() and not PAGE_MARK.match(lines[k + 1])
           and not re.search(r"\.\s*$", lines[k]) and k - i < 16):
        k += 1
    return j, k


def release(pgs, table=None):
    """The release passages, read for who releases whom.

    Returns {"clauses": [{"cite", "page", "line", "quote", "releasing", "released", "classes",
             "each_other"}], "released", "releasing", "classes", "mutual": Hit or None,
             "defined": [(name, aliases)]}.
    """
    table = table or _rules.terms()
    not_names = table.get("not_names", [])
    classes = table.get("classes", [])
    defined = parties(pgs, not_names)
    all_names = [d[0] for d in defined]
    group_table = groups(pgs, defined, not_names, classes)
    clauses = []

    for pn, lines in enumerate(pgs, 1):
        i = 0
        while i < len(lines):
            if not lines[i].strip():
                i += 1
                continue
            window = lines[i] + " " + " ".join(lines[i + 1:i + 3])
            m = RELEASE_VERB.search(window)
            if not (m and m.start() <= len(lines[i])):
                i += 1
                continue
            j, k = _sentence(lines, i)
            sentence = _squash(" ".join(lines[j:k + 1]))
            got = False
            for vm in RELEASE_VERB.finditer(sentence):
                rest = sentence[vm.end():]
                fm = FROM.search(rest)
                if not fm:
                    continue
                obj = rest[:fm.start()]
                if SENTENCE_BREAK.search(obj):
                    continue
                subj = sentence[:vm.start()]
                stops = [x.end() for x in SENTENCE_BREAK.finditer(subj)]
                subj = subj[stops[-1]:] if stops else subj
                each_other = bool(re.search(r"\b(?:each other|one another|the other part(?:y|ies))\b", obj, re.I))
                names, cls = _names_in(obj, defined, not_names, classes, group_table)
                subj_names, _c = _names_in(subj, defined, not_names, classes, group_table)
                if each_other or (not names and re.search(r"\bpart(?:y|ies)\b", obj, re.I)):
                    each_other = True
                    names = names or list(all_names)
                    subj_names = subj_names or list(all_names)
                if not names and not cls:
                    continue
                got = True
                quote = sentence if len(sentence) <= 420 else sentence[:420].rsplit(" ", 1)[0] + " …"
                clauses.append({"page": pn, "line": i + 1, "cite": "p. %d:%d" % (pn, i + 1), "quote": quote,
                                "releasing": subj_names, "released": names, "classes": cls,
                                "each_other": each_other})
            i = (k + 1) if (got and k > i) else (i + 1)
    released, releasing, cls_all = [], [], []
    for c in clauses:
        for n in c["released"]:
            if n not in released:
                released.append(n)
        for n in c["releasing"]:
            if n not in releasing:
                releasing.append(n)
        for x in c["classes"]:
            if x not in cls_all:
                cls_all.append(x)
    mutual_hits = find(pgs, [t for t in table["terms"] if t["id"] == "release_mutual"][0]["patterns"], 1)
    return {"clauses": clauses, "released": released, "releasing": releasing, "classes": cls_all,
            "mutual": mutual_hits[0] if mutual_hits else None, "defined": defined}


def others_released(rel, only, by=None):
    """Released persons and entities other than `only`.

    A clause in which `only` is the sole releasing party is the return release and is left out.
    With `by`, only the clauses that `by` gives are read, and `by` is left out of the result.
    """
    d = rel["defined"]
    out = []
    for c in rel["clauses"]:
        givers = c["releasing"]
        if givers and all(same_party(g, only, d) for g in givers) and not c["each_other"]:
            continue
        if by and givers and not any(same_party(g, by, d) for g in givers):
            continue
        for n in c["released"]:
            if same_party(n, only, d) or (by and same_party(n, by, d)):
                continue
            if n not in out:
                out.append(n)
    return out


def same_party(a, b, defined):
    """True when two names point at one defined party, or match without regard to case and punctuation."""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    for full, aliases in defined:
        keys = {_norm(full)} | {_norm(x) for x in aliases}
        if na in keys and nb in keys:
            return True
    return False


# --------------------------------------------------------------------------- the check

def check(path=None, text=None, release_only=None, expect_none=None, strict=False, by=None, rule_dir=None):
    """Run the term list. Returns (result dict, exit code)."""
    table = _rules.terms(rule_dir)
    if text is not None:
        pgs = _pdf.from_text(text)
        label = "pasted text"
    else:
        pgs = _pdf.pages(path)
        label = os.path.basename(path)
    chars = _pdf.char_count(pgs)
    rows = []
    for t in table["terms"]:
        hits = find(pgs, t["patterns"])
        rows.append({"id": t["id"], "group": t["group"], "label": t["label"], "th": t.get("th", ""),
                     "found": bool(hits), "hits": [h.as_dict() for h in hits]})
    rel = release(pgs, table)
    code = 0
    problems = []
    if chars == 0:
        problems.append("No text could be read from this file. A scanned PDF needs OCR first.")
        code = 1
    if release_only:
        if not rel["released"]:
            problems.append("--release-only %s: no released person or entity could be read from a release passage; "
                            "read the release by eye." % release_only)
            code = 1
        else:
            others = others_released(rel, release_only, by)
            if others:
                problems.append("--release-only %s: the release also names %s." % (release_only, "; ".join(others)))
                code = 1
            if not any(same_party(n, release_only, rel["defined"]) for n in rel["released"]):
                problems.append("--release-only %s: that name was not read among the released parties." % release_only)
                code = 1
        if strict and rel["classes"]:
            problems.append("--strict: the release also reaches these classes: %s." % ", ".join(rel["classes"]))
            code = 1
    for term_id in (expect_none or []):
        term_id = term_id.strip().replace("-", "_")
        if not term_id:
            continue
        row = next((r for r in rows if r["id"] == term_id), None) or \
            next((r for r in rows if r["id"].startswith(term_id)), None)
        if row is None:
            problems.append("--expect-none %s: no such term in rules/terms.json." % term_id)
            code = 1
        elif row["found"]:
            problems.append("--expect-none %s: FOUND at %s." % (row["id"], row["hits"][0]["cite"]))
            code = 1
    result = {
        "file": label, "pages": len(pgs), "chars": chars, "groups": table["groups"], "terms": rows,
        "release": {"clauses": rel["clauses"], "released": rel["released"],
                    "releasing": rel["releasing"], "classes": rel["classes"],
                    "mutual": rel["mutual"].as_dict() if rel["mutual"] else None,
                    "defined": [{"name": n, "aliases": a} for n, a in rel["defined"]]},
        "problems": problems,
    }
    return result, code


def render(result):
    lines = ["TERMS — %s (%d page%s read, %s characters)" % (
        result["file"], result["pages"], "" if result["pages"] == 1 else "s", format(result["chars"], ",")), ""]
    for g in result["groups"]:
        rows = [r for r in result["terms"] if r["group"] == g]
        if not rows:
            continue
        lines.append(g)
        for r in rows:
            if r["found"]:
                h = r["hits"][0]
                more = ("; also %s" % ", ".join(x["cite"] for x in r["hits"][1:4])) if len(r["hits"]) > 1 else ""
                lines.append("  FOUND  %s — %s%s" % (r["label"], h["cite"], more))
                lines.append("         \"%s\"" % h["quote"])
            else:
                lines.append("  —      %s — %s" % (r["label"], NOT_FOUND))
        lines.append("")
    rel = result["release"]
    lines.append("Release, read closely")
    if rel["clauses"]:
        for c in rel["clauses"]:
            lines.append("  %s  \"%s\"" % (c["cite"], c["quote"]))
            lines.append("      releasing: %s" % ("; ".join(c["releasing"]) or "no name read"))
            lines.append("      released: %s%s" % ("; ".join(c["released"]) or "no name read",
                                                 (" · classes: %s" % ", ".join(c["classes"])) if c["classes"] else ""))
        lines.append("  Released, all clauses: %s" % ("; ".join(rel["released"]) or "no name read"))
        lines.append("  Classes also released: %s" % (", ".join(rel["classes"]) or "none read"))
        lines.append("  Mutual release wording: %s" % (("FOUND %s" % rel["mutual"]["cite"]) if rel["mutual"] else NOT_FOUND))
    else:
        lines.append("  A release clause with named parties: %s" % NOT_FOUND)
    if rel["defined"]:
        lines.append("  Defined parties: %s" % "; ".join(
            "%s%s" % (d["name"], (" (%s)" % ", ".join(d["aliases"])) if d["aliases"] else "") for d in rel["defined"]))
    if result["problems"]:
        lines.append("")
        for p in result["problems"]:
            lines.append("CHECK: %s" % p)
    return "\n".join(lines)
