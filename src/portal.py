"""Flask portal and authenticated workspace dispatch over the existing editorial core.

The adapter retains the proven editorial handlers without an internal HTTP proxy.
Every request receives its own handler and server-selected workspace dependencies.
"""
from contextlib import closing
import html
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlencode
from flask import Flask, Response, abort, g, redirect, request
from werkzeug.middleware.proxy_fix import ProxyFix
from .accounts import Accounts
from .google_login import GoogleLogin
from .linkedin import Credentials, OAuth
from .web_app import make_handler, page, esc
from .workspaces import Workspace, Workspaces
from .portal_ui import auth_page, home_page
from .social_oauth import SocialOAuth
from .review_ai import Reviewer

COOKIE = 'asap_portal'


def create_app(db, password, runtime=None, *, start_workers=False, google=None, secure=None, trust_proxy=False):
    db = Path(db)
    app = Flask(__name__, static_folder=str(Path(__file__).parent/'static'), static_url_path='/assets')
    app.config.update(MAX_CONTENT_LENGTH=16384)
    if trust_proxy:
        # Only enable behind exactly one trusted reverse proxy (Caddy).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    secure = os.environ.get('ASAP_COOKIE_SECURE') == '1' if secure is None else secure
    accounts = Accounts(db.parent / 'accounts.sqlite3')
    google = google or GoogleLogin()
    default = Workspace(db, runtime, OAuth(Credentials(db.parent / 'linkedin_credentials')))
    workspaces = Workspaces(db.parent / 'workspaces', accounts, default, start_workers)
    handler_class = make_handler(db, password, port=5000, runtime=runtime, linkedin_oauth=default.oauth)
    social = SocialOAuth()
    reviewer = Reviewer()
    legacy_sessions = {}
    cache_lock = threading.RLock()
    app.extensions.update(accounts=accounts, workspaces=workspaces, google=google, social=social,reviewer=reviewer)
    if start_workers:
        workspaces.restore()

    for workspace in [default]+[workspaces.get(uid) for uid in accounts.ids()]:
        reviewer.recover(workspace.db)

    def document(title, body, status=200):
        nav = '<nav><a href="/">ASAP</a>'
        nav += '<a href="/app">My workspace</a><a href="/account">Account</a>' if g.get('user') else '<a href="/signin">Sign in</a><a href="/register">Create account</a>'
        nav += '</nav>'
        return Response(page(title, nav + body), status=status, content_type='text/html; charset=utf-8')

    def set_cookie(response, token, authenticated=False):
        response.set_cookie(COOKIE, token, max_age=28800 if authenticated else 600,
                            secure=secure, httponly=True, samesite='Lax', path='/')
        return response

    def anonymous():
        if not g.session:
            token = accounts.new_session()
            g.token, g.session = token, accounts.session(token)
            g.new_cookie = token
        return g.session

    def csrf_field():
        return '<input type="hidden" name="csrf" value="' + esc(anonymous()['csrf']) + '">'

    def check_csrf():
        if not g.session or not secrets.compare_digest(request.form.get('csrf', ''), g.session['csrf']):
            abort(403)

    def throttle(action, maximum=8, period=60):
        if not accounts.limit(action + ':' + (request.remote_addr or ''), maximum, period):
            abort(429)

    def signed_in(user):
        token = accounts.new_session(user['id'], g.token)
        workspaces.get(user['id'])
        response = set_cookie(redirect('/admin', 303), token, True)
        # A workspace sign-in cannot inherit a previous shared-admin login.
        response.delete_cookie('asap_session_5000', path='/')
        return response

    @app.before_request
    def context():
        # Cache before any CSRF/form parsing so the legacy adapter sees the same bytes.
        g.request_body = request.get_data(cache=True) if request.method == 'POST' else b''
        g.token = request.cookies.get(COOKIE, '')
        g.session = accounts.session(g.token)
        g.user = accounts.user(g.session['user_id']) if g.session and g.session['user_id'] else None
        g.new_cookie = None

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'public, max-age=86400' if request.endpoint=='static' else 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers.setdefault('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; img-src https: http:; form-action 'self' https://www.linkedin.com https://x.com https://bsky.social; base-uri 'none'; frame-src 'self'")
        if not request.path.endswith('/feed'):
            response.headers['X-Frame-Options'] = 'DENY'
        if secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if g.get('new_cookie'):
            set_cookie(response, g.new_cookie)
        return response

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def unavailable(error):
        return document('Request unavailable', '<p>Refresh the page and try again. If requests are limited, wait a minute.</p>', error.code)

    def account_gateway(register=False, error=''):
        session=anonymous()
        return Response(auth_page(register=register,google_ready=google.ready,
                                  csrf=session['csrf'],error=error,
                                  email=request.form.get('email','') if request.method=='POST' else ''),
                        content_type='text/html; charset=utf-8')

    @app.get('/')
    def home():
        if g.user:
            return redirect('/admin',303)
        return Response(home_page(),content_type='text/html; charset=utf-8')

    @app.route('/register', methods=['GET', 'POST'])
    @app.route('/signin', methods=['GET', 'POST'])
    def sign_in():
        register = request.path == '/register'
        if g.user:
            return redirect('/admin', 303)
        error = ''
        if request.method == 'POST':
            check_csrf(); throttle('register' if register else 'signin', 5 if register else 8)
            email, password = request.form.get('email', ''), request.form.get('password', '')
            if len(password) > 256:
                abort(400)
            try:
                if register:
                    if password != request.form.get('confirm_password'):
                        raise ValueError('Passwords do not match.')
                    user = accounts.register(email, password)
                else:
                    user = accounts.authenticate(email, password)
                    if not user:
                        raise ValueError('Email or password is incorrect.')
                return signed_in(user)
            except ValueError as exc:
                error = str(exc)
        return account_gateway(register=register,error=error)

    @app.get('/app')
    def dashboard():
        if not g.user:
            return redirect('/signin', 303)
        return redirect('/admin',303)

    @app.get('/account')
    def account():
        if not g.user:
            return redirect('/signin', 303)
        body = '<section class="panel"><p>Email: ' + esc(g.user['email']) + '</p><p>Google: ' + ('Linked' if g.user['google_sub'] else 'Not linked') + '</p>'
        if google.ready and not g.user['google_sub']:
            body += '<form method="post" action="/auth/google/link">' + csrf_field() + '<button>Link Google with this email</button></form>'
        body += '<form method="post" action="/logout">' + csrf_field() + '<button>Sign out</button></form></section>'
        return document('Your account', body)

    @app.route('/auth/google', methods=['GET'])
    @app.post('/auth/google/link')
    def google_start():
        if not google.ready:
            return document('Google sign-in setup pending', '<p>Email and password sign-in is available. The administrator still needs to configure Google OAuth.</p>', 503)
        link_user = None
        if request.method == 'POST':
            if not g.user:
                abort(403)
            check_csrf(); link_user = g.user['id']
        elif g.user:
            return redirect('/admin', 303)
        throttle('google-start')
        anonymous()
        state, nonce, verifier = accounts.start_oauth(g.token, link_user)
        return redirect(google.authorize(state, nonce, verifier), 303)

    @app.get('/auth/google/callback')
    def google_callback():
        if not google.ready or not g.session:
            abort(400)
        try:
            if any(len(request.args.getlist(k)) != 1 for k in ('state', 'code')) or 'error' in request.args:
                raise ValueError('Google authorization was declined or invalid. Start again.')
            pending = accounts.consume_oauth(request.args['state'], g.token)
            if pending['link_user'] and (not g.user or g.user['id'] != pending['link_user']):
                raise ValueError('Sign in again before linking Google.')
            claims = google.exchange(request.args['code'], pending['verifier'], pending['nonce'])
            user = accounts.google_user(claims, pending['link_user'])
            return signed_in(user)
        except ValueError as exc:
            # Only our own validation messages are displayed; library exceptions may
            # contain tokens or provider payloads and must remain private.
            message = str(exc) if str(exc).startswith(('Google authorization', 'Google sign-in expired', 'Sign in ', 'Link the ', 'This Google ', 'Google must ', 'Registration capacity')) else 'Google sign-in could not be verified. Start again.'
            return document('Google sign-in unsuccessful', '<p>' + esc(message) + '</p><a href="/signin">Return to sign in</a>', 400)
        except Exception:
            return document('Google sign-in unsuccessful', '<p>Google could not complete sign-in. Start again from the sign-in page.</p>', 400)

    def portal_session():
        with cache_lock:
            # Keep LinkedIn transient Page selection tied to the exact login session.
            now = time.time()
            for key in list(legacy_sessions):
                if legacy_sessions[key]['expires'] <= now:
                    del legacy_sessions[key]
            session = legacy_sessions.setdefault(g.session['token_hash'], {})
            session.update(csrf=g.session['csrf'], expires=g.session['expires'], authenticated=True, user_id=g.user['id'])
            return session

    class Adapter(handler_class):
        def __init__(self, workspace):
            self.db, self.runtime, self.linkedin_oauth = workspace.db, workspace.runtime, workspace.oauth
            self.config_path = workspace.runtime.config_path if workspace.runtime else workspace.db.parent / 'polling.local.json'
            self.devtools = None
            self.ai_ready = reviewer.model.ready
            self.feed_url = request.host_url.rstrip('/') + ('/u/'+g.user['id']+'/feed' if g.user else '/feed')
            self.path = request.full_path.rstrip('?')
            self.headers = request.headers
            self.rfile = io.BytesIO(g.request_body)
            self.client_address = (request.remote_addr or '', 0)
            self.response = None
            if g.user:
                self.session = portal_session
        def send(self, status, body, cookie=None):
            self.response = Response(body, status=status, content_type='text/html; charset=utf-8')
            if cookie:
                self.response.headers.add('Set-Cookie', cookie)
            return self.response
        def redirect(self, path, cookie=None):
            self.response = redirect(path, 303)
            if cookie:
                self.response.headers.add('Set-Cookie', cookie)
            return self.response

    @app.post('/llm/suggest')
    def ai_suggest():
        workspace=workspaces.get(g.user['id']) if g.user else default
        session=Adapter(workspace).session()
        if not session or not session.get('authenticated'):
            abort(403)
        if not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):
            abort(403)
        throttle('ai-review:'+str(g.user['id'] if g.user else 'admin'),3,60)
        try:
            reviewer.submit(workspace.db,request.form.get('platform',''),request.form.get('post_id',''),g.user['id'] if g.user else 'admin')
            return redirect('/admin?view=pending&notice=AI+review+requested.+Refresh+results+to+see+the+suggestion.',303)
        except ValueError as exc:
            return document('AI review unavailable','<p>'+esc(exc)+'</p><a href="/admin?view=pending">Back to review queue</a>',400)

    @app.get('/bluesky/client-metadata.json')
    def bluesky_client_metadata():
        return social.bluesky_metadata()

    @app.post('/<provider>/connect')
    def social_start(provider):
        if provider=='linkedin':
            return editorial('linkedin/connect')
        if provider not in ('x','bluesky'):
            abort(404)
        workspace = workspaces.get(g.user['id']) if g.user else default
        session = Adapter(workspace).session()
        if not session or not session.get('authenticated'):
            return redirect('/signin',303)
        if not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):
            abort(403)
        throttle('social-connect',5)
        try:
            url, nonce = social.begin(provider,session,workspace,g.session['token_hash'] if g.user else None)
            response = redirect(url,303)
            response.set_cookie('asap_connect_'+provider,nonce,max_age=600,secure=secure,
                                httponly=True,samesite='Lax',path='/'+provider+'/callback')
            return response
        except Exception:
            message = ('The administrator needs to configure X website authorization.' if provider=='x' and not os.environ.get('X_CLIENT_ID')
                       else 'Authorization could not start. Return to Sources and try again later.')
            return document('Connection unavailable','<p>'+esc(message)+'</p><a href="/admin?view=sources">Back to Sources</a>',400)

    @app.get('/<provider>/callback')
    def social_callback(provider):
        # LinkedIn retains its existing callback handler.
        if provider=='linkedin':
            return editorial('linkedin/callback')
        if provider not in ('x','bluesky'):
            abort(404)
        try:
            if any(len(request.args.getlist(k))!=1 for k in ('state',)) or len(request.args.getlist('code'))>1:
                raise ValueError('Invalid callback')
            pending = social.consume(provider,request.args['state'],request.cookies.get('asap_connect_'+provider,''),
                                     g.session['token_hash'] if g.user else None)
            if 'error' in request.args or not request.args.get('code'):
                raise ValueError('Authorization declined')
            if provider=='bluesky' and len(request.args.getlist('iss'))!=1:
                raise ValueError('Missing issuer')
            # Strict legacy cookies are absent during a cross-site redirect.
            # Reissue the same verified session as Lax so the following Sources
            # navigation retains login; CSRF remains required for every mutation.
            legacy_cookie = Adapter(pending['workspace']).oauth_session_cookie(pending['session']) if pending['owner'] is None else None
            social.complete(pending,request.args['code'],request.args.get('iss',''))
            response = redirect('/admin?view=sources&notice=Account+connected.+Automatic+polling+remains+off+for+new+sources.',303)
            if legacy_cookie:
                response.headers.add('Set-Cookie',legacy_cookie)
        except Exception:
            response = document('Connection unsuccessful','<p>The connection was declined, expired, or could not be verified. Return to Sources to start again. Bluesky Authenticate currently supports bsky.social hosted accounts.</p><a href="/admin?view=sources">Back to Sources</a>',400)
        response.delete_cookie('asap_connect_'+provider,path='/'+provider+'/callback')
        return response

    @app.route('/u/<uid>/feed')
    @app.route('/u/<uid>/embed-demo')
    def public_workspace(uid):
        try:
            workspace = workspaces.get(uid)
        except ValueError:
            abort(404)
        handler = Adapter(workspace)
        handler.path = '/feed' if request.path.endswith('/feed') else '/embed-demo'
        # Public feeds must not inherit an authenticated viewer's workspace context.
        handler.do_GET()
        response = handler.response
        if request.path.endswith('/embed-demo'):
            response.set_data(response.get_data().replace(b'src="/feed"', ('src="/u/' + uid + '/feed"').encode()))
        return response

    @app.route('/<path:path>', methods=['GET', 'POST'])
    def editorial(path):
        if path == 'logout' and g.user:
            check_csrf()
            with cache_lock:
                previous = legacy_sessions.pop(g.session['token_hash'], None)
                if previous:
                    previous['authenticated'] = False
            accounts.logout(g.token)
            response = redirect('/signin', 303)
            response.delete_cookie(COOKIE, path='/')
            response.delete_cookie('asap_session_5000', path='/')
            return response
        # /feed and /embed-demo retain the original deployment's public identity.
        workspace = default if path in ('feed', 'embed-demo') or not g.user else workspaces.get(g.user['id'])
        if path == 'login' and g.user:
            return redirect('/admin', 303)
        if path == 'linkedin/callback':
            state = request.args.get('state', '')
            # Strict administrator cookies are deliberately absent on this cross-site
            # callback. Route only by an existing opaque state, then the core verifies
            # the nonce, expiry and the initiating session before any network call.
            candidates = [default] + list(workspaces.active.values())
            for candidate in candidates:
                with candidate.oauth.lock:
                    pending = candidate.oauth.pending.get(state)
                if pending:
                    session = pending['session']
                    if session.get('user_id'):
                        with closing(accounts.connect()) as conn:
                            alive = conn.execute('SELECT 1 FROM sessions WHERE user_id=? AND csrf=? AND expires>?', (session['user_id'], session['csrf'], time.time())).fetchone()
                        if not alive:
                            session['authenticated'] = False
                        if not g.user or g.user['id'] != session['user_id'] or g.session['csrf'] != session['csrf']:
                            return document('LinkedIn connection expired', '<p>Return to Sources in the account that started this connection.</p>', 400)
                    workspace = candidate
                    break
        if g.user and request.method == 'POST' and path == 'notifications':
            check_csrf()
            if not g.user['email_verified'] or request.form.get('recipient', '').strip().lower() != g.user['email']:
                return document('Verify your notification address', '<p>Link Google with your account email before enabling email notifications. Notifications can only be sent to that verified address.</p>', 403)
        handler = Adapter(workspace)
        if request.method == 'POST':
            handler.do_POST()
        else:
            handler.do_GET()
        response = handler.response
        if response is None:
            abort(500)
        if g.user and response.content_type.startswith('text/html') and path == 'admin':
            uid = g.user['id']
            content = response.get_data().replace(b'href="/feed"', ('href="/u/' + uid + '/feed"').encode()).replace(b'href="/embed-demo"', ('href="/u/' + uid + '/embed-demo"').encode())
            content = content.replace(b'<h1>ASAP Admin</h1>', ('<h1>ASAP Workspace</h1><a href="/app">My workspace</a><a href="/account">Account</a><span>' + esc(g.user['email']) + '</span>').encode())
            response.set_data(content)
        return response

    return app
