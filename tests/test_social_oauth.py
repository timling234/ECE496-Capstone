"""No network: real cryptography, callback ownership, refresh and source ingestion."""
from contextlib import closing
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from src.app_runtime import AppRuntime
from src.portal import create_app, COOKIE
from src.social_oauth import SocialOAuth, XCredentials, destination, dpop, BSKY
from src.store_poc import store, process_stored
from src.web_editorial import initialize
from run_polling import load_sources

DID='did:plc:abcdefghijklmnopqrstuvwx'
PDS='https://enoki.us-east.host.bsky.network'


def csrf(response):
    return re.search(rb'name="csrf" value="([^"]+)"',response.data).group(1).decode()


class SocialTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.db=self.root/'asap.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn:
            store(conn,[]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
        self.runtime=AppRuntime(self.db)
        self.app=create_app(self.db,'admin',runtime=self.runtime,secure=False)
        self.app.testing=True
        self.social=self.app.extensions['social'];self.social.http=self.http
        self.a=self.app.test_client();self.b=self.app.test_client()
        self.accounts=self.app.extensions['accounts'];self.ws=self.app.extensions['workspaces']
        self.addCleanup(self.ws.stop)
        self.calls=[];self.payload_override={};self.subject=DID;self.pds=PDS;self.issuer=BSKY
        self.env=patch.dict(os.environ,{'X_CLIENT_ID':'fixture-id','X_CLIENT_SECRET':'fixture-secret','ASAP_PUBLIC_URL':'https://asap.surf'})
        self.env.start();self.addCleanup(self.env.stop)
        self.alice=self.register(self.a,'alice@example.com');self.bob=self.register(self.b,'bob@example.com')

    def register(self,client,email):
        token=csrf(client.get('/register'))
        self.assertEqual(client.post('/register',data=dict(csrf=token,email=email,password='fixture-password-1234',confirm_password='fixture-password-1234')).status_code,303)
        return self.accounts.user(self.accounts.session(client.get_cookie(COOKIE).value)['user_id'])

    def http(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        if url.endswith('/oauth/par'):
            return 201,{'request_uri':'urn:ietf:params:oauth:request_uri:fixture','expires_in':600},{'DPoP-Nonce':'fixture-nonce'}
        if url=='https://api.x.com/2/oauth2/token':
            return 200,dict(access_token='private-x-token',refresh_token='private-refresh',expires_in=7200,scope='tweet.read users.read offline.access',token_type='bearer',**self.payload_override),{}
        if url=='https://api.x.com/2/users/me':
            return 200,{'data':{'id':'12345','username':'fixture-user'}},{}
        if url==BSKY+'/oauth/token':
            return 200,{'access_token':'discard-bsky-token','refresh_token':'discard-refresh','sub':self.subject,'scope':'atproto','token_type':'DPoP'},{}
        if url=='https://plc.directory/'+DID:
            return 200,{'id':DID,'service':[{'id':'#atproto_pds','type':'AtprotoPersonalDataServer','serviceEndpoint':self.pds}]},{}
        if url==PDS+'/.well-known/oauth-protected-resource':
            return 200,{'resource':PDS,'authorization_servers':[self.issuer]},{}
        if url==BSKY+'/.well-known/oauth-authorization-server':
            return 200,{'issuer':self.issuer},{}
        raise AssertionError('Unexpected network destination')

    def start(self,client,provider):
        result=client.post('/'+provider+'/connect',data={'csrf':csrf(client.get('/admin'))})
        self.assertEqual(result.status_code,303,result.data)
        state=next(s for s,p in self.social.pending.items() if p['platform']==provider)
        return state,result

    def callback(self,client,provider,state,**extra):
        return client.get('/'+provider+'/callback?'+urlencode(dict(state=state,code='fixture-code',**extra)))

    def test_x_authorize_pkce_scopes_and_no_client_secret_in_browser(self):
        state,result=self.start(self.a,'x')
        query=parse_qs(urlparse(result.location).query)
        self.assertEqual(query['scope'],['tweet.read users.read offline.access'])
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertNotIn('fixture-secret',result.location);self.assertNotIn('tweet.write',result.location)
        self.assertEqual(self.calls,[])
        self.assertIn('HttpOnly;',result.headers['Set-Cookie'])
        self.assertIn('SameSite=Lax',result.headers['Set-Cookie'])

    def test_x_callback_creates_disabled_source_and_private_credentials(self):
        state,_=self.start(self.a,'x')
        result=self.callback(self.a,'x',state)
        self.assertEqual(result.status_code,303,result.data)
        wa=self.ws.get(self.alice['id']);source=wa.runtime.read_config()['sources'][-1]
        self.assertFalse(source['enabled']);self.assertEqual(source['account'],'12345')
        grant=wa.db.parent/'x_credentials'/(source['connection_id']+'.json')
        self.assertEqual(grant.stat().st_mode&0o777,0o600)
        self.assertIn('private-x-token',grant.read_text())
        self.assertNotIn(b'private-x-token',self.a.get('/admin?view=sources').data)
        self.assertNotIn(b'fixture-user',self.b.get('/admin?view=sources').data)
        self.assertEqual(len(self.calls),2)
        provider=load_sources(wa.runtime.config_path)[0].provider
        self.assertEqual(provider.account,'12345')
        self.assertEqual(provider.token_getter(),'private-x-token')
        received=[]
        provider.transport=lambda url,token:(received.append(token) or {'data':[]})
        provider.fetch(None)
        self.assertEqual(received,['private-x-token'])
        self.assertEqual(self.callback(self.a,'x',state).status_code,400)
        self.assertEqual(len(self.calls),2)
        # Grant survives application restart in this tenant only.
        restarted=create_app(self.db,'admin',runtime=self.runtime,secure=False)
        self.assertEqual(restarted.extensions['workspaces'].get(self.alice['id']).runtime.sources()[0].provider.token_getter(),'private-x-token')
        self.assertEqual(restarted.extensions['workspaces'].get(self.bob['id']).runtime.sources(),[])

    def test_cross_account_cookie_or_state_does_not_consume_authorization(self):
        state,_=self.start(self.a,'x')
        nonce=self.a.get_cookie('asap_connect_x',path='/x/callback').value
        self.b.set_cookie('asap_connect_x',nonce,path='/x/callback')
        self.assertEqual(self.callback(self.b,'x',state).status_code,400)
        self.assertEqual(self.calls,[])
        self.assertIn(state,self.social.pending)
        self.assertEqual(self.callback(self.a,'x',state).status_code,303)

    def test_csrf_expiry_decline_and_logout_make_no_provider_request(self):
        self.assertEqual(self.a.post('/x/connect',data={'csrf':'bad'}).status_code,403)
        state,_=self.start(self.a,'x');self.social.pending[state]['expires']=0
        self.assertEqual(self.callback(self.a,'x',state).status_code,400)
        state,_=self.start(self.a,'x')
        self.assertEqual(self.callback(self.a,'x',state,error='access_denied').status_code,400)
        state,_=self.start(self.a,'x')
        self.a.post('/logout',data={'csrf':csrf(self.a.get('/account'))})
        self.assertEqual(self.callback(self.a,'x',state).status_code,400)
        self.assertEqual(self.calls,[])

    def test_invalid_scopes_fail_without_profile_lookup_or_saved_grant(self):
        original=self.social.http
        def missing_scope(method,url,**kwargs):
            if url.endswith('/oauth2/token'):
                self.calls.append((method,url,kwargs))
                return 200,dict(access_token='secret',expires_in=7200,scope='users.read',token_type='bearer'),{}
            return original(method,url,**kwargs)
        self.social.http=missing_scope
        state,_=self.start(self.a,'x')
        self.assertEqual(self.callback(self.a,'x',state).status_code,400)
        self.assertEqual(len(self.calls),1)
        self.assertFalse((self.ws.get(self.alice['id']).db.parent/'x_credentials').exists())

    def test_x_refresh_once_persists_rotation_and_parallel_source_reads(self):
        credentials=XCredentials(self.root/'grant',request=self.http,clock=lambda:100)
        connection='a'*32
        credentials.save(connection,dict(access_token='expired',refresh_token='old',expires_at=0))
        self.assertEqual(credentials.access_token(connection),'private-x-token')
        self.assertEqual(credentials.access_token(connection),'private-x-token')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(credentials.read(connection)['refresh_token'],'private-refresh')

    def test_x_refresh_rate_limit_preserves_cooldown_and_does_not_retry(self):
        from urllib.error import HTTPError
        calls=[]
        def limited(*args,**kwargs):
            calls.append(1)
            return 429,{'error':'too_many_requests'},{'Retry-After':'600'}
        credentials=XCredentials(self.root/'limited',request=limited)
        credentials.save('a'*32,dict(access_token='expired',refresh_token='private',expires_at=0))
        with self.assertRaises(HTTPError) as caught:
            credentials.access_token('a'*32)
        self.assertEqual(caught.exception.code,429)
        self.assertEqual(caught.exception.headers['Retry-After'],'600')
        self.assertEqual(len(calls),1)

    def test_bluesky_identity_only_dpop_par_then_disabled_public_source(self):
        state,result=self.start(self.a,'bluesky')
        self.assertTrue(result.location.startswith(BSKY+'/oauth/authorize?'))
        self.assertGreater(self.social.pending[state]['expires'],time.time()+590)
        par=self.calls[0][2]
        self.assertEqual(par['data']['scope'],'atproto')
        self.assertEqual(par['data']['code_challenge_method'],'S256')
        self.assertIn('DPoP',par['headers'])
        self.assertEqual(self.callback(self.a,'bluesky',state,iss=BSKY).status_code,303)
        wa=self.ws.get(self.alice['id']);source=wa.runtime.read_config()['sources'][-1]
        self.assertEqual(source['account'],DID);self.assertFalse(source['enabled'])
        grant=(wa.db.parent/'bluesky_credentials'/(source['connection_id']+'.json')).read_text()
        self.assertIn('identity_only',grant);self.assertNotIn('discard-bsky-token',grant);self.assertNotIn('discard-refresh',grant)
        self.assertEqual(len(self.calls),5)
        self.assertNotIn(DID.encode(),self.b.get('/admin?view=sources').data)

    def test_bluesky_issuer_mismatch_before_token_exchange(self):
        state,_=self.start(self.a,'bluesky')
        self.assertEqual(self.callback(self.a,'bluesky',state,iss='https://attacker.example').status_code,400)
        self.assertEqual(len(self.calls),1)

    def test_bluesky_untrusted_subject_pds_or_issuer_cannot_create_source(self):
        for invalid in ('subject','pds','issuer'):
            with self.subTest(invalid=invalid):
                self.subject=DID;self.pds=PDS;self.issuer=BSKY
                setattr(self,invalid,{'subject':'did:web:127.0.0.1','pds':'https://127.0.0.1','issuer':'https://evil.example'}[invalid])
                state,_=self.start(self.a,'bluesky')
                self.assertEqual(self.callback(self.a,'bluesky',state,iss=BSKY).status_code,400)
                self.assertEqual(len(self.ws.get(self.alice['id']).runtime.read_config()['sources']),1)

    def test_dpop_nonce_challenge_has_exactly_one_bounded_retry(self):
        calls=[]
        def nonce_challenge(method,url,**kwargs):
            calls.append(kwargs)
            if len(calls)==1:return 400,{'error':'use_dpop_nonce'},{'DPoP-Nonce':'next-nonce'}
            return 201,{'request_uri':'urn:ietf:params:oauth:request_uri:ok','expires_in':60},{}
        self.social.http=nonce_challenge
        self.start(self.a,'bluesky')
        self.assertEqual(len(calls),2)
        decode=lambda value:json.loads(base64.urlsafe_b64decode(value+'='*(-len(value)%4)))
        self.assertEqual(decode(calls[1]['headers']['DPoP'].split('.')[1])['nonce'],'next-nonce')
        self.assertNotEqual(calls[0]['headers']['DPoP'],calls[1]['headers']['DPoP'])
        calls.clear()
        self.social.http=lambda *a,**k:(400,{'error':'invalid_client'},{})
        self.assertEqual(self.a.post('/bluesky/connect',data={'csrf':csrf(self.a.get('/admin'))}).status_code,400)

    def test_dpop_signature_is_valid_es256_and_has_no_private_jwk(self):
        key=ec.generate_private_key(ec.SECP256R1());token=dpop(key,BSKY+'/oauth/token','nonce')
        header,body,signature=token.split('.')
        decode=lambda v:base64.urlsafe_b64decode(v+'='*(-len(v)%4))
        self.assertNotIn('d',json.loads(decode(header))['jwk'])
        raw=decode(signature);self.assertEqual(len(raw),64)
        key.public_key().verify(encode_dss_signature(int.from_bytes(raw[:32],'big'),int.from_bytes(raw[32:],'big')),(header+'.'+body).encode(),ec.ECDSA(hashes.SHA256()))

    def test_destinations_block_private_arbitrary_and_redirect_shapes(self):
        for url in ('http://bsky.social','https://localhost','https://bsky.social.evil.test','https://bsky.social@127.0.0.1','https://bsky.social:8080/oauth/token'):
            with self.assertRaises(ValueError):destination(url)
        destination(PDS);destination(BSKY)
        metadata=self.a.get('/bluesky/client-metadata.json').json
        self.assertEqual(metadata['scope'],'atproto');self.assertEqual(metadata['redirect_uris'],['https://asap.surf/bluesky/callback'])
        self.assertNotIn('fixture-secret',json.dumps(metadata))

    def test_connected_source_identity_cannot_be_edited_and_reauth_keeps_reference(self):
        state,_=self.start(self.a,'x');self.callback(self.a,'x',state)
        runtime=self.ws.get(self.alice['id']).runtime
        source=runtime.read_config()['sources'][-1];connection=source['connection_id']
        response=self.a.post('/source-save',data=dict(csrf=csrf(self.a.get('/admin')),source_key='x:12345',account='999',interval_seconds=1800,page_size=5))
        self.assertEqual(response.status_code,400)
        state,_=self.start(self.a,'x');self.callback(self.a,'x',state)
        self.assertEqual(runtime.read_config()['sources'][-1]['connection_id'],connection)
        self.assertEqual(len(runtime.read_config()['sources']),2)

    def test_bluesky_handle_authorization_merges_existing_source_and_keeps_settings(self):
        from src.source_auth import authentication
        runtime=self.ws.get(self.alice['id']).runtime
        config=runtime.read_config()
        config['sources'].append(dict(platform='bluesky',account='fixture.bsky.social',enabled=False,interval_seconds=3600,page_size=7))
        runtime.save_config(config)
        original=self.social.http
        def aliases(method,url,**kwargs):
            result=original(method,url,**kwargs) if 'identity.resolveHandle?' not in url else (200,{'did':DID},{})
            if url=='https://plc.directory/'+DID:result[1]['alsoKnownAs']=['at://fixture.bsky.social']
            return result
        self.social.http=aliases
        state,_=self.start(self.a,'bluesky')
        self.assertEqual(self.callback(self.a,'bluesky',state,iss=BSKY).status_code,303)
        blue=[s for s in runtime.read_config()['sources'] if s['platform']=='bluesky']
        self.assertEqual(len(blue),1);self.assertEqual(blue[0]['account'],'fixture.bsky.social')
        self.assertEqual(blue[0]['authorized_account'],DID)
        self.assertEqual(blue[0]['page_size'],7);self.assertEqual(blue[0]['interval_seconds'],3600)
        self.assertEqual(authentication(blue[0],runtime.config_path.parent),'Authenticated')
        self.assertEqual(runtime.sources()[0].provider.actor,DID)

    def test_remove_and_restore_saved_connection_without_deleting_posts_or_other_tenant(self):
        state,_=self.start(self.a,'x');self.callback(self.a,'x',state)
        runtime=self.ws.get(self.alice['id']).runtime
        token=csrf(self.a.get('/admin'))
        self.a.post('/announcement',data=dict(csrf=token,text='Keep this announcement'))
        self.assertEqual(self.b.post('/source-remove',data=dict(csrf=csrf(self.b.get('/admin')),source_key='x:12345')).status_code,400)
        self.assertEqual(self.a.post('/source-remove',data=dict(csrf='bad',source_key='x:12345')).status_code,403)
        self.assertEqual(self.a.post('/source-remove',data=dict(csrf=token,source_key='x:12345')).status_code,303)
        self.assertNotIn('x:12345',[s['platform']+':'+s.get('account','') for s in runtime.read_config()['sources']])
        self.assertIn(b'Keep this announcement',self.a.get('/admin?view=pending').data)
        from src.source_connections import choices
        choice=next(c for c in choices(runtime.read_config(),runtime.config_path.parent) if c['platform']=='x')
        data=dict(provider='x',connection_ref=choice['connection_ref'],interval_seconds=1800,page_size=5)
        self.assertEqual(self.b.post('/source-save',data=dict(csrf=csrf(self.b.get('/admin')),**data)).status_code,400)
        self.assertEqual(self.a.post('/source-save',data=dict(csrf=token,**data)).status_code,303)
        self.assertFalse(runtime.read_config()['sources'][-1]['enabled'])
        self.assertEqual(len(self.calls),2)  # Add/remove did not call a provider.

    def test_source_editor_uses_icons_and_server_owned_connected_account(self):
        html=self.a.get('/admin?view=sources&source_form=add').data.split(b'class="panel source-editor"')[1]
        for name in ('X','Bluesky','LinkedIn'):
            self.assertIn(('aria-label="Select '+name+'"').encode(),html)
        self.assertNotIn(b'Choose provider',html);self.assertNotIn(b'Authenticate Bluesky',html)
        self.assertNotIn(b'name="account"',html)
        state,_=self.start(self.a,'x');self.callback(self.a,'x',state)
        html=self.a.get('/admin?view=sources&edit_source=x%3A12345').data.split(b'class="panel source-editor"')[1]
        self.assertIn(b'Advanced settings',html);self.assertIn(b'Posts per request',html)
        self.assertNotIn(b'name="account"',html)
        self.assertEqual(self.a.post('/source-save',data=dict(csrf=csrf(self.a.get('/admin')),source_key='x:12345',interval_seconds=3600,page_size=5)).status_code,303)
        self.assertEqual(self.ws.get(self.alice['id']).runtime.read_config()['sources'][-1]['account'],'12345')

    def test_legacy_cross_site_callback_restores_exact_original_login(self):
        client=self.app.test_client()
        client.post('/login',data=dict(csrf=csrf(client.get('/login')),password='admin'))
        original=client.get_cookie('asap_session_5000').value
        state,_=self.start(client,'x')
        # Simulate the browser withholding its Strict login cookie on return
        # from X, but sending the dedicated Lax callback nonce.
        client.delete_cookie('asap_session_5000')
        result=self.callback(client,'x',state)
        self.assertEqual(result.status_code,303)
        cookie=client.get_cookie('asap_session_5000')
        self.assertEqual(cookie.value,original)
        self.assertEqual(cookie.same_site,'Lax');self.assertTrue(cookie.http_only)
        self.assertIn('Max-Age=287',result.headers.getlist('Set-Cookie')[0])
        landing=client.get(result.location)
        self.assertEqual(landing.status_code,200)
        self.assertIn(b'ASAP Admin',landing.data)
        self.assertIn(b'class="badge good">Authenticated',landing.data)
        self.assertIn(b'Re-authenticate',landing.data)
        self.assertIn(b'Disabled',landing.data)
        self.assertEqual(client.post('/source-toggle',data={'csrf':'bad','source_key':'x:12345'}).status_code,403)
        # A replay cannot issue another session cookie.
        replay=self.callback(client,'x',state)
        self.assertEqual(replay.status_code,400)
        self.assertFalse(any(h.startswith('asap_session_5000=') for h in replay.headers.getlist('Set-Cookie')))

    def test_legacy_administrator_connection_and_logout(self):
        client=self.app.test_client()
        client.post('/login',data=dict(csrf=csrf(client.get('/login')),password='admin'))
        state,_=self.start(client,'x')
        self.assertEqual(self.callback(client,'x',state).status_code,303)
        self.assertEqual(self.runtime.read_config()['sources'][-1]['account'],'12345')
        state,_=self.start(client,'x')
        client.post('/logout',data=dict(csrf=csrf(client.get('/admin'))))
        count=len(self.calls)
        self.assertEqual(self.callback(client,'x',state).status_code,400)
        self.assertEqual(len(self.calls),count)


if __name__=='__main__':unittest.main()
