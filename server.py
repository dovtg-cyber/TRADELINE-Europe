#!/usr/bin/env python3
"""TRADELINE API: password-based accounts and Gemini chat proxy."""
from __future__ import annotations

import hashlib, json, os, re, secrets, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VID=re.compile(r"^[a-z0-9]{8,64}$")


def cfg():
    e=os.environ.get
    return {"port":int(e("PORT","8080")),"key":e("GEMINI_API_KEY",e("GOOGLE_API_KEY","")),"upstream":e("GEMINI_UPSTREAM","https://generativelanguage.googleapis.com/v1beta/models"),"model":e("GEMINI_MODEL","gemini-2.5-flash"),"free":int(e("FREE_LIMIT","5")),"ip_daily":int(e("IP_DAILY_LIMIT","25")),"db":e("DB_PATH","usage.db"),"database_url":e("DATABASE_URL",""),"max_tokens":int(e("MAX_TOKENS","600")),"paid":{x.strip().lower() for x in e("PAID_EMAILS","").split(',') if x.strip()},"origins":[x.strip() for x in e("ALLOWED_ORIGINS","https://tradeline-europe-u7gw.onrender.com").split(',') if x.strip()]}

SYSTEM=("You are TRADELINE Legal Intelligence for TRADELINE EUROPE in Warsaw. Answer in the user's language. Evidence first: never invent laws, articles, rates or links. Prefer official links to EUR-Lex, EU legislation, TARIC, ISAP/Dziennik Ustaw and Polish tax/customs authorities. If a source cannot be verified, say so plainly. Separate mandatory rules from recommendations, ask at most three missing questions for country, date, goods, origin and party role, and recommend a qualified specialist for binding conclusions.")


def password_hash(value):return hashlib.pbkdf2_hmac("sha256",value.encode(),b"tradeline-account-v1",300000).hex()


class Store:
    def __init__(self,url="",path="usage.db"):
        self.pg=None;self.url=url;self.lock=threading.Lock()
        if url:
            import psycopg
            self.pg=psycopg
            with self.conn() as c:self.schema(c,True)
        else:
            self.db=sqlite3.connect(path,check_same_thread=False);self.db.execute("PRAGMA journal_mode=WAL");self.db.execute("PRAGMA foreign_keys=ON");self.schema(self.db,False);self.db.commit()
    def conn(self):return self.pg.connect(self.url)
    @staticmethod
    def schema(c,pg):
        if pg:
            c.execute("CREATE TABLE IF NOT EXISTS visitor(id text PRIMARY KEY,n bigint NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS ip(ip text,day text,n bigint NOT NULL,PRIMARY KEY(ip,day))")
            c.execute("CREATE TABLE IF NOT EXISTS accounts(id text PRIMARY KEY,email text UNIQUE NOT NULL,name text NOT NULL,password text NOT NULL,verified boolean NOT NULL DEFAULT true,created_at bigint NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS sessions(token text PRIMARY KEY,user_id text NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,expires_at bigint NOT NULL)")
        else:
            c.executescript("CREATE TABLE IF NOT EXISTS visitor(id TEXT PRIMARY KEY,n INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS ip(ip TEXT,day TEXT,n INTEGER NOT NULL,PRIMARY KEY(ip,day)); CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,expires_at INTEGER NOT NULL);")
    def register(self,name,email,password):
        uid=secrets.token_urlsafe(18);now=int(time.time())
        try:
            if self.pg:
                with self.conn() as c:c.execute("INSERT INTO accounts(id,email,name,password,verified,created_at) VALUES(%s,%s,%s,%s,true,%s)",(uid,email,name,password_hash(password),now))
            else:
                with self.lock:self.db.execute("INSERT INTO accounts(id,email,name,password,verified,created_at) VALUES(?,?,?,?,1,?)",(uid,email,name,password_hash(password),now));self.db.commit()
        except Exception as exc:
            if "unique" in str(exc).lower():raise ValueError("email_exists") from exc
            raise
        return uid
    def login(self,email,password):
        if self.pg:
            with self.conn() as c:row=c.execute("SELECT id,password FROM accounts WHERE email=%s",(email,)).fetchone()
        else:row=self.db.execute("SELECT id,password FROM accounts WHERE email=?",(email,)).fetchone()
        if not row or not secrets.compare_digest(row[1],password_hash(password)):return None,None
        token=secrets.token_urlsafe(32);expires=int(time.time())+30*86400
        if self.pg:
            with self.conn() as c:c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(%s,%s,%s)",(token,row[0],expires))
        else:
            with self.lock:self.db.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",(token,row[0],expires));self.db.commit()
        return token,self.account(token)
    def account(self,token):
        if self.pg:
            with self.conn() as c:row=c.execute("SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=%s AND s.expires_at>%s",(token,int(time.time()))).fetchone()
        else:row=self.db.execute("SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=? AND s.expires_at>?",(token,int(time.time()))).fetchone()
        return {"id":row[0],"email":row[1],"name":row[2],"verified":bool(row[3])} if row else None
    def logout(self,token):
        if self.pg:
            with self.conn() as c:c.execute("DELETE FROM sessions WHERE token=%s",(token,))
        else:
            with self.lock:self.db.execute("DELETE FROM sessions WHERE token=?",(token,));self.db.commit()
    def used(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        if self.pg:
            with self.conn() as c:a=c.execute("SELECT n FROM visitor WHERE id=%s",(vid,)).fetchone();b=c.execute("SELECT n FROM ip WHERE ip=%s AND day=%s",(ip,day)).fetchone()
        else:a=self.db.execute("SELECT n FROM visitor WHERE id=?",(vid,)).fetchone();b=self.db.execute("SELECT n FROM ip WHERE ip=? AND day=?",(ip,day)).fetchone()
        return (a[0] if a else 0,b[0] if b else 0)
    def bump(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        if self.pg:
            with self.lock:
                with self.conn() as c:c.execute("INSERT INTO visitor(id,n) VALUES(%s,1) ON CONFLICT(id) DO UPDATE SET n=visitor.n+1",(vid,));c.execute("INSERT INTO ip(ip,day,n) VALUES(%s,%s,1) ON CONFLICT(ip,day) DO UPDATE SET n=ip.n+1",(ip,day))
        else:
            with self.lock:self.db.execute("INSERT INTO visitor(id,n) VALUES(?,1) ON CONFLICT(id) DO UPDATE SET n=n+1",(vid,));self.db.execute("INSERT INTO ip(ip,day,n) VALUES(?,?,1) ON CONFLICT(ip,day) DO UPDATE SET n=n+1",(ip,day));self.db.commit()


def call_model(c,messages):
    contents=[{"role":"model" if m["role"]=="assistant" else "user","parts":[{"text":m["content"]}]} for m in messages]
    body=json.dumps({"systemInstruction":{"parts":[{"text":SYSTEM}]},"contents":contents,"generationConfig":{"temperature":0.2,"maxOutputTokens":c["max_tokens"]}}).encode()
    model=urllib.parse.quote(c["model"],safe="");url=c["upstream"].rstrip("/")+"/"+model+":generateContent"
    req=urllib.request.Request(url,data=body,method="POST",headers={"content-type":"application/json","x-goog-api-key":c["key"]})
    with urllib.request.urlopen(req,timeout=60) as r:payload=json.loads(r.read())
    return "".join(p["text"] for candidate in payload.get("candidates",[]) for p in candidate.get("content",{}).get("parts",[]) if isinstance(p.get("text"),str)).strip()


def make_handler(c,store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send_json(self,code,payload):
            data=json.dumps(payload).encode();origin=self.headers.get("Origin","");self.send_response(code)
            if origin in c["origins"]:self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Vary","Origin");self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
        def do_OPTIONS(self):
            self.send_response(204);origin=self.headers.get("Origin","")
            if origin in c["origins"]:self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Access-Control-Allow-Methods","POST, GET, OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type, Authorization");self.end_headers()
        def body(self):
            n=int(self.headers.get("Content-Length","0"))
            if n<=0 or n>40000:raise ValueError("bad_size")
            return json.loads(self.rfile.read(n))
        def token(self):
            value=self.headers.get("Authorization","");return value[7:] if value.startswith("Bearer ") else ""
        def do_GET(self):
            if self.path=="/health":return self.send_json(200,{"ok":True,"database":"postgresql" if c["database_url"] else "sqlite","ai":bool(c["key"]),"email":False,"provider":"gemini" if c["key"] else "none"})
            if self.path=="/api/account":
                account=store.account(self.token());return self.send_json(200,account) if account else self.send_json(401,{"error":"unauthorized"})
            self.send_json(404,{"error":"not_found"})
        def do_POST(self):
            try:body=self.body()
            except Exception:return self.send_json(400,{"error":"bad_request"})
            if self.path=="/api/auth/register":
                name=str(body.get("name","")).strip();email=str(body.get("email","")).strip().lower();password=str(body.get("password",""))
                if len(name)<2 or not EMAIL.match(email) or len(password)<8:return self.send_json(400,{"error":"bad_request"})
                try:uid=store.register(name,email,password)
                except ValueError:return self.send_json(409,{"error":"email_exists"})
                token,account=store.login(email,password)
                return self.send_json(201,{"ok":True,"token":token,"account":account})
            if self.path=="/api/auth/login":
                email=str(body.get("email","")).strip().lower();password=str(body.get("password",""));token,account=store.login(email,password)
                if not token:return self.send_json(401,{"error":"invalid_credentials"})
                return self.send_json(200,{"ok":True,"token":token,"account":account})
            if self.path=="/api/auth/logout":store.logout(self.token());return self.send_json(200,{"ok":True})
            if self.path in ("/api/auth/forgot","/api/auth/reset"):return self.send_json(501,{"error":"email_disabled"})
            if self.path=="/api/chat":
                messages=body.get("messages",[]);visitor=str(body.get("visitor",""));email=str(body.get("email","")).strip().lower()
                valid=isinstance(messages,list) and 1<=len(messages)<=12 and messages[0].get("role")=="user" and messages[-1].get("role")=="user" and VID.match(visitor) and all(m.get("role") in ("user","assistant") and isinstance(m.get("content"),str) and 0<len(m["content"])<=2000 for m in messages)
                if not valid:return self.send_json(400,{"error":"bad_request"})
                if not c["key"]:return self.send_json(503,{"error":"not_configured"})
                ip=self.headers.get("X-Forwarded-For","").split(',')[0].strip() or self.client_address[0];paid=email in c["paid"];used,ipn=store.used(visitor,ip)
                if not paid and (used>=c["free"] or ipn>=c["ip_daily"]):return self.send_json(429,{"error":"limit"})
                try:reply=call_model(c,messages)
                except (urllib.error.URLError,TimeoutError,ValueError,OSError):return self.send_json(502,{"error":"upstream"})
                if not reply:return self.send_json(502,{"error":"empty"})
                if not paid:store.bump(visitor,ip);used+=1
                return self.send_json(200,{"reply":reply,"left":None if paid else max(0,c["free"]-used)})
            self.send_json(404,{"error":"not_found"})
    return Handler


def make_server(c=None,host="0.0.0.0"):
    c=c or cfg();store=Store(c["database_url"],c["db"])
    return ThreadingHTTPServer((host,c["port"]),make_handler(c,store))

if __name__=="__main__":
    s=make_server();print("TRADELINE API listening on",s.server_address);s.serve_forever()
