"""The mediation statement, the muzzle list, the brief, the calendar file, the rule table, the CLI and the desk."""
import contextlib
import datetime as dt
import io
import json
import os
import socket
import threading
import urllib.error
import urllib.request

from chirograph import brief
from chirograph import cli
from chirograph import closing
from chirograph import desk
from chirograph import ics
from chirograph import matter
from chirograph import offers
from chirograph import rules
from chirograph import statement

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(ROOT, "examples", "doe-v-roe")


def make(tmp_path, reader_tz="Asia/Bangkok"):
    m = str(tmp_path / "doe")
    matter.scaffold(m, "Jane Doe", "Roe Holdings, LLC", "26CV000000", "Alameda", reader_tz=reader_tz)
    return m


def doc(m, rel, body="x"):
    p = os.path.join(m, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return rel


def fill(m):
    offers.add(m, "2026-08-03", "Jane Doe", "Roe Holdings, LLC", "letter", 240000, document=doc(m, "offers/a.txt"),
               expires="2026-08-17", expires_time="17:00")
    offers.add(m, "2026-08-12", "Roe Holdings, LLC", "Jane Doe", "998", 60000, method="email", document=doc(m, "offers/b.txt"))
    data = dict(statement.TEMPLATE)
    data.update({"for_party": "Plaintiff Jane Doe", "mediator": "Pat Example",
                 "session": {"date": "2026-09-09", "time": "09:30", "place": "by video"},
                 "parties": ["Jane Doe sold a business to Roe Holdings, LLC."],
                 "facts": ["Roe Holdings made seven payments and stopped."],
                 "claims": [{"claim": "Breach of the note", "basis": "Five unpaid payments", "amount": 150000},
                            {"claim": "Interest", "basis": "Contract rate", "amount": "21,500"}],
                 "terms_sought": ["One payment within 30 days.", "Dismissal with prejudice after payment."],
                 "signer": {"name": "Jane Doe", "role": "Plaintiff, self-represented"}})
    matter.write_json(m, "statement.json", data)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(argv)
    return code, out.getvalue()


# --------------------------------------------------------------------------- statement

def test_statement_builds_text_and_pdf_with_the_offer_history(tmp_path):
    m = make(tmp_path)
    fill(m)
    code, msgs, files = statement.build(m, today="2026-08-28")
    assert code == 0 and len(files) == 2
    with open(files[0], encoding="utf-8") as fh:
        text = fh.read()
    assert "MEDIATION STATEMENT OF PLAINTIFF JANE DOE" in text
    assert "Mon Aug 3 2026 | Jane Doe → Roe Holdings, LLC | letter | $240,000 | lapsed" in text
    assert "Wed Aug 12 2026 | Roe Holdings, LLC → Jane Doe | statutory offer (CCP §998) | $60,000 | open" in text
    assert "Total of the stated amounts |  | $171,500" in text
    assert "Last positions: plaintiff $240,000, defendant $60,000. Gap $180,000." in text
    assert "(b) Dismissal with prejudice after payment." in text
    from pypdf import PdfReader
    reader = PdfReader(files[1])
    page = reader.pages[0].extract_text()
    assert "MEDIATION STATEMENT OF PLAINTIFF JANE DOE" in page and "page 1" in page
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (612, 792)       # US Letter


def test_statement_text_has_one_paragraph_per_line(tmp_path):
    m = make(tmp_path)
    fill(m)
    long_para = "The note called for twelve quarterly payments. " * 12
    data = statement.load(m)
    data["facts"] = [long_para.strip()]
    matter.write_json(m, "statement.json", data)
    _c, _m, files = statement.build(m, today="2026-08-28")
    with open(files[0], encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert long_para.strip() in lines


def test_a_muzzled_word_stops_the_statement_with_line_numbers(tmp_path):
    m = make(tmp_path)
    fill(m)
    with open(os.path.join(m, "muzzles.txt"), "a", encoding="utf-8") as fh:
        fh.write("hardship\ncannot afford\n\\bpunish\n")
    data = statement.load(m)
    data["facts"] = ["Roe Holdings stopped paying.", "The delay is a hardship and Jane Doe cannot afford to wait."]
    matter.write_json(m, "statement.json", data)
    code, msgs, files = statement.build(m, today="2026-08-28")
    assert code == 1 and files == []
    assert not os.path.exists(os.path.join(m, "out", "mediation-statement.txt"))
    hits = [x for x in msgs if x.startswith("  line ")]
    assert len(hits) == 2 and "[hardship]" in hits[0] and "[cannot afford]" in hits[1]
    n = int(hits[0].split()[1].rstrip(":"))
    text = statement.to_text(statement.blocks(m, data, "2026-08-28"))
    assert "hardship" in text.splitlines()[n - 1]


def test_muzzle_hits_take_patterns_and_survive_a_bad_one():
    hits = statement.muzzle_hits("The note does not Punish late payment.\nNothing here.\n", ["\\bpunish", "(unclosed"])
    assert hits == [(1, "\\bpunish", "The note does not Punish late payment.")]


def test_statement_new_writes_a_blank_file_once(tmp_path):
    m = make(tmp_path)
    code, out = run(["statement", "new", m])
    assert code == 0 and os.path.exists(os.path.join(m, "statement.json"))
    try:
        statement.new(m)
        assert False
    except SystemExit:
        pass


# --------------------------------------------------------------------------- brief and calendar file

def closing_matter(tmp_path):
    m = make(tmp_path)
    offers.add(m, "2026-09-10", "Roe Holdings, LLC", "Jane Doe", "998", 60000, document=doc(m, "offers/b.txt"))
    closing.build(m, {"signed": "2026-09-17", "payment": {"amount": 120000, "days": 21, "cite": "Agreement §1"},
                      "hearings": [{"date": "2026-09-24", "time": "09:00", "title": "Case management conference"},
                                   {"date": "2026-12-03", "time": "09:00", "title": "Trial setting conference"}]})
    closing.advance(m, "notice", doc(m, "evidence/sent.txt"), "SERVED", "2026-09-18")
    return m


def test_brief_has_its_five_parts(tmp_path):
    m = closing_matter(tmp_path)
    text = brief.brief(m, "2026-09-21")
    for part in ("Today", "Next 7 days", "Clocks running", "Tasks with no evidence on this disk", "Offers open"):
        assert ("\n%s\n" % part) in text, part
    assert "Past its date, not finished" in text and "Notice of settlement of the entire case [SERVED]" in text
    assert "O1 ($60,000): 19 days left." in text
    assert "Notice of settlement of the entire case [SERVED] — next: FILED" in text
    assert "Thu Sep 24 2026 09:00 court time = Thu Sep 24 2026 23:00 in Asia/Bangkok." in text


def test_calendar_file_carries_the_arithmetic_and_utc_times(tmp_path):
    m = closing_matter(tmp_path)
    text, n = ics.to_ics(m, "2026-09-21", now=dt.datetime(2026, 9, 21, 16, 0, 0))
    assert n == 6                                              # offer clock, notice, payment, dismissal, two hearings
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    flat = text.replace("\r\n ", "")
    assert "DTSTART:20260924T160000Z" in flat                  # 09:00 Pacific daylight time
    assert "DTSTART:20261203T170000Z" in flat                  # 09:00 Pacific standard time
    assert "DTSTART;VALUE=DATE:20261008" in flat
    assert "settled Sep 17 + 45 days (Cal. Rules of Court\\, rule 3.1385(b))" in flat
    assert "next FILED: no evidence on this disk" in flat
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, line


# --------------------------------------------------------------------------- rule table

def test_each_rule_names_its_source_and_how_it_was_verified():
    table = rules.settlement()
    assert len(table["rules"]) >= 12
    for r in table["rules"]:
        for field in ("id", "label", "direction", "cite", "source", "verify", "text"):
            assert r.get(field), (r.get("id"), field)
        v = r["verify"]
        assert v.startswith("read https://") or v.startswith("from memory, not read"), r["id"]
        assert r["source"].startswith("https://leginfo.legislature.ca.gov/") or r["source"].startswith("https://courts.ca.gov/")
    for key, m in table["methods"].items():
        assert m["verify"].startswith("read https://") or m["verify"] == "from memory, not read", key
    assert rules.rule("ca.998_lapse")["days"] == 30 and rules.rule("ca.dismissal")["days"] == 45
    ext = rules.rule("ca.998_service_extension")
    assert ext["optional"] and ext["verify"].startswith("from memory, not read") and "Poster" in ext["authority"]
    assert rules.is_read(rules.rule("ca.notice_of_settlement")) and not rules.is_read(ext)
    assert "verify: read https://courts.ca.gov/cms/rules/index/three/rule3_1385 2026-11-23" in rules.describe()


def test_service_methods_resolve_through_aliases():
    assert rules.method("e-service")[0] == "email" and rules.method(None)[0] == "personal"
    assert rules.method("mail")[1]["add"] == 5 and rules.method("mail_out_of_us")[1]["add"] == 20
    try:
        rules.method("carrier pigeon")
        assert False
    except Exception as exc:
        assert "unknown service method" in str(exc)


# --------------------------------------------------------------------------- command line

def test_cli_end_to_end(tmp_path):
    m = str(tmp_path / "doe")
    code, out = run(["new-matter", m, "--plaintiff", "Jane Doe", "--defendant", "Roe Holdings, LLC",
                     "--case-no", "26CV000000", "--county", "Alameda", "--reader-tz", "Europe/London"])
    assert code == 0 and os.path.exists(os.path.join(m, "matter.json"))
    doc(m, "offers/b.txt")
    code, out = run(["offer", "add", m, "--made", "2026-08-12", "--from", "Roe Holdings, LLC", "--to", "Jane Doe",
                     "--kind", "998", "--amount", "60,000", "--method", "email", "--document", "offers/b.txt"])
    assert code == 0 and "O1 entered" in out and "Lapses Fri Sep 11 2026" in out
    code, out = run(["offer", "list", m, "--today", "2026-08-28"])
    assert code == 0 and "OPEN" in out and "Clocks running" in out
    code, out = run(["offer", "list", m, "--today", "2026-08-28", "--json"])
    assert json.loads(out)["offers"][0]["status_now"] == "OPEN"
    code, out = run(["offer", "decide", "O1", "sideways", m])
    assert code == 2 and "a decision is one of" in out
    code, out = run(["closing", "build", m, "--signed", "2026-09-17", "--payment-amount", "120000", "--payment-days", "21",
                     "--payment-cite", "Agreement §1", "--instrument", "Quitclaim deed", "--signer-abroad",
                     "--instrument-sign-days", "14", "--retain", "--hearing", "2026-09-24 09:00 Case management conference",
                     "--today", "2026-09-18"])
    assert code == 0 and "Closing list built: 6 tasks." in out
    code, out = run(["closing", "done", "notice", m, "--evidence", "evidence/none.txt"])
    assert code == 1 and "no evidence on this disk" in out
    doc(m, "evidence/built.txt")
    code, out = run(["closing", "done", "notice", m, "--evidence", "evidence/built.txt"])
    assert code == 0 and "notice is BUILT" in out
    code, out = run(["closing", "list", m, "--json"])
    assert [t["state_now"] for t in json.loads(out)["tasks"] if t["id"] == "notice"] == ["BUILT"]
    code, out = run(["brief", m, "--today", "2026-09-18"])
    assert code == 0 and out.startswith("BRIEF — Jane Doe v. Roe Holdings")
    code, out = run(["ics", m, "--today", "2026-09-18"])
    assert code == 0 and os.path.exists(os.path.join(m, "out", "settlement.ics"))
    code, out = run(["rules"])
    assert code == 0 and "ca.998_lapse" in out
    code, out = run([])
    assert code == 2


def test_cli_terms_check_exit_codes(tmp_path):
    p = str(tmp_path / "a.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write('Jane Doe ("Doe") and Acme Widgets, Inc. ("Acme") and Carol Smith ("Smith") agree.\n'
                 "1. Doe releases Acme and Smith from all claims.\n2. This Agreement is confidential.\n")
    code, out = run(["terms", "check", p])
    assert code == 0 and "FOUND  Confidentiality — p. 1:3" in out
    code, out = run(["terms", "check", p, "--release-only", "Acme"])
    assert code == 1 and "the release also names Carol Smith" in out
    code, out = run(["terms", "check", p, "--expect-none", "confidentiality,non-disparagement"])
    assert code == 1 and "--expect-none confidentiality: FOUND at p. 1:3." in out
    code, out = run(["terms", "check", str(tmp_path / "nope.pdf")])
    assert code == 2 and "not on this disk" in out


# --------------------------------------------------------------------------- desk

def fetch(url, token=None, data=None, host=None):
    req = urllib.request.Request(url, data=data)
    if token:
        req.add_header("X-Chirograph-Token", token)
    if host:
        req.add_header("Host", host)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_desk_serves_the_page_and_the_json_endpoints(tmp_path):
    m = closing_matter(tmp_path)
    doc(m, "agreements/a.txt", 'Jane Doe ("Doe") and Acme Widgets, Inc. ("Acme") agree.\n1. Doe releases Acme from all claims.\n')
    httpd, port = desk.make_server(free_port(), m, today="2026-09-21")
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        base = "http://127.0.0.1:%d" % port
        token = desk.State.token
        code, page = fetch(base + "/desk/index.html")
        assert code == 200 and token in page and "{{TOKEN}}" not in page
        assert "โต๊ะงานยอมความ" in page and 'id="lang"' in page          # Thai labels and the toggle
        code, body = fetch(base + "/api/state")
        assert code == 403                                               # no token
        code, body = fetch(base + "/api/state", token, host="example.com")
        assert code == 403                                               # another host name
        code, body = fetch(base + "/api/state", token)
        s = json.loads(body)
        assert code == 200 and s["matter"]["name"] == "Jane Doe v. Roe Holdings" and s["today"] == "2026-09-21"
        assert s["offers"][0]["running"] and s["offers"][0]["clock"]["line"].startswith("Lapses Sat Oct 10 2026")
        notice = [t for t in s["closing"] if t["id"] == "notice"][0]
        assert notice["state_now"] == "SERVED" and notice["next_state"] == "FILED"
        assert s["agreements"] == ["agreements/a.txt"] and s["brief"].startswith("BRIEF")
        code, body = fetch(base + "/api/terms?file=agreements/a.txt", token)
        assert code == 200 and json.loads(body)["release"]["released"] == ["Acme Widgets, Inc."]
        code, body = fetch(base + "/api/terms?file=../../etc/hosts", token)
        assert code == 400
        code, body = fetch(base + "/api/terms", token, json.dumps({"text": "This Agreement is confidential."}).encode())
        r = json.loads(body)
        assert code == 200 and [t for t in r["terms"] if t["id"] == "confidentiality"][0]["found"]
        assert fetch(base + "/api/nothing", token)[0] == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_desk_falls_to_the_next_port_when_one_is_taken(tmp_path):
    m = make(tmp_path)
    port = free_port()
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            httpd, got = desk.make_server(port, m)
        try:
            assert got != port and port < got < port + 10
            assert "port %d is in use" % port in out.getvalue()
        finally:
            httpd.server_close()
    finally:
        blocker.close()


def test_desk_page_has_both_languages_for_every_label():
    with open(os.path.join(ROOT, "desk", "index.html"), encoding="utf-8") as fh:
        page = fh.read()
    import re
    keys = set(re.findall(r'data-(?:i|ph)="([a-z0-9]+)"', page))
    for k in keys:
        m = re.search(r"\b%s: \[\"([^\"]*)\", \"([^\"]*)\"\]" % re.escape(k), page)
        assert m, k
        assert m.group(1) and re.search(r"[฀-๿]", m.group(2)), k


# --------------------------------------------------------------------------- the example matter

def test_the_example_matter_reads_end_to_end():
    assert os.path.exists(os.path.join(EXAMPLE, "matter.json")), "run scripts/make_example.py"
    text, views = offers.render(EXAMPLE, "2026-09-21")
    assert [v.status for v in views] == ["LAPSED", "LAPSED", "REJECTED", "ACCEPTED"]
    assert all(v.flags == [] for v in views)
    text, rws = closing.render(EXAMPLE, "2026-09-21")
    assert len(rws) == 11 and "FILED: no evidence on this disk" in text
    assert [r.shown for r in rws if r.id == "notice"] == ["SERVED"]
    for f in ("mediation-statement.txt", "mediation-statement.pdf", "settlement.ics", "terms check.txt"):
        assert os.path.exists(os.path.join(EXAMPLE, "out", f)), f
    assert statement.muzzle_entries(EXAMPLE) == ["leverage", "hardship", "cannot afford", "\\bpunish", "revenge"]
