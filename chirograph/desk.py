"""The desk: a large-type window in the browser, served from this computer.

    chirograph desk [--matter DIR] [--port 8775] [--no-open]

Starts a Python http.server on 127.0.0.1 and opens /desk/index.html. The page reads the same
engine as the command line through small JSON endpoints: the ladder, the clocks, the closing
list and the terms check. The desk shows; it does not change a matter file. Each API call
carries a token printed into the page at start-up, and the server answers requests addressed
to 127.0.0.1 or localhost. When the port is taken it tries the next one.

Vendored and cut down from Cursitor (cursitor/desk.py), same author, MIT.
"""
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import brief as _brief
from . import closing as _closing
from . import courtdays as cd
from . import matter as _matter
from . import offers as _offers
from . import terms as _terms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "desk")
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript",
         ".json": "application/json", ".svg": "image/svg+xml"}
MAX_BODY = 4 * 1024 * 1024
AGREEMENT_EXT = (".pdf", ".txt")


def html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class State(object):
    token = ""
    matter = None
    port = 8775
    today = None


def agreements(matter_dir):
    """Agreement files the terms check can read: the matter's agreements/ folder."""
    d = os.path.join(matter_dir, "agreements")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join("agreements", f) for f in os.listdir(d)
                  if f.lower().endswith(AGREEMENT_EXT) and not f.startswith("."))


def state(matter_dir, today=None):
    """Everything the page draws, as one JSON object."""
    m, day, views = _offers.evaluate(matter_dir, today)
    cur = m.get("currency") or "$"
    pos = _offers.positions(views)
    _m, rws = _closing.rows(matter_dir)
    amounts = [float(v.offer["amount"]) for v in views if v.offer.get("amount") is not None]

    def pos_row(v):
        return None if not v else {"id": v.id, "from": v.offer["from"], "amount": v.offer["amount"],
                                   "amount_text": _offers.money(v.offer["amount"], cur), "status": v.status,
                                   "made": v.offer["made"]}

    return {
        "matter": {"name": m.get("name", ""), "case_number": m.get("case_number", ""), "court": m.get("court", ""),
                   "court_tz": m.get("court_tz", ""), "reader_tz": m.get("reader_tz", "")},
        "today": day.isoformat(),
        "today_text": cd.fmt_full(day),
        "offers": [dict(v.as_dict(cur), made_text=cd.fmt_full(cd.parse_date(v.offer["made"]))) for v in views],
        "max_amount": max(amounts) if amounts else 0,
        "positions": {"plaintiff": pos_row(pos["plaintiff"]), "defendant": pos_row(pos["defendant"]),
                      "gap": pos["gap"], "gap_text": _offers.money(pos["gap"], cur) if pos["gap"] is not None else "",
                      "midpoint": pos["midpoint"],
                      "midpoint_text": _offers.money(pos["midpoint"], cur) if pos["midpoint"] is not None else "",
                      "accepted": pos_row(pos["accepted"])},
        "closing": [dict(r.as_dict(), date_text=cd.fmt_full(r.date) if r.date else "",
                         days=(r.date - day).days if r.date else None) for r in rws],
        "agreements": agreements(matter_dir),
        "brief": _brief.brief(matter_dir, day.isoformat()),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ChirographDesk/0.1"

    def log_message(self, fmt, *args):  # quiet console
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _token_ok(self, query):
        t = self.headers.get("X-Chirograph-Token") or (query.get("t") or [""])[0]
        return secrets.compare_digest(t, State.token)

    def _inside(self, rel):
        """A path inside the matter folder, or None."""
        if not State.matter or not rel:
            return None
        p = os.path.realpath(os.path.join(State.matter, rel))
        root = os.path.realpath(State.matter)
        if (p == root or p.startswith(root + os.sep)) and os.path.isfile(p) and p.lower().endswith(AGREEMENT_EXT):
            return p
        return None

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "host"})
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/desk", "/desk/"):
            self.send_response(302)
            self.send_header("Location", "/desk/index.html")
            self.end_headers()
            return
        if u.path.startswith("/desk/"):
            name = os.path.basename(urllib.parse.unquote(u.path[len("/desk/"):]))
            p = os.path.join(STATIC, name)
            if not os.path.isfile(p):
                return self._send(404, {"error": "not found"})
            with open(p, "rb") as fh:
                body = fh.read()
            if name == "index.html":
                body = body.replace(b"{{TOKEN}}", State.token.encode())
            return self._send(200, body, TYPES.get(os.path.splitext(name)[1], "application/octet-stream"))
        if not self._token_ok(q):
            return self._send(403, {"error": "token"})
        try:
            if u.path == "/api/state":
                if not State.matter:
                    return self._send(200, {"matter": None})
                return self._send(200, state(State.matter, State.today))
            if u.path == "/api/terms":
                p = self._inside((q.get("file") or [""])[0])
                if not p:
                    return self._send(400, {"error": "not on this disk, or outside the matter folder"})
                result, _code = _terms.check(p, release_only=(q.get("release_only") or [None])[0])
                return self._send(200, result)
        except cd.RuleError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:
            return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "host"})
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if not self._token_ok(q):
            return self._send(403, {"error": "token"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": "text over 4 MB"})
            data = json.loads((self.rfile.read(n) if n else b"{}").decode("utf-8") or "{}")
            if u.path == "/api/terms":
                text = data.get("text") or ""
                if not text.strip():
                    return self._send(400, {"error": "no text"})
                result, _code = _terms.check(text=text, release_only=data.get("release_only") or None)
                return self._send(200, result)
        except cd.RuleError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:
            return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})
        return self._send(404, {"error": "not found"})


def make_server(port=8775, matter=None, today=None, tries=10):
    """Bind 127.0.0.1 on `port` or the next free one. Returns (httpd, port)."""
    State.token = secrets.token_urlsafe(18)
    State.matter = _matter.find(matter) if matter else _matter.find()
    State.today = today
    httpd = None
    for p in range(port, port + tries):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            print("port %d is in use; trying %d" % (p, p + 1))
    if httpd is None:
        return None, None
    State.port = httpd.server_address[1]
    return httpd, State.port


def serve(port=8775, matter=None, open_browser=True, today=None):
    httpd, port = make_server(port, matter, today)
    if httpd is None:
        print("no free port found; pass --port")
        return 1
    url = "http://127.0.0.1:%d/desk/index.html" % port
    print("Chirograph desk: %s" % url, flush=True)
    print("Matter: %s" % (State.matter or "none (start with --matter <folder>)"))
    print("Token: %s" % State.token, flush=True)
    print("Press Control-C to stop.", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0
