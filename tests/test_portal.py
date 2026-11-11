"""Offline acceptance: two identities, HTTP ownership boundary, restart and OIDC."""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from src.accounts import Accounts, digest
from src.google_login import GoogleLogin
from src.portal import create_app, COOKIE
from src.store_poc import store, process_stored
from src.web_editorial import initialize

PASSWORD = 'fixture-password-1234'


def csrf(response):
    return re.search(rb'name="csrf" value="([^"]+)"', response.data).group(1).decode()


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.db = self.root / 'asap.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn:
            store(conn, []); process_stored(conn); conn.commit(); initialize(conn); conn.commit()
        self.google = Mock(ready=True)
        self.google.authorize.side_effect = lambda state, nonce, verifier: 'https://accounts.google.com/?state='+state
        self.app = create_app(self.db, 'admin', google=self.google, secure=False)
        self.app.testing = True
        self.a, self.b = self.app.test_client(), self.app.test_client()
        self.accounts = self.app.extensions['accounts']
        self.workspaces = self.app.extensions['workspaces']
        self.addCleanup(self.workspaces.stop)

    def register(self, client, email):
        token = csrf(client.get('/register'))
        response = client.post('/register', data=dict(csrf=token, email=email, password=PASSWORD, confirm_password=PASSWORD))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, '/admin')
        session = self.accounts.session(client.get_cookie(COOKIE).value)
        return self.accounts.user(session['user_id'])

    def post(self, client, path, data):
        token = csrf(client.get('/admin'))
        return client.post(path, data=dict(csrf=token, **data))

    def test_two_users_cannot_read_private_or_mutate_each_others_posts(self):
        alice = self.register(self.a, 'alice@example.com'); bob = self.register(self.b, 'bob@example.com')
        self.assertEqual(self.post(self.a, '/announcement', dict(text='Alice private notice')).status_code, 303)
        self.assertNotIn(b'Alice private notice', self.b.get('/admin?view=pending').data)
        wa, wb = self.workspaces.get(alice['id']), self.workspaces.get(bob['id'])
        with closing(sqlite3.connect(wa.db)) as conn:
            post_id = conn.execute('SELECT post_id FROM posts').fetchone()[0]
            self.assertEqual(conn.execute('SELECT account_id FROM posts').fetchone()[0], alice['id'])
        attack = self.post(self.b, '/action', dict(platform='manual', post_id=post_id, action='approve', user_id=alice['id']))
        self.assertEqual(attack.status_code, 400)
        self.assertEqual(self.post(self.a, '/action', dict(platform='manual', post_id=post_id, action='approve')).status_code, 303)
        self.assertIn(b'Alice private notice', self.a.get('/u/'+alice['id']+'/feed').data)
        self.assertNotIn(b'Alice private notice', self.b.get('/u/'+bob['id']+'/feed').data)
        self.assertNotIn(b'Alice private notice', self.a.get('/feed').data)
        with closing(sqlite3.connect(wa.db)) as conn:
            self.assertEqual(conn.execute('SELECT actor FROM editorial_actions LIMIT 1').fetchone()[0], alice['id'])
        self.assertEqual(self.post(self.a, '/action', dict(platform='manual', post_id=post_id, action='withdraw')).status_code, 303)
        self.assertNotIn(b'Alice private notice', self.a.get('/u/'+alice['id']+'/feed').data)
        self.assertEqual(json.loads(wa.runtime.config_path.read_text())['sources'], [{'platform':'linkedin','enabled':False}])
        self.assertNotEqual(wa.oauth.credentials.directory if hasattr(wa.oauth.credentials,'directory') else wa.db.parent, wb.db.parent)

    def test_csrf_session_rotation_logout_restart_and_hashed_passwords(self):
        anon = self.a.get('/register'); old = self.a.get_cookie(COOKIE).value
        response = self.a.post('/register', data=dict(csrf='bad', email='a@example.com', password=PASSWORD, confirm_password=PASSWORD))
        self.assertEqual(response.status_code, 403)
        alice = self.register(self.a, 'alice@example.com')
        token = self.a.get_cookie(COOKIE).value
        self.assertNotEqual(old, token); self.assertIsNone(self.accounts.session(old))
        with closing(self.accounts.connect()) as conn:
            row = conn.execute('SELECT password_hash FROM users').fetchone()
            self.assertNotIn(PASSWORD, row[0])
            self.assertIsNone(conn.execute('SELECT 1 FROM sessions WHERE token_hash=?', (token,)).fetchone())
            self.assertIsNotNone(conn.execute('SELECT 1 FROM sessions WHERE token_hash=?', (digest(token),)).fetchone())
        restarted = create_app(self.db, 'admin', google=self.google, secure=False)
        client = restarted.test_client(); client.set_cookie(COOKIE, token)
        self.assertEqual(client.get('/app').location, '/admin')
        self.assertEqual(client.post('/logout', data={'csrf':'bad'}).status_code, 403)
        self.assertEqual(client.get('/logout').status_code, 403)
        csrf_value = csrf(client.get('/account'))
        self.assertEqual(client.post('/logout', data={'csrf':csrf_value}).status_code, 303)
        self.assertIsNone(self.accounts.session(token))
        self.assertEqual(self.a.get('/app').status_code, 303)
        self.assertEqual(self.a.get('/u/../../feed').status_code, 404)

    def test_workspace_settings_and_source_credentials_do_not_leak(self):
        alice = self.register(self.a, 'alice@example.com'); bob = self.register(self.b, 'bob@example.com')
        self.assertEqual(self.post(self.a, '/presentation', dict(accent='#aa1122', font_size='19', show_origin='on')).status_code, 303)
        self.assertNotIn(b'#aa1122', self.b.get('/u/'+bob['id']+'/feed').data)
        self.assertIn(b'#aa1122', self.a.get('/u/'+alice['id']+'/feed').data)
        # No original administrator X bearer credential is borrowed by new accounts.
        self.assertEqual(self.post(self.a, '/source-save', dict(provider='x',account='123',interval_seconds='1800',page_size='5')).status_code, 400)
        self.assertEqual(self.post(self.a, '/notifications', dict(enabled='on',channel='email',recipient='victim@example.com')).status_code, 403)
        self.assertEqual(self.post(self.a, '/source-save', dict(provider='bluesky',account='alice.bsky.social',interval_seconds='1800',page_size='5')).status_code, 303)
        self.assertNotIn(b'alice.bsky.social', self.b.get('/admin?view=sources').data)
        self.assertFalse(any(s.get('enabled') for s in self.workspaces.get(alice['id']).runtime.read_config()['sources']))

    def test_legacy_admin_and_public_feed_compatibility(self):
        client = self.app.test_client()
        login = client.get('/login')
        response = client.post('/login', data={'csrf':csrf(login),'password':'admin'})
        self.assertEqual(response.status_code, 303)
        self.assertIn(b'ASAP Admin', client.get('/admin').data)
        self.assertEqual(client.get('/feed').status_code, 200)
        self.assertIsNone(client.get('/feed').headers.get('X-Frame-Options'))
        self.assertEqual(client.get('/admin').headers['X-Frame-Options'], 'DENY')
        user = self.register(client, 'new@example.com')
        self.assertIsNone(client.get_cookie('asap_session_5000'))
        self.assertIn(b'ASAP Workspace', client.get('/admin').data)
        feed_console = client.get('/admin?view=feed').data
        self.assertIn(b'ASAP Workspace', feed_console)
        self.assertIn(b'aria-label="Feed embed code"', feed_console)
        self.assertIn(('src="http://localhost/u/'+user['id']+'/feed"').encode(), feed_console)
        self.assertNotIn(b'Embedding Preview', client.get('/admin').data)
        self.assertIn(b'Mock Website', client.get('/admin').data)
        self.assertIn(('href="/u/'+user['id']+'/embed-demo"').encode(), client.get('/admin').data)
        preview = client.get('/u/'+user['id']+'/embed-demo')
        self.assertIn(('src="/u/'+user['id']+'/feed"').encode(), preview.data)

    def google_begin(self, client):
        response = client.get('/auth/google')
        self.assertEqual(response.status_code, 303)
        return parse_qs(urlparse(response.location).query)['state'][0]

    def test_google_login_state_binding_replay_and_minimal_claims(self):
        state = self.google_begin(self.a)
        self.google.exchange.return_value = dict(sub='google-sub-1', email='google@example.com', email_verified=True)
        stolen = self.b.get('/auth/google/callback?'+urlencode(dict(state=state,code='fixture')))
        self.assertEqual(stolen.status_code, 400); self.google.exchange.assert_not_called()
        response = self.a.get('/auth/google/callback?'+urlencode(dict(state=state,code='fixture')))
        self.assertEqual(response.status_code, 303); self.google.exchange.assert_called_once()
        self.assertEqual(self.a.get('/auth/google/callback?'+urlencode(dict(state=state,code='fixture'))).status_code, 400)
        self.google.exchange.assert_called_once()
        uid = self.accounts.session(self.a.get_cookie(COOKIE).value)['user_id']
        self.assertEqual(self.accounts.user(uid)['google_sub'], 'google-sub-1')

    def test_google_never_auto_links_local_email_and_explicit_link_is_csrf_protected(self):
        alice = self.register(self.a, 'alice@example.com')
        self.google.exchange.return_value = dict(sub='google-alice',email='alice@example.com',email_verified=True)
        state = self.google_begin(self.b)
        response = self.b.get('/auth/google/callback?'+urlencode(dict(state=state,code='fixture')))
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.accounts.user(alice['id'])['google_sub'])
        self.assertEqual(self.a.post('/auth/google/link', data={'csrf':'bad'}).status_code, 403)
        response = self.a.post('/auth/google/link', data={'csrf':csrf(self.a.get('/account'))})
        state = parse_qs(urlparse(response.location).query)['state'][0]
        self.assertEqual(self.a.get('/auth/google/callback?'+urlencode(dict(state=state,code='fixture'))).status_code, 303)
        self.assertEqual(self.accounts.user(alice['id'])['google_sub'], 'google-alice')

    def test_auth_rate_limit_duplicate_registration_and_cookie_security(self):
        self.register(self.a, 'alice@example.com')
        cookie = self.a.get_cookie(COOKIE)
        self.assertTrue(cookie.http_only); self.assertEqual(cookie.same_site, 'Lax')
        for index in range(8):
            response = self.b.get('/signin')
            failure = self.b.post('/signin', data=dict(csrf=csrf(response),email='alice@example.com',password='incorrect'))
            self.assertEqual(failure.status_code, 200)
        self.assertEqual(self.b.post('/signin', data=dict(csrf=csrf(self.b.get('/signin')),email='alice@example.com',password=PASSWORD)).status_code, 429)
        with self.assertRaises(ValueError):self.accounts.register('ALICE@example.com',PASSWORD)
        with self.assertRaises(ValueError):self.accounts.register('weak@example.com','admin')
        secure_app = create_app(self.db,'admin',secure=True)
        response = secure_app.test_client().get('/signin',base_url='https://asap.surf')
        self.assertIn('Secure;',response.headers['Set-Cookie'])
        self.assertEqual(response.headers['Strict-Transport-Security'],'max-age=31536000')

    def test_google_oidc_authorize_uses_pkce_nonce_and_only_login_scopes(self):
        google = GoogleLogin('id','secret','https://asap.surf/auth/google/callback')
        values = parse_qs(urlparse(google.authorize('state','nonce','verifier')).query)
        self.assertEqual(values['scope'],['openid email profile'])
        self.assertEqual(values['code_challenge_method'],['S256'])
        self.assertNotIn('secret', google.authorize('state','nonce','verifier'))
        self.assertEqual(values['nonce'],['nonce'])
        with patch('requests.post') as post, patch('google.oauth2.id_token.verify_oauth2_token') as verify:
            post.return_value.json.return_value={'id_token':'signed-fixture'}
            verify.return_value=dict(sub='sub',nonce='nonce',email_verified=True)
            self.assertEqual(google.exchange('code','verifier','nonce')['sub'],'sub')
            self.assertEqual(verify.call_args.args[2],'id')
            verify.return_value={'nonce':'wrong'}
            with self.assertRaises(ValueError):google.exchange('code','verifier','nonce')

    def test_linkedin_credentials_callback_and_page_choice_are_account_bound(self):
        alice=self.register(self.a,'alice@example.com'); bob=self.register(self.b,'bob@example.com')
        wa,wb=self.workspaces.get(alice['id']),self.workspaces.get(bob['id'])
        config=dict(client_id='fixture-id',client_secret='fixture-secret',redirect_uri='https://asap.surf/linkedin/callback')
        calls=[]
        def exchange(*args,**kwargs):
            calls.append(1)
            return dict(access_token='alice-private-token',expires_in=3600,scope='r_organization_social,rw_organization_admin')
        wa.oauth.config_getter=lambda:config; wa.oauth.request=exchange
        response=self.post(self.a,'/linkedin/connect',{})
        self.assertEqual(response.status_code,303)
        state=parse_qs(urlparse(response.location).query)['state'][0]
        nonce=self.a.get_cookie('asap_linkedin_5000',path='/linkedin/callback').value
        self.b.set_cookie('asap_linkedin_5000',nonce,path='/linkedin/callback')
        self.assertEqual(self.b.get('/linkedin/callback?'+urlencode(dict(state=state,code='code'))).status_code,400)
        self.assertEqual(calls,[])
        self.assertEqual(self.a.get('/linkedin/callback?'+urlencode(dict(state=state,code='code'))).status_code,200)
        self.assertEqual(calls,[1])
        files=list(wa.oauth.credentials.directory.glob('*.json'))
        self.assertEqual(len(files),1)
        self.assertFalse(wb.oauth.credentials.directory.exists())
        self.assertNotIn(b'alice-private-token',self.a.get('/linkedin/choose').data)
        self.assertNotIn(b'alice-private-token',self.b.get('/admin?view=sources').data)
        # Logging out revokes an in-flight authorization before its token exchange.
        response=self.post(self.a,'/linkedin/connect',{})
        state=parse_qs(urlparse(response.location).query)['state'][0]
        self.post(self.a,'/logout',{})
        self.assertEqual(self.a.get('/linkedin/callback?'+urlencode(dict(state=state,code='code'))).status_code,400)
        self.assertEqual(calls,[1])

    def test_google_invalid_claims_duplicate_parameters_and_expired_state(self):
        state=self.google_begin(self.a)
        self.assertEqual(self.a.get('/auth/google/callback?state='+state+'&state=extra&code=code').status_code,400)
        self.google.exchange.assert_not_called()
        with closing(self.accounts.connect()) as conn,conn:
            conn.execute('UPDATE oauth_states SET expires=0')
        self.assertEqual(self.a.get('/auth/google/callback?'+urlencode(dict(state=state,code='code'))).status_code,400)
        self.google.exchange.assert_not_called()
        for claims in ({'sub':'x','email':'x@example.com','email_verified':False},{'email':'x@example.com','email_verified':True}):
            with self.assertRaises(ValueError):self.accounts.google_user(claims)

    def test_verified_notification_body_and_recipient_isolation(self):
        alice=self.register(self.a,'alice@example.com')
        self.accounts.google_user(dict(sub='google-alice',email='alice@example.com',email_verified=True),alice['id'])
        # No SMTP is called: settings persist with delivery disabled.
        response=self.post(self.a,'/notifications',dict(channel='email',recipient='alice@example.com'))
        self.assertEqual(response.status_code,303)
        with closing(sqlite3.connect(self.workspaces.get(alice['id']).db)) as conn:
            row=conn.execute('SELECT enabled,recipient FROM notification_settings').fetchone()
            self.assertEqual(row,(0,'alice@example.com'))
        self.assertEqual(self.post(self.a,'/notifications',dict(channel='email',recipient='other@example.com')).status_code,403)

from urllib.parse import urlencode
