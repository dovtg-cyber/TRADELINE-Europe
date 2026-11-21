#!/usr/bin/env python3
"""TRADELINE API: accounts, verification, password reset and AI chat proxy."""
from __future__ import annotations

import hashlib, json, os, re, secrets, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VID=re.compile(r"^[a-z0-9]{8,64}$")


def cfg():
    e=os.environ.get
    return {"port":int(e("PORT","8080")),"key":e("GEMINI_API_KEY",e("GOOGLE_API_KEY","")),"upstream":e("GEMINI_UPSTREAM","https://generativelanguage.googleapis.com/v1beta/models"),"model":e("GEMINI_MODEL","gemini-2.5-flash"),"free":int(e("FREE_LIMIT","5")),"ip_daily":int(e("IP_DAILY_LIMIT","25")),"db":e("DB_PATH","usage.db"),"database_url":e("DATABASE_URL",""),"max_tokens":int(e("MAX_TOKENS","600")),"paid":{x.strip().lower() for x in e("PAID_EMAILS","").split(',') if x.strip()},"origins":[x.strip() for x in e("ALLOWED_ORIGINS","https://tradeline-europe-u7gw.onrender.com").split(',') if x.strip()],"resend_api_key":e("RESEND_API_KEY",""),"email_from":e("EMAIL_FROM",""),"smtp_host":e("SMTP_HOST",""),"smtp_port":int(e("SMTP_PORT","587")),"smtp_user":e("SMTP_USER",""),"smtp_pass":e("SMTP_PASS",""),"smtp_from":e("SMTP_FROM",e("SMTP_USER",""))}

SYSTEM=("You are TRADELINE Legal Intelligence for TRADELINE EUROPE in Warsaw. Answer in the user's language. Evidence first: never invent laws, articles, rates or links. Prefer official links to EUR-Lex, EU legislation, TARIC, ISAP/Dziennik Ustaw and Polish tax/customs authorities. If a source cannot be verified, say so plainly. If an answer uses a source, provide the complete clickable https:// URL. Separate mandatory rules from recommendations, ask at most three missing questions for country, date, goods, origin and party role, and recommend a qualified specialist for binding conclusions.")


class SqliteStore:
    def __init__(self,path):
        self.lock=threading.Lock();self.c=sqlite3.connect(path,check_same_thread=False);self.c.execute("PRAGMA journal_mode=WAL");self.c.execute("PRAGMA foreign_keys=ON")
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS visitor(id TEXT PRIMARY KEY,n INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS ip(ip TEXT,day TEXT,n INTEGER NOT NULL,PRIMARY KEY(ip,day));
        CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,verified INTEGER NOT NOT NULL DEFAULT 0,verify_code TEXT,verify_until INTEGER,reset_code TEXT,reset_until INTEGER,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires_at INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES accounts(id) ON DELETE CASCADE);
        """);self.c.commit()
    @staticmethod
    def password(value):return hashlib.pbkdf2_hmac("sha256",value.encode(),b"tradeline-account-v1",300000).hex()
    def used(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        with self.lock:
            a=self.c.execute("SELECT n FROM visitor WHERE id=?",(vid,)).fetchone();b=self.c.execute("SELECT n FROM ip WHERE ip=? AND day=?",(ip,day)).fetchone()
        return (a[0] if a else 0,b[0] if b else 0)
    def bump(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        with self.lock:
            self.c.execute("INSERT INTO visitor(id,n) VALUES(?,1) ON CONFLICT(id) DO UPDATE SET n=n+1",(vid,));self.c.execute("INSERT INTO ip(ip,day,n) VALUES(?,?,1) ON CONFLICT(ip,day) DO UPDATE SET n=n+1",(ip,day));self.c.commit()
    def register(self,name,email,password):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}";uid=secrets.token_urlsafe(18);now=int(time.time())
        with self.lock:
            try:self.c.execute("INSERT INTO accounts(id,email,name,password,verified,verify_code,verify_until,reset_code,reset_until,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(uid,email,name,self.password(password),0,code,now+1800,None,None,now));self.c.commit()
            except sqlite3.IntegrityError as exc:raise ValueError("email_exists") from exc
        return uid,code
    def resend_verification(self,email):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}"
        with self.lock:
            row=self.c.execute("SELECT id FROM accounts WHERE email=?",(email,)).fetchone()
            if not row:return None
            self.c.execute("UPDATE accounts SET verify_code=?,verify_until=? WHERE email=?",(code,int(time.time())+1800,email));self.c.commit()
        return code
    def verify(self,email,code):
        email=email.lower().strip()
        with self.lock:
            row=self.c.execute("SELECT id,verify_code,verify_until FROM accounts WHERE email=?",(email,)).fetchone()
            if not row or row[1]!=code or int(time.time())>row[2]:return False
            self.c.execute("UPDATE accounts SET verified=1,verify_code=NULL,verify_until=NULL WHERE id=?",(row[0],));self.c.commit()
        return True
    def login(self,email,password):
        email=email.lower().strip();row=self.c.execute("SELECT id,verified,password FROM accounts WHERE email=?",(email,)).fetchone()
        if not row:return None,"invalid"
        if row[1]!=1:return None,"unverified"
        if not secrets.compare_digest(row[2],self.password(password)):return None,"invalid"
        token=secrets.token_urlsafe(32);expires=int(time.time())+30*86400
        with self.lock:self.c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",(token,row[0],expires));self.c.commit()
        return token,None
    def account(self,token):
        row=self.c.execute("SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=? AND s.expires_at>?",(token,int(time.time()))).fetchone()
        return {"id":row[0],"email":row[1],"name":row[2],"verified":bool(row[3])} if row else None
    def logout(self,token):
        with self.lock:self.c.execute("DELETE FROM sessions WHERE token=?",(token,));self.c.commit()
    def begin_reset(self,email):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}"
        with self.lock:
            row=self.c.execute("SELECT id FROM accounts WHERE email=?",(email,)).fetchone()
            if not row:return None
            self.c.execute("UPDATE accounts SET reset_code=?,reset_until=? WHERE email=?",(code,int(time.time()+1800),email));self.c.commit()
        return code
    def reset_password(self,email,code,password):
        email=email.lower().strip()
        with self.lock:
            row=self.c.execute("SELECT id,reset_code,reset_until FROM accounts WHERE email=?",(email,)).fetchone()
            if not row or row[1]!=code or int(time.time())>row[2]:return False
            self.c.execute("UPDATE accounts SET password=?,reset_code=NULL,reset_until=NULL,verified=1 WHERE id=?",(self.password(password),row[0]));self.c.execute("DELETE FROM sessions WHERE user_id=?",(row[0],));self.c.commit()
        return True


class PostgresStore:
    def __init__(self,url):
        import psycopg
        self.psycopg=psycopg;self.url=url;self.lock=threading.Lock();self._exec_script()
    def conn(self):return self.psycopg.connect(self.url)
    def _exec_script(self):
        schema="""
        CREATE TABLE IF NOT EXISTS visitor(id text PRIMARY KEY,n bigint NOT NULL);
        CREATE TABLE IF NOT EXISTS ip(ip text,day text,n bigint NOT NULL,PRIMARY KEY(ip,day));
        CREATE TABLE IF NOT EXISTS accounts(id text PRIMARY KEY,email text UNIQUE NOT NULL,name text NOT NULL,password text NOT NULL,verified boolean NOT NULL DEFAULT false,verify_code text,verify_until bigint,reset_code text,reset_until bigint,created_at bigint NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token text PRIMARY KEY,user_id text NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,expires_at bigint NOT NULL);
        """
        with self.conn() as c:c.execute(schema)
    @staticmethod
    def password(value):return hashlib.pbkdf2_hmac("sha256",value.encode(),b"tradeline-account-v1",300000).hex()
    def used(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        with self.conn() as c:
            a=c.execute("SELECT n FROM visitor WHERE id=%s",(vid,)).fetchone();b=c.execute("SELECT n FROM ip WHERE ip=%s AND day=%s",(ip,day)).fetchone()
        return (a[0] if a else 0,b[0] if b else 0)
    def bump(self,vid,ip):
        day=time.strftime("%Y-%m-%d",time.gmtime())
        with self.lock:
            with self.conn() as c:
                c.execute("INSERT INTO visitor(id,n) VALUES(%s,1) ON CONFLICT(id) DO UPDATE SET n=visitor.n+1",(vid,));c.execute("INSERT INTO ip(ip,day,n) VALUES(%s,%s,1) ON CONFLICT(ip,day) DO UPDATE SET n=ip.n+1",(ip,day))
    def register(self,name,email,password):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}";uid=secrets.token_urlsafe(18);now=int(time.time())
        try:
            with self.conn() as c:c.execute("INSERT INTO accounts(id,email,name,password,verified,verify_code,verify_until,created_at) VALUES(%s,%s,%s,%s,false,%s,%s,%s)",(uid,email,name,self.password(password),code,now+1800,now))
        except Exception as exc:
            if "unique" in str(exc).lower():raise ValueError("email_exists") from exc
            raise
        return uid,code
    def resend_verification(self,email):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}"
        with self.conn() as c:
            row=c.execute("SELECT id FROM accounts WHERE email=%s",(email,)).fetchone()
            if not row:return None
            c.execute("UPDATE accounts SET verify_code=%s,verify_until=%s WHERE email=%s",(code,int(time.time())+1800,email))
        return code
    def verify(self,email,code):
        email=email.lower().strip()
        with self.conn() as c:
            row=c.execute("SELECT id,verify_code,verify_until FROM accounts WHERE email=%s",(email,)).fetchone()
            if not row or row[1]!=code or int(time.time())>row[2]:return False
            c.execute("UPDATE accounts SET verified=true,verify_code=NULL,verify_until=NULL WHERE id=%s",(row[0],))
        return True
    def login(self,email,password):
        email=email.lower().strip()
        with self.conn() as c:
            row=c.execute("SELECT id,verified,password FROM accounts WHERE email=%s",(email,)).fetchone()
            if not row:return None,"invalid"
            if not row[1]:return None,"unverified"
            if not secrets.compare_digest(row[2],self.password(password)):return None,"invalid"
            token=secrets.token_urlsafe(32);expires=int(time.time())+30*86400;c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(%s,%s,%s)",(token,row[0],expires))
        return token,None
    def account(self,token):
        with self.conn() as c:row=c.execute("SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=%s AND s.expires_at>%s",(token,int(time.time()))).fetchone()
        return {"id":row[0],"email":row[1],"name":row[2],"verified":bool(row[3])} if row else None
    def logout(self,token):
        with self.conn() as c:c.execute("DELETE FROM sessions WHERE token=%s",(token,))
    def begin_reset(self,email):
        email=email.lower().strip();code=f"{secrets.randbelow(1000000):06d}"
        with self.conn() as c:
            row=c.execute("SELECT id FROM accounts WHERE email=%s",(email,)).fetchone()
            if not row:return None
            c.execute("UPDATE accounts SET reset_code=%s,reset_until=%s WHERE email=%s",(code,int(time.time())+1800,email))
        return code
    def reset_password(self,email,code,password):
        email=email.lower().strip()
        with self.conn() as c:
            row=c.execute("SELECT id,reset_code,reset_until FROM accounts WHERE email=%s",(email,)).fetchone()
            if not row or row[1]!=code or int(time.time())>row[2]:return False
            c.execute("UPDATE accounts SET password=%s,reset_code=NULL,reset_until=NULL,verified=true WHERE id=%s",(self.password(password),row[0]));c.execute("DELETE FROM sessions WHERE user_id=%s",(row[0],))
        return True


def send_email(c,to,subject,text):
    if c["resend_api_key"]:
        if not c["email_from"]:raise RuntimeError("email_not_configured")
        body=json.dumps({"from":c["email_from"],"to":[to],"subject":subject,"text":text}).encode();req=urllib.request.Request("https://api.resend.com/emails",data=body,method="POST",headers={"Authorization":"Bearer "+c["resend_api_key"],"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=20) as r:
            if r.status>=300:raise RuntimeError("email_provider_error")
        return
    if not c["smtp_host"] or not c["smtp_user"] or not c["smtp_pass"] or not c["smtp_from"]:raise RuntimeError("email_not_configured")
    import smtplib
    from email.message import EmailMessage
    msg=EmailMessage();msg["Subject"]=subject;msg["From"]=c["smtp_from"];msg["To"]=to;msg.set_content(text)
    with smtplib.SMTP(c["smtp_host"],c["smtp_port"],timeout=20) as smtp:smtp.starttls();smtp.login(c["smtp_user"],c["smtp_pass"]);smtp.send_message(msg)


def call_model(c,messages):
    contents=[]
    if messages:
        contents.append({"role":"user","parts":[{"text":"SYSTEM INSTRUCTIONS:\n"+SYSTEM}]})
    for message in messages:
        role="model" if message["role"]=="assistant" else "user"
        contents.append({"role":role,"parts":[{"text":message["content"]}]})
    body=json.dumps({"contents":contents,"generationConfig":{"temperature":0.2,"maxOutputTokens":c["max_tokens"]}}).encode()
    model=urllib.parse.quote(c["model"],safe="")
    url=c["upstream"].rstrip("/")+"/"+model+":generateContent"
    req=urllib.request.Request(url,data=body,method="POST",headers={"content-type":"application/json","x-goog-api-key":c["key"]})
    with urllib.request.urlopen(req,timeout=60) as r:payload=json.loads(r.read())
    texts=[]
    for candidate in payload.get("candidates",[]):
        for part in candidate.get("content",{}).get("parts",[]):
            if isinstance(part.get("text"),str):texts.append(part["text"])
    return "".join(texts).strip()


def make_handler(c,store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send_json(self,code,payload):
            data=json.dumps(payload).encode();self.send_response(code);origin=self.headers.get("Origin","");allowed=origin if origin in c["origins"] else ""
            if allowed:self.send_header("Access-Control-Allow-Origin",allowed)
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
            if self.path=="/health":return self.send_json(200,{"ok":True,"database":"postgresql" if c["database_url"] else "sqlite","ai":bool(c["key"]),"email":bool(c["resend_api_key"] or c["smtp_host"]),"provider":"gemini" if c["key"] else "none"})
            if self.path=="/api/account":
                account=store.account(self.token());return self.send_json(200,account) if account else self.send_json(401,{"error":"unauthorized"})
            self.send_json(404,{"error":"not_found"})
        def do_POST(self):
            try:body=self.body()
            except Exception:return self.send_json(400,{"error":"bad_request"})
            if self.path=="/api/auth/register":
                name=str(body.get("name","")).strip();email=str(body.get("email","")).strip().lower();password=str(body.get("password",""))
                if len(name)<2 or not EMAIL.match(email) or len(password)<8:return self.send_json(400,{"error":"bad_request"})
                try:_,code=store.register(name,email,password)
                except ValueError:return self.send_json(409,{"error":"email_exists"})
                try:send_email(c,email,"Confirm your TRADELINE account",f"Hello {name},\n\nYour TRADELINE verification code is: {code}\n\nThe code expires in 30 minutes.")
                except Exception:return self.send_json(503,{"error":"email_not_configured"})
                return self.send_json(201,{"ok":True,"email":email})
            if self.path=="/api/auth/resend":
                email=str(body.get("email","")).strip().lower();code=store.resend_verification(email)
                if code:
                    try:send_email(c,email,"Your TRADELINE verification code",f"Your verification code is: {code}\nThe code expires in 30 minutes.")
                    except Exception:return self.send_json(503,{"error":"email_not_configured"})
                return self.send_json(200,{"ok":True})
            if self.path=="/api/auth/verify":
                if not store.verify(str(body.get("email","")),str(body.get("code",""))):return self.send_json(400,{"error":"invalid_or_expired"})
                return self.send_json(200,{"ok":True,"verified":True})
            if self.path=="/api/auth/login":
                token,error=store.login(str(body.get("email","")),str(body.get("password","")))
                if error=="unverified":return self.send_json(403,{"error":"unverified"})
                if not token:return self.send_json(401,{"error":"invalid_credentials"})
                return self.send_json(200,{"ok":True,"token":token,"account":store.account(token)})
            if self.path=="/api/auth/logout":store.logout(self.token());return self.send_json(200,{"ok":True})
            if self.path=="/api/auth/forgot":
                email=str(body.get("email","")).strip().lower();code=store.begin_reset(email)
                if code:
                    try:send_email(c,email,"Reset your TRADELINE password",f"Your password-reset code is: {code}\nThe code expires in 30 minutes.")
                    except Exception:return self.send_json(503,{"error":"email_not_configured"})
                return self.send_json(200,{"ok":True})
            if self.path=="/api/auth/reset":
                email=str(body.get("email","")).strip().lower();password=str(body.get("password",""))
                if len(password)<8:return self.send_json(400,{"error":"bad_password"})
                if not store.reset_password(email,str(body.get("code","")),password):return self.send_json(200,{"ok":True})
                return self.send_json(400,{"error":"invalid_or_expired"})
            if self.path=="/api/chat":
                messages=body.get("messages",[]);visitor=str(body.get("visitor",""));email=str(body.get("email","")).strip().lower()
                valid=isinstance(messages,list) and 1<=len(messages)<=12 and messages[0].get("role")=="user" and messages[-1].get("role")=="user" and VID.match(visitor) and all(m.get("role") in ("user","assistant") and isinstance(m.get("content"),str) and 0<len(m["content"])<=2000 for m in messages)
                if not valid:return self.send_json(400,{"error":"bad_request"})
                if not c["key"]:return self.send_json(503,{"error":"not_configured"})
                ip=self.headers.get("X-Forwarded-For","").split(',')[0].strip() or self.client_address[0];paid=email in c["paid"];used,ipn=store.used(visitor,ip)
                if not paid and (used>=c["free"] or ipn>=c["ip_daily"]):return self.send_json(429,{"error":"limit"})
                try:reply=call_model(c,[{"role":m["role"],"content":m["content"]} for m in messages])
                except (urllib.error.URLError,TimeoutError,ValueError,OSError):return self.send_json(502,{"error":"upstream"})
                if not reply:return self.send_json(502,{"error":"empty"})
                if not paid:store.bump(visitor,ip);used+=1
                return self.send_json(200,{"reply":reply,"left":None if paid else max(0,c["free"]-used)})
            self.send_json(404,{"error":"not_found"})
    return Handler


def make_server(c=None,host="0.0.0.0"):
    c=c or cfg();store=PostgresStore(c["database_url"]) if c["database_url"] else SqliteStore(c["db"])
    return ThreadingHTTPServer((host,c["port"]),make_handler(c,store))


if __name__=="__main__":
    s=make_server();print("TRADELINE API listening on",s.server_address);s.serve_forever()
