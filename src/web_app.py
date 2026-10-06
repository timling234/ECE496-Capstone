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
from .console_ui import render_console, STYLE
from .dev_tools import DevTools
from .web_editorial import initialize, items, decide, publishable, create_announcement, edit_announcement, set_order, presentation, save_presentation

def esc(value): return html.escape(str(value or ''),quote=True)

def safe_url(value):
    parsed=urlparse(str(value or ''))
    return str(value) if parsed.scheme in ('http','https') and parsed.netloc else ''

def page(title,body,settings=None,console=False):
    settings=settings or dict(accent="#215e95",font_size=14 if console else 16)
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>'+esc(title)+'</title><style>body{font:16px system-ui;background:#f2f5f8;color:#172536;max-width:1000px;margin:30px auto;padding:0 20px}'
        'article,.panel{background:white;border:1px solid #d8e0e8;border-radius:12px;padding:20px;margin:16px 0}nav{display:flex;gap:16px;flex-wrap:wrap}'
        'button{padding:9px 15px;cursor:pointer;background:#215e95;color:white;border:0;border-radius:6px}input{padding:10px}form{display:inline-block;margin:6px}'
        '.content{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#536579}img{max-width:100%;max-height:300px;border-radius:8px}a{color:#215e95}'
        +(STYLE if console else '')+'body{font-size:'+str(settings['font_size'])+'px}a{color:'+settings['accent']+'}</style></head><body>'+('' if console else '<h1>'+esc(title)+'</h1>')+body+'</body></html>').encode()

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

def make_server(db,password,host='127.0.0.1',port=5000,runtime=None,dev_enabled=False):
    sessions={}; attempts={}
    cookie_name="asap_session_"+str(port)
    devtools=DevTools(runtime,enabled=dev_enabled) if runtime else None
    config_path=runtime.config_path if runtime else Path(db).parent/'polling.local.json'
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
            token=cookies.get(cookie_name); token=token.value if token else ''
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
                    cookie_name+'='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=600')
            if route=='/embed-demo':
                return self.send(200,page('Mock MSRG Website','<p>Standalone website embedding the ASAP feed:</p><iframe title="ASAP feed" src="/feed" style="width:100%;height:650px;border:0"></iframe>'))
            if route=='/feed':
                with closing(self.db_connection()) as conn:
                    posts=publishable(conn); settings=presentation(conn)
                return self.send(200,page('MSRG / ASAP Feed','<p>Research updates</p>'+(''.join(card(p,show_origin=settings['show_origin']) for p in posts) or '<div class="panel">No published updates yet.</div>'),settings))
            session=self.session()
            if not session or not session['authenticated']: return self.redirect('/login')
            if route!='/admin': return self.send(404,page('Not found',''))
            view=parse_qs(parsed.query).get('view',['dashboard'])[0]
            with closing(self.db_connection()) as conn:
                posts=items(conn)
                settings=presentation(conn)
                history=conn.execute('SELECT action,platform,post_id,actor,acted_at FROM editorial_actions ORDER BY id DESC LIMIT 20').fetchall()
            body=render_console(posts,history,settings,read_config(),session,view,esc,card,runtime,devtools,
                parse_qs(parsed.query).get('notice',[''])[0])
            self.send(200,page('ASAP Admin',body,console=True))
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
                return self.redirect('/admin',cookie_name+'='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if not session['authenticated']:return self.send(403,page('Sign in required',''))
            if route=='/logout':
                session['expires']=0
                return self.redirect('/login',cookie_name+'=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if route in ('/fetch','/source-toggle','/dev-task'):
                try:
                    if route=='/dev-task':
                        if not devtools or not devtools.enabled:raise ValueError('Development tools are disabled')
                        devtools.submit(value('test_id'),value('text'))
                        return self.redirect('/admin?view=testing')
                    if not runtime:raise ValueError('Polling runtime is not active in this server')
                    platform=value('platform')
                    if route=='/fetch':runtime.request_fetch(platform)
                    else:
                        config=runtime.read_config()
                        source=next((s for s in config['sources'] if s['platform']==platform and platform in ('x','bluesky')),None)
                        if source is None:raise ValueError('Source not configured')
                        source['enabled']=not source.get('enabled',False)
                        source['interval_seconds']=source.get('interval_seconds') or 1800
                        runtime.save_config(config)
                    return self.redirect('/admin?view=sources')
                except ValueError as exc:return self.send(400,page('Operation unavailable',esc(exc)))
            if route=='/sources':
                try:
                    config=read_config()
                    for source in config['sources']:
                        platform=source['platform']
                        if platform not in ('x','bluesky'):continue
                        account=value(platform+'_account').strip();enabled=bool(value(platform+'_enabled'))
                        interval=int(value(platform+'_interval')) if value(platform+'_interval') else 1800
                        if not account or (platform=='x' and not account.isdecimal()):raise ValueError('A valid source account is required')
                        if (interval is not None and interval<1) or (enabled and interval is None):raise ValueError('Enabled sources require a positive interval')
                        source.update(account=account,enabled=enabled,interval_seconds=interval)
                    if runtime:runtime.save_config(config)
                    else:
                        config_path.parent.mkdir(parents=True,exist_ok=True)
                        temporary=config_path.with_suffix('.json.tmp')
                        temporary.write_text(json.dumps(config,indent=2),encoding='utf-8');temporary.replace(config_path)
                except ValueError as exc:return self.send(400,page('Invalid source configuration',esc(exc)))
                return self.redirect('/admin?view=sources')
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
    server=ThreadingHTTPServer((host,port),Handler)
    cookie_name="asap_session_"+str(server.server_port)
    server.runtime=runtime;server.devtools=devtools
    return server
