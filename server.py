"""TRADELINE chat proxy. Keeps the model API key on the server and enforces the free limit (default 5 generations).
Python standard library only. Run: python server.py   (see README.md)."""
from __future__ import annotations
import json, os, re, sqlite3, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def cfg() -> dict:
    e = os.environ.get
    return {
        "port": int(e("PORT", "8080")), "key": e("ANTHROPIC_API_KEY", ""),
        "upstream": e("UPSTREAM_URL", "https://api.anthropic.com/v1/messages"),
        "model": e("CLAUDE_MODEL", "claude-sonnet-5-5"), "free": int(e("FREE_LIMIT", "5")), "ip_daily": int(e("IP_DAILY_LIMIT", "25")),
        "paid": {x.strip().lower() for x in e("PAID_EMAILS", "").split(",") if x.strip()},
        "origins": [x.strip() for x in e("ALLOWED_ORIGINS", "*").split(",") if x.strip()], "db": e("DB_PATH", "usage.db"), "max_tokens": int(e("MAX_TOKENS", "600")),
    }


SYSTEM = ("You are TRADELINE Legal Intelligence, the assistant of TRADELINE EUROPE, a trade-support company in Warsaw, Poland. You help entrepreneurs, importers, "
          "exporters and trade specialists with international trade (customs and duties, import and export requirements, documents, VAT and other taxes on "
          "cross-border operations, contracts and delivery terms, compliance, logistics) and with the company's services. Jurisdictions: the European Union and "
          "Poland first; say clearly when a question is outside them.\nEvidence first:\n"
          "- Never present a guess as a legal fact. Separate what is mandatory from what is only recommended.\n"
          "- Name the official source where the answer can be checked (EUR-Lex, TARIC, the Polish ISAP and Dziennik Ustaw, the Ministry of Finance). Mention a "
          "specific act or article only if you are certain it exists and applies; otherwise say which source to search. Never invent regulation numbers, article "
          "numbers, rates or links.\n"
          "- Law changes and depends on the date. When the date of the operation, the goods (CN/TARIC code), the country of origin or the roles of the parties "
          "matter and are missing, ask for them (at most three short questions) and give general orientation meanwhile.\n"
          "- If you cannot confirm something, say so plainly and say what is missing.\n"
          "- You give information, not legal advice. For high-risk operations or binding conclusions recommend verification by a qualified specialist or the "
          "TRADELINE team.\nStyle: reply in the user's language; be concise and structured (short paragraphs or bullet lists), about 200 words unless asked for more.")
VID = re.compile(r"^[a-z0-9]{8,64}$")


class Store:
    def __init__(self, path: str) -> None:
        self.lock = threading.Lock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.execute("CREATE TABLE IF NOT EXISTS visitor(id TEXT PRIMARY KEY, n INTEGER NOT NULL)")
        self.c.execute("CREATE TABLE IF NOT EXISTS ip(ip TEXT, day TEXT, n INTEGER NOT NULL, PRIMARY KEY(ip, day))")
        self.c.commit()

    def used(self, vid: str, ip: str) -> tuple[int, int]:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with self.lock:
            a = self.c.execute("SELECT n FROM visitor WHERE id=?", (vid,)).fetchone()
            b = self.c.execute("SELECT n FROM ip WHERE ip=? AND day=?", (ip, day)).fetchone()
        return (a[0] if a else 0, b[0] if b else 0)

    def bump(self, vid: str, ip: str) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with self.lock:
            self.c.execute("INSERT INTO visitor(id,n) VALUES(?,1) ON CONFLICT(id) DO UPDATE SET n=n+1", (vid,))
            self.c.execute("INSERT INTO ip(ip,day,n) VALUES(?,?,1) ON CONFLICT(ip,day) DO UPDATE SET n=n+1", (ip, day))
            self.c.commit()


def call_model(c: dict, messages: list[dict]) -> str:
    body = json.dumps({"model": c["model"], "max_tokens": c["max_tokens"], "system": SYSTEM, "messages": messages}).encode()
    req = urllib.request.Request(c["upstream"], data=body, method="POST", headers={"content-type": "application/json", "x-api-key": c["key"], "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read())
    return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text").strip()


def make_handler(c: dict, store: Store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            origin = self.headers.get("Origin", "")
            allow = origin if (origin and ("*" in c["origins"] or origin in c["origins"])) else ("*" if "*" in c["origins"] else "")
            if allow:
                self.send_header("Access-Control-Allow-Origin", allow)
            self.send_header("Vary", "Origin"); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            if origin and ("*" in c["origins"] or origin in c["origins"]):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers()

        def do_GET(self):
            self._send(200, {"ok": True}) if self.path == "/health" else self._send(404, {"error": "not_found"})

        def do_POST(self):
            if self.path != "/api/chat":
                return self._send(404, {"error": "not_found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n <= 0 or n > 40000:
                    return self._send(400, {"error": "bad_size"})
                d = json.loads(self.rfile.read(n))
                msgs = d["messages"]; vid = str(d.get("visitor", "")); email = str(d.get("email", "")).strip().lower()
                ok = isinstance(msgs, list) and 1 <= len(msgs) <= 12 and msgs[0].get("role") == "user" and msgs[-1].get("role") == "user" and VID.match(vid) \
                    and all(m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and 0 < len(m["content"]) <= 2000 for m in msgs)
                if not ok:
                    return self._send(400, {"error": "bad_request"})
            except Exception:
                return self._send(400, {"error": "bad_request"})
            if not c["key"] and "api.anthropic.com" in c["upstream"]:
                return self._send(503, {"error": "not_configured"})
            ip = (self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0])
            paid = email in c["paid"]
            used, ipn = store.used(vid, ip)
            if not paid and (used >= c["free"] or ipn >= c["ip_daily"]):
                return self._send(429, {"error": "limit"})
            try:
                reply = call_model(c, [{"role": m["role"], "content": m["content"]} for m in msgs])
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                return self._send(502, {"error": "upstream"})
            if not reply:
                return self._send(502, {"error": "empty"})
            if not paid:
                store.bump(vid, ip); used += 1
            self._send(200, {"reply": reply, "left": None if paid else max(0, c["free"] - used)})
    return H


def make_server(c: dict | None = None, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    c = c or cfg()
    return ThreadingHTTPServer((host, c["port"]), make_handler(c, Store(c["db"])))


if __name__ == "__main__":
    s = make_server()
    print("chat proxy listening on", s.server_address)
    s.serve_forever()
