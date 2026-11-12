"""FR-7/FR-9: editorial console and approved-only feed.
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
from .feed_ui import feed_body, mock_body, appearance_overrides
from .source_config import configure_source, find_source, identity, add_platform
from .source_connections import choices
from .linkedin import OAuth, Credentials
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
        +(STYLE if console else '')+'body{font-size:'+str(settings['font_size'])+'px}a{color:'+settings['accent']+'}</style></head><body>'+('' if console else '<h1>'+esc(title)+'</h1>')+body+('<script src="/console.js" defer></script>' if console else '')+'</body></html>').encode()

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
        review=p.get('ai_review')
        if review:
            if review['stale'] or review['status']=='stale':
                body+='<p><small>AI suggestion is outdated. Request a new review.</small></p>'
            elif review['status']=='complete':
                label={'approve':'Approve','reject':'Reject','needs_review':'Needs review'}.get(review['recommendation'],'Needs review')
                body+='<section class="ai-suggestion"><b>AI suggestion: '+esc(label)+'</b><p>'+esc(review['reason'])+'</p><small>AI analysis · '+esc(review['model'])+'</small></section>'
                if review.get('execution'):body+='<p><small>'+esc(review['execution'])+'</small></p>'
            elif review['status']=='error':body+='<p><small>'+esc(review['error'])+'</small></p>'
            else:body+='<p><small>AI review in progress…</small></p>'
        if p.get('ai_available'):
            running=review and review['status']=='running'
            body+='<form method="post" action="/llm/suggest"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="return_view" value="'+esc(return_view)+'"><input type="hidden" name="platform" value="'+esc(p['platform'])+'"><input type="hidden" name="post_id" value="'+esc(p['post_id'])+'"><button '+('disabled' if running else '')+'>AI review suggestion</button></form>'
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
        body+='<details><summary>Edit announcement</summary><form method="post" action="/edit"><input type="hidden" name="return_view" value="'+esc(return_view)+'"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="post_id" value="'+esc(p['post_id'])+'"><textarea name="text" maxlength="10000" required>'+esc(p['text'])+'</textarea><button>Save edit (requires review)</button></form></details>'
    return body+'</article>'

def make_handler(db,password,host='127.0.0.1',port=5000,runtime=None,dev_enabled=False,linkedin_oauth=None):
    sessions={}; attempts={}
    cookie_secure='; Secure' if os.environ.get('ASAP_COOKIE_SECURE')=='1' else ''
    cookie_name="asap_session_"+str(port)
    devtools=DevTools(runtime,enabled=dev_enabled) if runtime else None
    config_path=runtime.config_path if runtime else Path(db).parent/'polling.local.json'
    linkedin_oauth=linkedin_oauth or OAuth(Credentials(config_path.parent/'linkedin_credentials'))
    oauth_cookie='asap_linkedin_'+str(port)
    example=Path(__file__).resolve().parents[1]/'config'/'polling.example.json'
    def linkedin_choices(session):
        choice=session.get('linkedin_choice',{})
        csrf=esc(session['csrf'])
        body='<h1>Choose your LinkedIn Page</h1><p>Only Pages available to your authorized account can be connected. Pulling starts manually.</p>'
        if not choice.get('loaded'):
            return body+'<form method="post" action="/linkedin/pages"><input type="hidden" name="csrf" value="'+csrf+'"><button>Load my Pages</button></form>'
        for account,name in choice['pages'].items():
            body+='<form class="panel" method="post" action="/linkedin/select"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="organization" value="'+esc(account)+'"><b>'+esc(name)+'</b> · <a href="https://www.linkedin.com/company/'+esc(account)+'/" target="_blank" rel="noopener noreferrer">View Page</a> <button>Connect this Page</button></form>'
        if not choice['pages']:body+='<p>No eligible Pages found. Sign in with the account that administers the Page.</p>'
        if choice.get('more'):body+='<form method="post" action="/linkedin/pages"><input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="more" value="1"><button>Load more Pages</button></form>'
        return body+'<p><a href="/admin?view=sources">Back to Sources</a></p>'
    class Handler(BaseHTTPRequestHandler):
        def read_config(self):
            path=self.config_path if self.config_path.exists() else example
            return json.loads(path.read_text(encoding='utf-8'))
        def actor(self):
            session=self.session() or {}
            return session.get('user_id') or 'admin'
        def log_message(self,*args): pass # Never log credentials, cookies or post content.
        def send(self,status,body,cookie=None):
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src https: http:; form-action 'self' https://www.linkedin.com; base-uri 'none'; frame-src 'self'")
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
        def oauth_session_cookie(self, session):
            # Recover only the exact existing session bound to a verified OAuth
            # state + callback nonce. Keep the bearer and original expiry.
            for token, current in sessions.items():
                if current is session and current.get('authenticated') and current['expires']>time.time():
                    remaining=int(current['expires']-time.time())
                    return cookie_name+'='+token+cookie_secure+'; HttpOnly; SameSite=Lax; Path=/; Max-Age='+str(remaining)
            raise ValueError('Original administrator session expired')
        def db_connection(self): return sqlite3.connect(self.db,timeout=10)
        def do_GET(self):
            parsed=urlparse(self.path); route=parsed.path
            if route=='/linkedin/callback':
                # Separate Lax nonce cookie allows cross-site OAuth callback without
                # weakening the existing Strict administrator session cookie.
                values=parse_qs(parsed.query)
                cookies=SimpleCookie()
                try:cookies.load(self.headers.get('Cookie',''))
                except Exception:return self.send(400,page('LinkedIn connection failed','Start again from Sources.'))
                nonce=cookies.get(oauth_cookie)
                try:
                    if any(len(values.get(k,[]))!=1 for k in ('state',)) or len(values.get('code',[]))>1:
                        raise ValueError('Invalid LinkedIn callback')
                    linked_session=self.linkedin_oauth.finish(values['state'][0],nonce.value if nonce else '',
                        values.get('code',[''])[0],denied='error' in values)
                    body=linkedin_choices(linked_session)
                    return self.send(200,page('LinkedIn connected',body),oauth_cookie+'=; HttpOnly; SameSite=Lax; Path=/linkedin/callback; Max-Age=0'+cookie_secure)
                except Exception:
                    # Never show authorization codes, tokens, provider payloads or exceptions.
                    return self.send(400,page('LinkedIn connection failed','Permission was declined, the connection expired, or LinkedIn could not complete it. <a href="/admin?view=sources">Return to Sources and reconnect</a>.'))
            if route=='/': return self.redirect('/admin')
            if route=='/favicon.ico': return self.send(204,b'')
            if route not in ('/login','/admin','/feed','/embed-demo','/linkedin/choose'):return self.send(404,page('Not found',''))
            if route=='/login':
                token=secrets.token_urlsafe(32)
                sessions[token]={'csrf':secrets.token_urlsafe(32),'expires':time.time()+600,'authenticated':False}
                return self.send(200,page('Admin sign in','<form method="post" action="/login"><input type="hidden" name="csrf" value="'+sessions[token]['csrf']+'"><label>Password <input type="password" name="password" required autocomplete="current-password"></label><button>Sign in</button></form>'),
                    cookie_name+'='+token+cookie_secure+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=600')
            if route=='/embed-demo':
                return self.send(200,page('Mock Website',mock_body(parse_qs(parsed.query))))
            if route=='/feed':
                with closing(self.db_connection()) as conn:
                    posts=publishable(conn); settings=presentation(conn)
                settings.update(appearance_overrides(parse_qs(parsed.query)))
                return self.send(200,page('MSRG / ASAP Feed',feed_body(posts,settings,esc,safe_url),settings))
            session=self.session()
            if not session or not session['authenticated']: return self.redirect('/login')
            if route=='/linkedin/choose':
                return self.send(200,page('Choose LinkedIn Page',linkedin_choices(session)))
            if route!='/admin': return self.send(404,page('Not found',''))
            query=parse_qs(parsed.query)
            view=query.get('view',['dashboard'])[0]
            if view=='duplicates':return self.redirect('/admin?view=pending&filters_set=1&duplicates=1')
            with closing(self.db_connection()) as conn:
                posts=items(conn)
                from .review_ai import attach
                attach(conn,posts,enabled=getattr(self,'ai_ready',False),config=getattr(self,'ai_config',None))
                settings=presentation(conn)
                notification_config=notifications.settings(conn)
                notification_state=notifications.summary(conn)
                conn.commit()
                history=conn.execute('SELECT action,platform,post_id,actor,acted_at FROM editorial_actions ORDER BY id DESC LIMIT 20').fetchall()
            body=render_console(posts,history,settings,self.read_config(),session,view,esc,card,self.runtime,self.devtools,
                query.get('notice',[''])[0],query=query,ai_panel=getattr(self,'ai_panel',None),connection_choices=choices(self.read_config(),self.config_path.parent),notification_config=notification_config,notification_state=notification_state,feed_url=getattr(self,'feed_url',None))
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
            if route=='/linkedin/connect':
                if not self.runtime:return self.send(400,page('LinkedIn unavailable','The source runtime is required.'))
                try:url,nonce=self.linkedin_oauth.begin(session)
                except ValueError as error:return self.send(400,page('LinkedIn setup required',esc(error)))
                return self.redirect(url,oauth_cookie+'='+nonce+'; HttpOnly; SameSite=Lax; Path=/linkedin/callback; Max-Age=600'+cookie_secure)
            if route=='/linkedin/pages':
                try:self.linkedin_oauth.pages(session,more=value('more')=='1')
                except Exception:return self.send(400,page('LinkedIn Pages unavailable','No Page was added. <a href="/linkedin/choose">Try loading your Pages again</a>, or reconnect from Sources.'))
                return self.redirect('/linkedin/choose')
            if route=='/linkedin/select':
                try:
                    if not self.runtime:raise ValueError('The source runtime is required')
                    choice=session.get('linkedin_choice')
                    if not choice or choice['expires']<=time.time() or value('organization') not in choice['pages']:
                        raise ValueError('Choose a Page returned by your LinkedIn authorization')
                    with self.runtime.lock:
                        config=self.runtime.read_config()
                        account=value('organization')
                        source=find_source(config,'linkedin:'+account)
                        if source is None:
                            source=find_source(config,'linkedin:')
                        if source is None:
                            source=dict(platform='linkedin',account=account)
                            config['sources'].append(source)
                        source['account']=account
                        source.pop('draft',None)
                        source.update(connection_id=choice['connection'],label=choice['pages'][account],
                                      enabled=False,interval_seconds=1800,page_size=100)
                        config['sources']=[s for s in config['sources'] if not (s['platform']=='linkedin' and not s.get('account'))]
                        self.runtime.save_config(config)
                        session.pop('linkedin_choice',None)
                    return self.redirect('/admin?view=sources&notice=LinkedIn+Page+connected.+Use+Fetch+Now+when+ready.')
                except ValueError as error:return self.send(400,page('LinkedIn Page unavailable',esc(error)))
            if route=='/logout':
                session['expires']=0
                return self.redirect('/login',cookie_name+'='+cookie_secure+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if route in ('/fetch','/source-toggle','/dev-task'):
                try:
                    if route=='/dev-task':
                        if not self.devtools or not self.devtools.enabled:raise ValueError('Development tools are disabled')
                        self.devtools.submit(value('test_id'),value('text'))
                        return self.redirect('/admin?view=testing')
                    if not self.runtime:raise ValueError('Polling runtime is not active in this server')
                    key=value('source_key') or value('platform')
                    if route=='/fetch':self.runtime.request_fetch(key)
                    else:
                        config=self.runtime.read_config()
                        source=find_source(config,key)
                        if source is None and key in ('x','bluesky'):
                            matches=[s for s in config['sources'] if s['platform']==key]
                            source=matches[0] if len(matches)==1 else None
                        if source and source['platform']=='linkedin' and not source.get('connection_id'):raise ValueError('Connect LinkedIn first')
                        if source is None:raise ValueError('Source not configured')
                        source['enabled']=not source.get('enabled',False)
                        source['interval_seconds']=source.get('interval_seconds') or 1800
                        self.runtime.save_config(config)
                    return self.redirect('/admin?view=sources')
                except ValueError as exc:return self.send(400,page('Operation unavailable',esc(exc)))
            if route=='/source-add':
                try:
                    if not self.runtime:raise ValueError('Source runtime required')
                    with self.runtime.lock:
                        config=self.read_config()
                        add_platform(config,value('provider'))
                        self.runtime.save_config(config)
                    return self.redirect('/admin?view=sources')
                except ValueError as exc:return self.send(400,page('Cannot add source',esc(exc)))
            if route=='/source-remove':
                try:
                    if not self.runtime:raise ValueError('Source runtime required')
                    self.runtime.remove_source(value('source_key'))
                    return self.redirect('/admin?view=sources&notice=Source+removed.+Existing+posts+are+kept.')
                except ValueError as exc:return self.send(400,page('Cannot remove source',esc(exc)))
            if route=='/source-save':
                try:
                    if not self.runtime:raise ValueError('Source management requires the app polling runtime')
                    with self.runtime.lock:
                        config=self.read_config();key=value('source_key') or None
                        existing=find_source(config,key) if key else None
                        fields={k:value(k) for k in ('provider','account','interval_seconds','enabled','page_size','name')}
                        if key:
                            if existing is None:raise ValueError('Source not found')
                            if value('account') and value('account')!=existing.get('account',''):raise ValueError('Connected account cannot be changed')
                            fields['account']=existing.get('account','')
                        else:
                            selected=next((s for s in choices(config,self.config_path.parent) if s['platform']==value('provider') and s['connection_ref']==value('connection_ref')),None)
                            if not selected:raise ValueError('Authenticate an account from Sources first')
                            if find_source(config,identity(selected)):raise ValueError('This account is already in Sources; edit its settings instead')
                            existing={k:v for k,v in selected.items() if k!='connection_ref'}
                            config['sources'].append(existing);key=identity(existing)
                            fields['account']=existing.get('account','')
                        if 'name' not in data:fields['name']=existing.get('name',existing['platform'])
                        configure_source(config,fields,key)
                        self.runtime.save_config(config)
                except ValueError as exc:return self.send(400,page('Invalid source configuration',esc(exc)))
                return self.redirect('/admin?view=sources')
            if route=='/sources':
                try:
                    config=self.read_config()
                    if any(sum(s['platform']==platform for s in config['sources'])>1 for platform in ('x','bluesky')):raise ValueError('Use per-source editing when multiple accounts are configured')
                    for source in config['sources']:
                        platform=source['platform']
                        if platform not in ('x','bluesky'):continue
                        account=value(platform+'_account').strip();enabled=bool(value(platform+'_enabled'))
                        interval=int(value(platform+'_interval')) if value(platform+'_interval') else 1800
                        if not account or (platform=='x' and not account.isdecimal()):raise ValueError('A valid source account is required')
                        if (interval is not None and interval<1) or (enabled and interval is None):raise ValueError('Enabled sources require a positive interval')
                        source.update(account=account,enabled=enabled,interval_seconds=interval)
                    if self.runtime:self.runtime.save_config(config)
                    else:
                        self.config_path.parent.mkdir(parents=True,exist_ok=True)
                        temporary=self.config_path.with_suffix('.json.tmp')
                        temporary.write_text(json.dumps(config,indent=2),encoding='utf-8');temporary.replace(self.config_path)
                except ValueError as exc:return self.send(400,page('Invalid source configuration',esc(exc)))
                return self.redirect('/admin?view=sources')
            if route=='/notifications':
                try:
                    with closing(self.db_connection()) as conn:
                        notifications.save_settings(conn,bool(value('enabled')),value('channel'),value('recipient'))
                except ValueError as exc:return self.send(400,page('Invalid notification settings',esc(exc)))
                if self.runtime:self.runtime.wake.set()
                return self.redirect('/admin?view=settings')
            if route=='/order':return self.send(410,page('Manual order removed','Use Pin and newest-first ordering.'))
            if route in ('/edit','/presentation'):
                try:
                    with closing(self.db_connection()) as conn:
                        if route=='/edit':edit_announcement(conn,value('post_id'),value('text'),actor=self.actor())
                        elif route=='/order':set_order(conn,value('platform'),value('post_id'),value('position'))
                        else:save_presentation(conn,value('accent'),value('font_size'),bool(value('show_origin')))
                except ValueError as exc:return self.send(400,page('Invalid change',esc(exc)))
                destination=value('return_view') or 'pending'
                if destination not in ('approved','pending','rejected'):destination='pending'
                return self.redirect('/admin?view=settings' if route=='/presentation' else '/admin?view='+destination)
            if route=='/announcement':
                try:
                    with closing(self.db_connection()) as conn:create_announcement(conn,value('text'),actor=self.actor())
                except ValueError as exc:return self.send(400,page('Invalid announcement',esc(exc)))
                return self.redirect('/admin')
            if route!='/action':return self.send(404,page('Not found',''))
            try:
                with closing(self.db_connection()) as conn:decide(conn,value('platform'),value('post_id'),value('action'),actor=self.actor())
            except ValueError as exc:return self.send(400,page('Action unavailable',esc(exc)))
            destination=value('return_view') or 'pending'
            if destination not in ('approved','pending','rejected'):destination='approved'
            self.redirect('/admin?view='+destination)
    Handler.db=Path(db)
    Handler.config_path=config_path
    Handler.runtime=runtime
    Handler.devtools=devtools
    Handler.linkedin_oauth=linkedin_oauth
    def set_port(value):
        nonlocal cookie_name, oauth_cookie
        cookie_name='asap_session_'+str(value)
        oauth_cookie='asap_linkedin_'+str(value)
    Handler.set_port=staticmethod(set_port)
    return Handler


def make_server(db,password,host='127.0.0.1',port=5000,runtime=None,dev_enabled=False,linkedin_oauth=None):
    """Compatibility entry point for existing HTTP tests and local tools."""
    handler=make_handler(db,password,host,port,runtime,dev_enabled,linkedin_oauth)
    server=ThreadingHTTPServer((host,port),handler)
    handler.set_port(server.server_port)
    server.linkedin_oauth=handler.linkedin_oauth
    server.runtime=runtime;server.devtools=handler.devtools
    return server
