"""FR-7/FR-9: single-admin local web console and approved-only feed.
No external reference code used. Standard library implementation.
"""
from contextlib import closing
import hmac
import html
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .console_ui import render_console, STYLE
from .dev_tools import DevTools
from . import notifications
from .feed_ui import feed_body, mock_body
from .source_config import configure_source, find_source, identity
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

def card(p,csrf=None,show_origin=True,return_view="pending"):
    status=p.get('editorial_status','approved' if not csrf else 'pending')
    label='PUBLISHED' if status=='approved' else 'REJECTED' if status=='rejected' else 'NEEDS REVIEW'
    body='<article data-platform="'+esc(p['platform'])+'" data-post-id="'+esc(p['post_id'])+'"><span class="post-status badge '+('good' if status=='approved' else 'bad' if status=='rejected' else 'warn')+'">'+label+'</span><small>'+(esc(p['platform'])+' · '+esc(p['account_id'])+' · ' if show_origin else '')+esc(p['created_at'] or 'Time unavailable')+'</small>'
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
        body+='<details class="source-details"><summary>Source details</summary><small>Post ID: '+esc(p['post_id'])+'<br>Source URL: '+esc(p['post_url'])+('<br>Internal duplicate key: '+esc(p['group']) if p['group'] else '')+'</small></details>'
        if p.get('editorial_reason')=='duplicate_not_selected':body+='<p><small>Reason: duplicate_not_selected</small></p>'
        actions=['reject']
        if p['candidate_status']=='candidate': actions.insert(0,'approve')
        if p['editorial_status']=='approved': actions=['withdraw','reject','unpin' if p['pinned'] else 'pin']
        for action in actions:
            label='Select & approve' if action=='approve' and p['group'] else action.capitalize()
            body+='<form method="post" action="/action">'
            for name,value in [('csrf',csrf),('platform',p['platform']),('post_id',p['post_id']),('action',action),('return_view',return_view)]:
                body+='<input type="hidden" name="'+name+'" value="'+esc(value)+'">'
            body+='<button>'+label+'</button></form>'
    if csrf and p['platform']=='manual':
        body+='<details><summary>Edit announcement</summary><form method="post" action="/edit"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="post_id" value="'+esc(p['post_id'])+'"><textarea name="text" maxlength="10000" required>'+esc(p['text'])+'</textarea><button>Save edit (requires review)</button></form></details>'
    return body+'</article>'

def make_server(db,password,host='127.0.0.1',port=5000,runtime=None,dev_enabled=False):
    sessions={}; attempts={}
    cookie_secure='; Secure' if os.environ.get('ASAP_COOKIE_SECURE')=='1' else ''
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
                    cookie_name+'='+token+cookie_secure+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=600')
            if route=='/embed-demo':
                return self.send(200,page('Mock MSRG Website',mock_body()))
            if route=='/feed':
                with closing(self.db_connection()) as conn:
                    posts=publishable(conn); settings=presentation(conn)
                return self.send(200,page('MSRG / ASAP Feed',feed_body(posts,settings,esc,safe_url),settings))
            session=self.session()
            if not session or not session['authenticated']: return self.redirect('/login')
            if route!='/admin': return self.send(404,page('Not found',''))
            query=parse_qs(parsed.query)
            view=query.get('view',['dashboard'])[0]
            if view=='duplicates':return self.redirect('/admin?view=pending&filters_set=1&duplicates=1')
            with closing(self.db_connection()) as conn:
                posts=items(conn)
                settings=presentation(conn)
                notification_config=notifications.settings(conn)
                notification_state=notifications.summary(conn)
                conn.commit()
                history=conn.execute('SELECT action,platform,post_id,actor,acted_at FROM editorial_actions ORDER BY id DESC LIMIT 20').fetchall()
            body=render_console(posts,history,settings,read_config(),session,view,esc,card,runtime,devtools,
                query.get('notice',[''])[0],query=query,notification_config=notification_config,notification_state=notification_state)
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
                return self.redirect('/admin',cookie_name+'='+token+cookie_secure+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if not session['authenticated']:return self.send(403,page('Sign in required',''))
            if route=='/logout':
                session['expires']=0
                return self.redirect('/login',cookie_name+'='+cookie_secure+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if route in ('/fetch','/source-toggle','/dev-task'):
                try:
                    if route=='/dev-task':
                        if not devtools or not devtools.enabled:raise ValueError('Development tools are disabled')
                        devtools.submit(value('test_id'),value('text'))
                        return self.redirect('/admin?view=testing')
                    if not runtime:raise ValueError('Polling runtime is not active in this server')
                    key=value('source_key') or value('platform')
                    if route=='/fetch':runtime.request_fetch(key)
                    else:
                        config=runtime.read_config()
                        source=find_source(config,key)
                        if source is None and key in ('x','bluesky'):
                            matches=[s for s in config['sources'] if s['platform']==key]
                            source=matches[0] if len(matches)==1 else None
                        if source and source['platform']=='linkedin':raise ValueError('LinkedIn API access pending')
                        if source is None:raise ValueError('Source not configured')
                        source['enabled']=not source.get('enabled',False)
                        source['interval_seconds']=source.get('interval_seconds') or 1800
                        runtime.save_config(config)
                    return self.redirect('/admin?view=sources')
                except ValueError as exc:return self.send(400,page('Operation unavailable',esc(exc)))
            if route=='/source-save':
                try:
                    config=read_config()
                    configure_source(config,{k:value(k) for k in ('provider','account','interval_seconds','enabled','page_size')},value('source_key') or None)
                    if not runtime:raise ValueError('Source management requires the app polling runtime')
                    runtime.save_config(config)
                except ValueError as exc:return self.send(400,page('Invalid source configuration',esc(exc)))
                return self.redirect('/admin?view=sources')
            if route=='/sources':
                try:
                    config=read_config()
                    if any(sum(s['platform']==platform for s in config['sources'])>1 for platform in ('x','bluesky')):raise ValueError('Use per-source editing when multiple accounts are configured')
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
            if route=='/notifications':
                try:
                    with closing(self.db_connection()) as conn:
                        notifications.save_settings(conn,bool(value('enabled')),value('channel'),value('recipient'))
                except ValueError as exc:return self.send(400,page('Invalid notification settings',esc(exc)))
                if runtime:runtime.wake.set()
                return self.redirect('/admin?view=settings')
            if route=='/order':return self.send(410,page('Manual order removed','Use Pin and newest-first ordering.'))
            if route in ('/edit','/presentation'):
                try:
                    with closing(self.db_connection()) as conn:
                        if route=='/edit':edit_announcement(conn,value('post_id'),value('text'))
                        elif route=='/order':set_order(conn,value('platform'),value('post_id'),value('position'))
                        else:save_presentation(conn,value('accent'),value('font_size'),bool(value('show_origin')))
                except ValueError as exc:return self.send(400,page('Invalid change',esc(exc)))
                return self.redirect('/admin?view=settings' if route=='/presentation' else '/admin?view=pending')
            if route=='/announcement':
                try:
                    with closing(self.db_connection()) as conn:create_announcement(conn,value('text'))
                except ValueError as exc:return self.send(400,page('Invalid announcement',esc(exc)))
                return self.redirect('/admin')
            if route!='/action':return self.send(404,page('Not found',''))
            try:
                with closing(self.db_connection()) as conn:decide(conn,value('platform'),value('post_id'),value('action'))
            except ValueError as exc:return self.send(400,page('Action unavailable',esc(exc)))
            destination=value('return_view') if value('action') in ('pin','unpin') else 'pending'
            if destination not in ('approved','pending','rejected'):destination='approved'
            self.redirect('/admin?view='+destination)
    server=ThreadingHTTPServer((host,port),Handler)
    cookie_name="asap_session_"+str(server.server_port)
    server.runtime=runtime;server.devtools=devtools
    return server
