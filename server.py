#!/usr/bin/env python3
"""TRADELINE API: free-tier-safe chat, account verification, and session handling."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VID = re.compile(r"^[a-z0-9]{8,64}$")


def cfg() -> dict:
    env = os.environ.get
    return {
        "port": int(env("PORT", "8080")),
        "key": env("ANTHROPIC_API_KEY", ""),
        "upstream": env("UPSTREAM_URL", "https://api.anthropic.com/v1/messages"),
        "model": env("CLAUDE_MODEL", "claude-sonnet-4-5"),
        "free": int(env("FREE_LIMIT", "5")),
        "ip_daily": int(env("IP_DAILY_LIMIT", "25")),
        "db": env("DB_PATH", "usage.db"),
        "database_url": env("DATABASE_URL", ""),
        "max_tokens": int(env("MAX_TOKENS", "600")),
        "paid": {x.strip().lower() for x in env("PAID_EMAILS", "").split(",") if x.strip()},
        "origins": [x.strip() for x in env("ALLOWED_ORIGINS", "https://tradeline-europe-u7gw.onrender.com").split(",") if x.strip()],
        "resend_api_key": env("RESEND_API_KEY", ""),
        "email_from": env("EMAIL_FROM", ""),
        "smtp_host": env("SMTP_HOST", ""),
        "smtp_port": int(env("SMTP_PORT", "587")),
        "smtp_user": env("SMTP_USER", ""),
        "smtp_pass": env("SMTP_PASS", ""),
        "smtp_from": env("SMTP_FROM", env("SMTP_USER", "")),
    }


SYSTEM = (
    "You are TRADELINE Legal Intelligence for TRADELINE EUROPE in Warsaw. Answer in the user's language. "
    "Evidence first: never invent laws, articles, rates or links. Prefer official links to EUR-Lex, EU legislation, "
    "TARIC, ISAP/Dziennik Ustaw and Polish tax/customs authorities. If a source cannot be verified, say so plainly. "
    "If an answer uses a source, provide the complete clickable https:// URL. Separate mandatory rules from recommendations, "
    "ask at most three missing questions for country, date, goods, origin and party role, and recommend a qualified "
    "specialist for binding conclusions."
)


class Store:
    """SQLite implementation for local/test use. Production should provide DATABASE_URL for PostgreSQL."""

    def __init__(self, path: str) -> None:
        self.lock = threading.Lock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.execute("PRAGMA foreign_keys=ON")
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS visitor(id TEXT PRIMARY KEY, n INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS ip(ip TEXT, day TEXT, n INTEGER NOT NULL, PRIMARY KEY(ip, day));
        CREATE TABLE IF NOT EXISTS accounts(
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            password TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
            verify_code TEXT, verify_until INTEGER,
            reset_code TEXT, reset_until INTEGER,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES accounts(id) ON DELETE CASCADE);
        """)
        self.c.commit()

    @staticmethod
    def password(value: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", value.encode(), b"tradeline-account-v1", 300_000).hex()

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

    def register(self, name: str, email: str, password: str) -> tuple[str, str]:
        email = email.lower().strip()
        code = f"{secrets.randbelow(1000000):06d}"
        user_id = secrets.token_urlsafe(18)
        now = int(time.time())
        with self.lock:
            try:
                self.c.execute(
                    "INSERT INTO accounts(id,email,name,password,verified,verify_code,verify_until,reset_code,reset_until,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (user_id, email, name, self.password(password), 0, code, now + 1800, None, None, now),
                )
                self.c.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("email_exists") from exc
        return user_id, code

    def resend_verification(self, email: str) -> str | None:
        email = email.lower().strip()
        code = f"{secrets.randbelow(1000000):06d}"
        with self.lock:
            row = self.c.execute("SELECT id FROM accounts WHERE email=?", (email,)).fetchone()
            if not row:
                return None
            self.c.execute("UPDATE accounts SET verify_code=?,verify_until=? WHERE email=?", (code, int(time.time()) + 1800, email))
            self.c.commit()
        return code

    def verify(self, email: str, code: str) -> bool:
        email = email.lower().strip()
        with self.lock:
            row = self.c.execute("SELECT id,verify_code,verify_until FROM accounts WHERE email=?", (email,)).fetchone()
            if not row or row[1] != code or int(time.time()) > row[2]:
                return False
            self.c.execute("UPDATE accounts SET verified=1,verify_code=NULL,verify_until=NULL WHERE id=?", (row[0],))
            self.c.commit()
        return True

    def login(self, email: str, password: str) -> tuple[str | None, str | None]:
        email = email.lower().strip()
        row = self.c.execute("SELECT id,verified,password FROM accounts WHERE email=?", (email,)).fetchone()
        if not row:
            return None, "invalid"
        if row[1] != 1:
            return None, "unverified"
        if not secrets.compare_digest(row[2], self.password(password)):
            return None, "invalid"
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + 30 * 86400
        with self.lock:
            self.c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, row[0], expires))
            self.c.commit()
        return token, None

    def account(self, token: str) -> dict | None:
        row = self.c.execute("SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=? AND s.expires_at>?", (token, int(time.time()))).fetchone()
        return {"id": row[0], "email": row[1], "name": row[2], "verified": bool(row[3])} if row else None

    def logout(self, token: str) -> None:
        with self.lock:
            self.c.execute("DELETE FROM sessions WHERE token=?", (token,))
            self.c.commit()

    def begin_reset(self, email: str) -> str | None:
        email = email.lower().strip()
        code = f"{secrets.randbelow(1000000):06d}"
        with self.lock:
            row = self.c.execute("SELECT id FROM accounts WHERE email=?", (email,)).fetchone()
            if not row:
                return None
            self.c.execute("UPDATE accounts SET reset_code=?,reset_until=? WHERE email=?", (code, int(time.time()) + 1800, email))
            self.c.commit()
        return code

    def reset_password(self, email: str, code: str, password: str) -> bool:
        email = email.lower().strip()
        with self.lock:
            row = self.c.execute("SELECT id,reset_code,reset_until FROM accounts WHERE email=?", (email,)).fetchone()
            if not row or row[1] != code or int(time.time()) > row[2]:
                return False
            self.c.execute("UPDATE accounts SET password=?,reset_code=NULL,reset_until=NULL,verified=1 WHERE id=?", (self.password(password), row[0]))
            self.c.execute("DELETE FROM sessions WHERE user_id=?", (row[0],))
            self.c.commit()
        return True


def send_resend(c: dict, to: str, subject: str, text: str) -> None:
    if not c["resend_api_key"] or not c["email_from"]:
        raise RuntimeError("email_not_configured")
    body = json.dumps({"from": c["email_from"], "to": [to], "subject": subject, "text": text}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST", headers={"Authorization": "Bearer " + c["resend_api_key"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError("email_provider_error")


def send_mail(c: dict, to: str, subject: str, text: str) -> None:
    if c["resend_api_key"]:
        send_resend(c, to, subject, text)
        return
    if not c["smtp_host"] or not c["smtp_user"] or not c["smtp_pass"] or not c["smtp_from"]:
        raise RuntimeError("email_not_configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = c["smtp_from"]
    msg["To"] = to
    msg.set_content(text)
    import smtplib
    with smtplib.SMTP(c["smtp_host"], c["smtp_port"], timeout=20) as smtp:
        smtp.starttls()
        smtp.login(c["smtp_user"], c["smtp_pass"])
        smtp.send_message(msg)


def call_model(c: dict, messages: list[dict]) -> str:
    body = json.dumps({"model": c["model"], "max_tokens": c["max_tokens"], "system": SYSTEM, "messages": messages}).encode()
    req = urllib.request.Request(c["upstream"], data=body, method="POST", headers={"content-type": "application/json", "x-api-key": c["key"], "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read())
    return "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text").strip()


def make_handler(c: dict, store: Store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, code: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(code)
            origin = self.headers.get("Origin", "")
            allowed = origin if origin in c["origins"] else ""
            if allowed:
                self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            if origin in c["origins"]:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 40000:
                raise ValueError("bad_size")
            return json.loads(self.rfile.read(length))

        def bearer_token(self) -> str:
            value = self.headers.get("Authorization", "")
            return value[7:] if value.startswith("Bearer ") else ""

        def do_GET(self) -> None:
            if self.path == "/health":
                return self.send_json(200, {"ok": True, "database": "sqlite" if not c["database_url"] else "configured", "ai": bool(c["key"]), "email": bool(c["resend_api_key"] or c["smtp_host"])})
            if self.path == "/api/account":
                account = store.account(self.bearer_token())
                return self.send_json(200, account) if account else self.send_json(401, {"error": "unauthorized"})
            self.send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            try:
                body = self.read_body()
            except Exception:
                return self.send_json(400, {"error": "bad_request"})

            if self.path == "/api/auth/register":
                name = str(body.get("name", "")).strip()
                email = str(body.get("email", "")).strip().lower()
                password = str(body.get("password", ""))
                if len(name) < 2 or not EMAIL.match(email) or len(password) < 8:
                    return self.send_json(400, {"error": "bad_request"})
                try:
                    _, code = store.register(name, email, password)
                except ValueError:
                    return self.send_json(409, {"error": "email_exists"})
                try:
                    send_mail(c, email, "Confirm your TRADELINE account", f"Hello {name},\n\nYour TRADELINE verification code is: {code}\n\nThe code expires in 30 minutes.\n")
                except Exception:
                    return self.send_json(503, {"error": "email_not_configured"})
                return self.send_json(201, {"ok": True, "email": email})

            if self.path == "/api/auth/resend":
                email = str(body.get("email", "")).strip().lower()
                code = store.resend_verification(email)
                if code:
                    try:
                        send_mail(c, email, "Your TRADELINE verification code", f"Your verification code is: {code}\nThe code expires in 30 minutes.\n")
                    except Exception:
                        return self.send_json(503, {"error": "email_not_configured"})
                return self.send_json(200, {"ok": True})

            if self.path == "/api/auth/verify":
                email = str(body.get("email", ""))
                code = str(body.get("code", ""))
                if not store.verify(email, code):
                    return self.send_json(400, {"error": "invalid_or_expired"})
                return self.send_json(200, {"ok": True, "verified": True})

            if self.path == "/api/auth/login":
                token, error = store.login(str(body.get("email", "")), str(body.get("password", "")))
                if error == "unverified":
                    return self.send_json(403, {"error": "unverified"})
                if not token:
                    return self.send_json(401, {"error": "invalid_credentials"})
                return self.send_json(200, {"ok": True, "token": token, "account": store.account(token)})

            if self.path == "/api/auth/logout":
                store.logout(self.bearer_token())
                return self.send_json(200, {"ok": True})

            if self.path == "/api/auth/forgot":
                email = str(body.get("email", "")).strip().lower()
                code = store.begin_reset(email)
                if code:
                    try:
                        send_mail(c, email, "Reset your TRADELINE password", f"Your password-reset code is: {code}\nThe code expires in 30 minutes.\n")
                    except Exception:
                        return self.send_json(503, {"error": "email_not_configured"})
                return self.send_json(200, {"ok": True})

            if self.path == "/api/auth/reset":
                email = str(body.get("email", "")).strip().lower()
                code = str(body.get("code", ""))
                password = str(body.get("password", ""))
                if len(password) < 8:
                    return self.send_json(400, {"error": "bad_password"})
                if not store.reset_password(email, code, password):
                    return self.send_json(400, {"error": "invalid_or_expired"})
                return self.send_json(200, {"ok": True})

            if self.path == "/api/chat":
                messages = body.get("messages", [])
                visitor = str(body.get("visitor", ""))
                email = str(body.get("email", "")).strip().lower()
                valid = (
                    isinstance(messages, list)
                    and 1 <= len(messages) <= 12
                    and messages[0].get("role") == "user"
                    and messages[-1].get("role") == "user"
                    and VID.match(visitor)
                    and all(message.get("role") in ("user", "assistant") and isinstance(message.get("content"), str) and 0 < len(message["content"]) <= 2000 for message in messages)
                )
                if not valid:
                    return self.send_json(400, {"error": "bad_request"})
                if not c["key"]:
                    return self.send_json(503, {"error": "not_configured"})
                ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
                paid = email in c["paid"]
                used, ip_count = store.used(visitor, ip)
                if not paid and (used >= c["free"] or ip_count >= c["ip_daily"]):
                    return self.send_json(429, {"error": "limit"})
                try:
                    reply = call_model(c, [{"role": message["role"], "content": message["content"]} for message in messages])
                except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                    return self.send_json(502, {"error": "upstream"})
                if not reply:
                    return self.send_json(502, {"error": "empty"})
                if not paid:
                    store.bump(visitor, ip)
                    used += 1
                return self.send_json(200, {"reply": reply, "left": None if paid else max(0, c["free"] - used)})

            self.send_json(404, {"error": "not_found"})

    return Handler


def make_server(c: dict | None = None, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    c = c or cfg()
    store = Store(c["db"])
    return ThreadingHTTPServer((host, c["port"]), make_handler(c, store))


if __name__ == "__main__":
    server = make_server()
    print("TRADELINE API listening on", server.server_address)
    server.serve_forever()
