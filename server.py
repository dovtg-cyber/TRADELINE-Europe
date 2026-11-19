#!/usr/bin/env python3
"""TRADELINE server: real Claude chat plus account verification and password login.

No API keys or SMTP passwords are stored in this file. Configure environment variables in Render.
"""
from __future__ import annotations
import hashlib, json, os, re, secrets, sqlite3, smtplib, threading, time, urllib.error, urllib.request
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VID=re.compile(r"^[a-z0-9]{8,64}$")


def cfg():
    e=os.environ.get
    return {
        "port":int(e("PORT","8080")),"key":e("ANTHROPIC_API_KEY",""),
        "upstream":e("UPSTREAM_URL","https://api.anthropic.com/v1/messages"),
        "model":e("CLAUDE_MODEL","claude-sonnet-4-5"),"free":int(e("FREE_LIMIT","5")),
        "ip_daily":int(e("IP_DAILY_LIMIT","25")),"db":e("DB_PATH","usage.db"),
        "max_tokens":int(e("MAX_TOKENS","600")),"paid":{x.strip().lower() for x in e("PAID_EMAILS","").split(',') if x.strip()},
        "origins":[x.strip() for x in e("ALLOWED_ORIGINS","*").split(',') if x.strip()],
        "smtp_host":e("SMTP_HOST",""),"smtp_port":int(e("SMTP_PORT","587")),"smtp_user":e("SMTP_USER",""),
        "smtp_pass":e("SMTP_PASS",""),"smtp_from":e("SMTP_FROM",e("SMTP_USER","")),"public_url":e("PUBLIC_URL",""),
    }

SYSTEM=("You are TRADELINE Legal Intelligence for TRADELINE EUROPE in Warsaw. Answer in the user's language. "
"Evidence first: never invent laws, articles, rates or links. Prefer official links to EUR-Lex, EU legislation, "
"TARIC, ISAP/Dziennik Ustaw and Polish tax/customs authorities. If a source matters and cannot be verified, say that plainly.
"
"If the answer uses a source, provide the complete clickable https:// URL. Separate mandatory rules from recommendations, "
"ask at most three missing questions for country, date, goods, origin and party role, and recommend a qualified specialist for binding conclusions.")

class Store:
    def __init__(self,path):
        self.lock=threading.Lock();self.c=sqlite3.connect(path,check_same_thread=False)
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS visitor(id TEXT PRIMARY KEY,n INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS ip(ip TEXT,day TEXT,n INTEGER NOT NULL,PRIMARY KEY(ip,day));
        CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,verify_code TEXT,verify_until INTEGER,reset_code TEXT,reset_until INTEGER,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires_at INTEGER NOT NULL);
        """);self.c.commit()
    def used(self,vid,ip):
        day=time.strftime('%Y-%m-%d',time.gmtime())
        with self.lock:
            a=self.c.execute('SELECT n FROM visitor WHERE id=?',(vid,)).fetchone();b=self.c.execute('SELECT n FROM ip WHERE ip=? AND day=?',(ip,day)).fetchone()
        return (a[0] if a else 0,b[0] if b else 0)
    def bump(self,vid,ip):
        day=time.strftime('%Y-%m-%d',time.gmtime())
        with self.lock:
            self.c.execute('INSERT INTO visitor(id,n) VALUES(?,1) ON CONFLICT(id) DO UPDATE SET n=n+1',(vid,));self.c.execute('INSERT INTO ip(ip,day,n) VALUES(?,?,1) ON CONFLICT(ip,day) DO UPDATE SET n=n+1',(ip,day));self.c.commit()
    def password(self,value):return hashlib.sha256(('TL2:'+value).encode()).hexdigest()
    def register(self,name,email,password):
        email=email.lower().strip();code=f'{secrets.randbelow(1000000):06d}';row=(secrets.token_urlsafe(18),email,name,self.password(password),0,code,int(time.time())+30*60,int(time.time()))
        with self.lock:
            try:self.c.execute('INSERT INTO accounts(id,email,name,password,verified,verify_code,verify_until,created_at) VALUES(?,?,?,?,?,?,?,?,)' if False else 'INSERT INTO accounts(id,email,name,password,verified,verify_code,verify_until,created_at) VALUES(?,?,?,?,?,?,?,?,)',row)
            except Exception as e:
                if 'UNIQUE' in str(e):raise ValueError('email_exists')
                raise
            self.c.commit()
        return row[0],code
    def verify(self,email,code):
        email=email.lower().strip()
        with self.lock:
            r=self.c.execute('SELECT id,verify_code,verify_until FROM accounts WHERE email=?',(email,)).fetchone()
            if not r or r[1]!=code or int(time.time())>r[2]:return False
            self.c.execute('UPDATE accounts SET verified=1,verify_code=NULL,verify_until=NULL WHERE id=?',(r[0],));self.c.commit();return True
    def login(self,email,password):
        email=email.lower().strip()
        r=self.c.execute('SELECT id,verified FROM accounts WHERE email=? AND password=?',(email,self.password(password))).fetchone()
        if not r:return None,'invalid';if not r[1]:return None,'unverified'
        token=secrets.token_urlsafe(32);exp=int(time.time())+30*86400
        with self.lock:self.c.execute('INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)',(token,r[0],exp));self.c.commit()
        return token,None
    def account(self,token):
        r=self.c.execute('SELECT a.id,a.email,a.name,a.verified FROM accounts a JOIN sessions s ON s.user_id=a.id WHERE s.token=? AND s.expires_at>?',(token,int(time.time()))).fetchone()
        return {'id':r[0],'email':r[1],'name':r[2],'verified':bool(r[3])} if r else None

def send_mail(c,to,subject,text):
    if not c['smtp_host'] or not c['smtp_user'] or not c['smtp_pass'] or not c['smtp_from']:
        raise RuntimeError('smtp_not_configured')
    m=EmailMessage();m['Subject']=subject;m['From']=c['smtp_from'];m['To']=to;m.set_content(text)
    with smtplib.SMTP(c['smtp_host'],c['smtp_port'],timeout=20) as s:
        s.starttls();s.login(c['smtp_user'],c['smtp_pass']);s.send_message(m)

def call_model(c,messages):
    body=json.dumps({'model':c['model'],'max_tokens':c['max_tokens'],'system':SYSTEM,'messages':messages}).encode()
    req=urllib.request.Request(c['upstream'],data=body,method='POST',headers={'content-type':'application/json','x-api-key':c['key'],'anthropic-version':'2023-06-01'})
    with urllib.request.urlopen(req,timeout=60) as r:j=json.loads(r.read())
    return ''.join(b.get('text','') for b in j.get('content',[]) if b.get('type')=='text').strip()

def make_handler(c,store):
    class H(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def send_json(self,code,obj):
            data=json.dumps(obj).encode();self.send_response(code);origin=self.headers.get('Origin','');allow=origin if origin and ('*' in c['origins'] or origin in c['origins']) else ('*' if '*' in c['origins'] else '')
            if allow:self.send_header('Access-Control-Allow-Origin',allow)
            self.send_header('Vary','Origin');self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def do_OPTIONS(self):
            self.send_response(204);origin=self.headers.get('Origin','')
            if origin and ('*' in c['origins'] or origin in c['origins']):self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Access-Control-Allow-Methods','POST, GET, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization');self.end_headers()
        def body(self):
            n=int(self.headers.get('Content-Length','0'))
            if n<=0 or n>40000:return None
            return json.loads(self.rfile.read(n))
        def do_GET(self):
            if self.path=='/health':return self.send_json(200,{'ok':True})
            if self.path=='/api/account':
                auth=self.headers.get('Authorization','');token=auth[7:] if auth.startswith('Bearer ') else '';u=store.account(token)
                return self.send_json(200,u) if u else self.send_json(401,{'error':'unauthorized'})
            self.send_json(404,{'error':'not_found'})
        def do_POST(self):
            try:d=self.body()
            except Exception:return self.send_json(400,{'error':'bad_request'})
            if d is None:return self.send_json(400,{'error':'bad_request'})
            if self.path=='/api/auth/register':
                name=str(d.get('name','')).strip();email=str(d.get('email','')).strip().lower();password=str(d.get('password',''))
                if len(name)<2 or not EMAIL.match(email) or len(password)<8:return self.send_json(400,{'error':'bad_request'})
                try:user_id,code=store.register(name,email,password)
                except ValueError:return self.send_json(409,{'error':'email_exists'})
                try:send_mail(c,email,'Confirm your TRADELINE account',f'Hello {name},\n\nYour TRADELINE verification code is: {code}\n\nThe code expires in 30 minutes.\n')
                except Exception:return self.send_json(503,{'error':'smtp_not_configured'})
                return self.send_json(201,{'ok':True,'email':email})
            if self.path=='/api/auth/verify':
                email=str(d.get('email',''));code=str(d.get('code',''))
                if not store.verify(email,code):return self.send_json(400,{'error':'invalid_or_expired'})
                token,_=store.login(email,str(d.get('password','')))
                if token:return self.send_json(200,{'ok':True,'token':token})
                return self.send_json(200,{'ok':True,'verified':True})
            if self.path=='/api/auth/login':
                token,error=store.login(str(d.get('email','')),str(d.get('password','')))
                if error=='unverified':return self.send_json(403,{'error':'unverified'})
                if not token:return self.send_json(401,{'error':'invalid_credentials'})
                return self.send_json(200,{'ok':True,'token':token,'account':store.account(token)})
            if self.path=='/api/chat':
                msgs=d.get('messages',[]);vid=str(d.get('visitor',''));email=str(d.get('email','')).strip().lower()
                ok=isinstance(msgs,list) and 1<=len(msgs)<=12 and msgs[0].get('role')=='user' and msgs[-1].get('role')=='user' and VID.match(vid) and all(m.get('role') in ('user','assistant') and isinstance(m.get('content'),str) and 0<len(m['content'])<=2000 for m in msgs)
                if not ok:return self.send_json(400,{'error':'bad_request'})
                if not c['key']:return self.send_json(503,{'error':'not_configured'})
                ip=self.headers.get('X-Forwarded-For','').split(',')[0].strip() or self.client_address[0];paid=email in c['paid'];used,ipn=store.used(vid,ip)
                if not paid and (used>=c['free'] or ipn>=c['ip_daily']):return self.send_json(429,{'error':'limit'})
                try:reply=call_model(c,[{'role':m['role'],'content':m['content']} for m in msgs])
                except (urllib.error.URLError,TimeoutError,ValueError,OSError):return self.send_json(502,{'error':'upstream'})
                if not reply:return self.send_json(502,{'error':'empty'})
                if not paid:store.bump(vid,ip);used+=1
                return self.send_json(200,{'reply':reply,'left':None if paid else max(0,c['free']-used)})
            self.send_json(404,{'error':'not_found'})
    return H

def make_server(c=None,host='0.0.0.0'):
    c=c or cfg();return ThreadingHTTPServer((host,c['port']),make_handler(c,Store(c['db'])))

if __name__=='__main__':
    s=make_server();print('TRADELINE server listening on',s.server_address);s.serve_forever()
