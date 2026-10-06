"""FR-7/FR-9: single-admin local web console and approved-only feed.
No external reference code used. Standard library implementation.
"""
from contextlib import closing
import hmac
import html
import json
import secrets
import sqlite3
import time
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .web_editorial import initialize, items, decide, publishable, create_announcement, edit_announcement, set_order, presentation, save_presentation

def esc(value): return html.escape(str(value or ''),quote=True)

def safe_url(value):
    parsed=urlparse(str(value or ''))
    return str(value) if parsed.scheme in ('http','https') and parsed.netloc else ''

def page(title,body,settings=None):
    settings=settings or dict(accent="#215e95",font_size=16)
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>'+esc(title)+'</title><style>body{font:16px system-ui;background:#f2f5f8;color:#172536;max-width:1000px;margin:30px auto;padding:0 20px}'
        'article,.panel{background:white;border:1px solid #d8e0e8;border-radius:12px;padding:20px;margin:16px 0}nav{display:flex;gap:16px;flex-wrap:wrap}'
        'button{padding:9px 15px;cursor:pointer;background:#215e95;color:white;border:0;border-radius:6px}input{padding:10px}form{display:inline-block;margin:6px}'
        '.content{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#536579}img{max-width:100%;max-height:300px;border-radius:8px}a{color:#215e95}'
        'body{font-size:'+str(settings['font_size'])+'px}a{color:'+settings['accent']+'}</style></head><body><h1>'+esc(title)+'</h1>'+body+'</body></html>').encode()

def card(p,csrf=None,show_origin=True):
    body='<article><small>'+(esc(p['platform'])+' · '+esc(p['account_id'])+' · ' if show_origin else '')+esc(p['created_at'] or 'Time unavailable')+'</small>'
    body+='<p class="content">'+esc(p['text'])+'</p>'
    url=safe_url(p['post_url'])
    if url: body+='<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">Original post</a>'
    for link in p['links']:
        url=safe_url(link)
        if url: body+='<p><a rel="noopener noreferrer" href="'+esc(url)+'">'+esc(url)+'</a></p>'
    for media in p['media']:
        url=safe_url(media.get('fullsize') or media.get('url') or media.get('preview_image_url'))
        if url: body+='<p><img loading="lazy" referrerpolicy="no-referrer" src="'+esc(url)+'" alt="'+esc(media.get('alt','Source media'))+'"></p>'
    if csrf:
        body+='<p>Review: '+esc(p['candidate_status'])+' · Editorial: <b>'+esc(p['editorial_status'])+'</b></p>'
        if p['group']: body+='<p><small>Duplicate group: '+esc(p['group'])+'</small></p>'
        actions=['reject']
        if p['candidate_status']=='candidate': actions.insert(0,'approve')
        if p['editorial_status']=='approved': actions=['withdraw','reject','unpin' if p['pinned'] else 'pin']
        for action in actions:
            label='Select & approve' if action=='approve' and p['group'] else action.capitalize()
            body+='<form method="post" action="/action">'
            for name,value in [('csrf',csrf),('platform',p['platform']),('post_id',p['post_id']),('action',action)]:
                body+='<input type="hidden" name="'+name+'" value="'+esc(value)+'">'
            body+='<button>'+label+'</button></form>'
    if csrf and p['editorial_status']=='approved':
        body+='<form method="post" action="/order"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="platform" value="'+esc(p['platform'])+'"><input type="hidden" name="post_id" value="'+esc(p['post_id'])+'"><label>Manual order (0 = default) <input type="number" name="position" min="0" max="100000" value="'+str(p['position'])+'"></label><button>Save order</button></form>'
    if csrf and p['platform']=='manual':
        body+='<details><summary>Edit announcement</summary><form method="post" action="/edit"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="post_id" value="'+esc(p['post_id'])+'"><textarea name="text" maxlength="10000" required>'+esc(p['text'])+'</textarea><button>Save edit (requires review)</button></form></details>'
    return body+'</article>'

def make_server(db,password,host='127.0.0.1',port=5000):
    sessions={}; attempts={}
    config_path=Path(db).parent/'polling.local.json'
    example=Path(__file__).resolve().parents[1]/'config'/'polling.example.json'
    def read_config():
        return json.loads((config_path if config_path.exists() else example).read_text(encoding='utf-8'))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass # Never log credentials, cookies or post content.
        def send(self,status,body,cookie=None):
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src https: http:; form-action 'self'; base-uri 'none'; frame-src 'self'")
            if urlparse(self.path).path!='/feed':self.send_header('X-Frame-Options','DENY')
            if cookie: self.send_header('Set-Cookie',cookie)
            self.end_headers(); self.wfile.write(body)
        def redirect(self,path,cookie=None):
            self.send_response(303); self.send_header('Location',path)
            if cookie:self.send_header('Set-Cookie',cookie)
            self.send_header('Cache-Control','no-store');self.end_headers()
        def session(self):
            cookies=SimpleCookie()
            try: cookies.load(self.headers.get('Cookie',''))
            except Exception: return None
            token=cookies.get('asap_session'); token=token.value if token else ''
            session=sessions.get(token)
            if session and session['expires']>time.time(): return session
            sessions.pop(token,None); return None
        def db_connection(self): return sqlite3.connect(db,timeout=10)
        def do_GET(self):
            parsed=urlparse(self.path); route=parsed.path
            if route=='/': return self.redirect('/admin')
            if route=='/favicon.ico': return self.send(204,b'')
            if route not in ('/login','/admin','/feed','/embed-demo'):return self.send(404,page('Not found',''))
            if route=='/login':
                token=secrets.token_urlsafe(32)
                sessions[token]={'csrf':secrets.token_urlsafe(32),'expires':time.time()+600,'authenticated':False}
                return self.send(200,page('Admin sign in','<form method="post" action="/login"><input type="hidden" name="csrf" value="'+sessions[token]['csrf']+'"><label>Password <input type="password" name="password" required autocomplete="current-password"></label><button>Sign in</button></form>'),
                    'asap_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=600')
            if route=='/embed-demo':
                return self.send(200,page('Mock MSRG Website','<p>Standalone website embedding the ASAP feed:</p><iframe title="ASAP feed" src="/feed" style="width:100%;height:650px;border:0"></iframe>'))
            if route=='/feed':
                with closing(self.db_connection()) as conn:
                    posts=publishable(conn); settings=presentation(conn)
                return self.send(200,page('MSRG / ASAP Feed','<p>Research updates</p>'+(''.join(card(p,show_origin=settings['show_origin']) for p in posts) or '<div class="panel">No published updates yet.</div>'),settings))
            session=self.session()
            if not session or not session['authenticated']: return self.redirect('/login')
            if route!='/admin': return self.send(404,page('Not found',''))
            view=parse_qs(parsed.query).get('view',['pending'])[0]
            with closing(self.db_connection()) as conn:
                posts=items(conn)
                settings=presentation(conn)
                history=conn.execute('SELECT action,platform,post_id,actor,acted_at FROM editorial_actions ORDER BY id DESC LIMIT 20').fetchall()
            nav='<nav>'+''.join('<a href="/admin?view='+v+'">'+label+'</a>' for v,label in [('pending','Pending / Needs Review'),('approved','Approved'),('rejected','Rejected'),('duplicates','Duplicate Groups')])+'<a href="/feed" target="_blank">Public feed ↗</a></nav>'
            nav+='<form method="post" action="/logout"><input type="hidden" name="csrf" value="'+session['csrf']+'"><button>Sign out</button></form>'
            chosen=[p for p in posts if (bool(p['group']) if view=='duplicates' else p['editorial_status']==view if view in ('approved','rejected') else p['editorial_status'] in ('pending','needs review'))]
            chosen.sort(key=lambda p:(p['group'] or '',p['created_at'] or '',p['post_id']),reverse=True)
            nav+='<details class="panel"><summary>Create announcement</summary><form method="post" action="/announcement"><input type="hidden" name="csrf" value="'+session['csrf']+'"><p><textarea name="text" rows="5" cols="45" maxlength="10000" required placeholder="Announcement text"></textarea></p><button>Create pending announcement</button></form></details>'
            nav+='<details class="panel"><summary>Feed appearance</summary><form method="post" action="/presentation"><input type="hidden" name="csrf" value="'+session['csrf']+'"><label>Link color <input type="color" name="accent" value="'+esc(settings['accent'])+'"></label><label>Font size <input name="font_size" type="number" min="12" max="24" value="'+str(settings['font_size'])+'"></label><label><input type="checkbox" name="show_origin" '+('checked' if settings['show_origin'] else '')+'>Show origin</label><button>Save appearance</button></form></details>'
            nav+='<details class="panel"><summary>Source configuration</summary><p>Saved settings apply when the polling worker restarts. Saving does not make API requests. LinkedIn API access pending.</p><form method="post" action="/sources"><input type="hidden" name="csrf" value="'+session['csrf']+'">'
            for source in read_config()['sources']:
                platform=source['platform']
                if platform not in ('x','bluesky'):continue
                nav+='<p><b>'+esc(platform)+'</b> <label>Account <input name="'+platform+'_account" value="'+esc(source.get('account'))+'" required></label><label>Interval seconds <input type="number" min="1" name="'+platform+'_interval" value="'+esc(source.get('interval_seconds'))+'"></label><label><input type="checkbox" name="'+platform+'_enabled" '+('checked' if source.get('enabled') else '')+'>Enabled</label></p>'
            nav+='<button>Save source settings</button></form></details>'
            body=nav+(''.join(card(p,session['csrf']) for p in chosen) or '<div class="panel">No posts in this view.</div>')
            body+='<details><summary>Recent editorial actions</summary>'+''.join('<p>'+esc(' · '.join(str(v) for v in row))+'</p>' for row in history)+'</details>'
            self.send(200,page('ASAP Admin',body))
        def do_POST(self):
            session=self.session()
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError: return self.send(400,page('Invalid request',''))
            if not 0<length<=16384:return self.send(400,page('Invalid request',''))
            data=parse_qs(self.rfile.read(length).decode('utf-8',errors='replace'))
            value=lambda k:data.get(k,[''])[0]
            if not session or not hmac.compare_digest(value('csrf'),session['csrf']):return self.send(403,page('Request expired','Refresh the page and try again.'))
            route=urlparse(self.path).path
            if route=='/login':
                now=time.time(); key=self.client_address[0]; recent=[t for t in attempts.get(key,[]) if now-t<60]
                if len(recent)>=5:return self.send(429,page('Please wait','Try again in one minute.'))
                attempts[key]=recent+[now]
                if not hmac.compare_digest(value('password').encode(),password.encode()):return self.send(403,page('Sign-in failed','<a href="/login">Try again</a>'))
                token=secrets.token_urlsafe(32)
                sessions[token]={'csrf':secrets.token_urlsafe(32),'expires':now+8*3600,'authenticated':True}
                session['expires']=0
                return self.redirect('/admin','asap_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if not session['authenticated']:return self.send(403,page('Sign in required',''))
            if route=='/logout':
                session['expires']=0
                return self.redirect('/login','asap_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if route=='/sources':
                try:
                    config=read_config()
                    for source in config['sources']:
                        platform=source['platform']
                        if platform not in ('x','bluesky'):continue
                        account=value(platform+'_account').strip();enabled=bool(value(platform+'_enabled'))
                        interval=int(value(platform+'_interval')) if value(platform+'_interval') else None
                        if not account or (platform=='x' and not account.isdecimal()):raise ValueError('A valid source account is required')
                        if (interval is not None and interval<1) or (enabled and interval is None):raise ValueError('Enabled sources require a positive interval')
                        source.update(account=account,enabled=enabled,interval_seconds=interval)
                    config_path.parent.mkdir(parents=True,exist_ok=True)
                    temporary=config_path.with_suffix('.json.tmp')
                    temporary.write_text(json.dumps(config,indent=2),encoding='utf-8');temporary.replace(config_path)
                except ValueError as exc:return self.send(400,page('Invalid source configuration',esc(exc)))
                return self.redirect('/admin')
            if route in ('/edit','/order','/presentation'):
                try:
                    with closing(self.db_connection()) as conn:
                        if route=='/edit':edit_announcement(conn,value('post_id'),value('text'))
                        elif route=='/order':set_order(conn,value('platform'),value('post_id'),value('position'))
                        else:save_presentation(conn,value('accent'),value('font_size'),bool(value('show_origin')))
                except ValueError as exc:return self.send(400,page('Invalid change',esc(exc)))
                return self.redirect('/admin')
            if route=='/announcement':
                try:
                    with closing(self.db_connection()) as conn:create_announcement(conn,value('text'))
                except ValueError as exc:return self.send(400,page('Invalid announcement',esc(exc)))
                return self.redirect('/admin')
            if route!='/action':return self.send(404,page('Not found',''))
            try:
                with closing(self.db_connection()) as conn:decide(conn,value('platform'),value('post_id'),value('action'))
            except ValueError as exc:return self.send(400,page('Action unavailable',esc(exc)))
            self.redirect('/admin')
    return ThreadingHTTPServer((host,port),Handler)
