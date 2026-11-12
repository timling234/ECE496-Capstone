"""Offline OAuth/browser HTTP flow, quota boundaries and ingestion tests."""
from contextlib import closing
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import html
import json
import re
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse

from run_polling import load_sources
from src.app_runtime import AppRuntime
from src.linkedin import Credentials, OAuth, LinkedInProvider, ReconnectRequired
from src.source_config import configure_source
from src.store_poc import store, process_stored, load_posts
from src.web_app import make_server
from src.web_editorial import initialize, publishable


POST = dict(id='urn:li:share:123', author='urn:li:organization:143906318',
            commentary='Authorized test <text>', createdAt=1700000000000,
            publishedAt=1700000000000, lastModifiedAt=1700000000001,
            lifecycleState='PUBLISHED', content={'article': {'source':'https://example.com/news'}})


class LinkedInTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.calls=[]; self.now=time.time()
        self.config=dict(client_id='fixture-client',client_secret='PRIVATE-CLIENT-SECRET',
                         redirect_uri='http://127.0.0.1:5000/linkedin/callback')
        def request(url, token=None, data=None, **kwargs):
            self.calls.append((url,token,data))
            if url.endswith('/accessToken'):
                return dict(access_token='PRIVATE-TOKEN',refresh_token='PRIVATE-REFRESH',
                            expires_in=3600,refresh_token_expires_in=31536000,
                            scope='r_organization_social,rw_organization_admin')
            if '/organizationAcls?' in url:
                return dict(elements=[dict(organization='urn:li:organization:143906318',
                    role='ADMINISTRATOR',state='APPROVED',**{'organization~':{'localizedName':'ASAP Test Lab'}})],paging={})
            return dict(elements=[dict(POST)],paging={'links':[{'rel':'next','href':'https://evil.example/steal'}]})
        self.request=request
        self.credentials=Credentials(self.root/'linkedin_credentials',lambda:self.config,request,lambda:self.now)
        self.oauth=OAuth(self.credentials,lambda:self.config,request,lambda:self.now)

    def session(self):
        return dict(authenticated=True,expires=self.now+3600,csrf='fixture-csrf')

    def grant(self):
        return self.credentials.save_grant(self.request('https://www.linkedin.com/oauth/v2/accessToken'))

    def test_image_posts_resolve_in_one_batch(self):
        connection=self.grant();calls=[]
        post=dict(POST,content={'multiImage':{'images':[{'id':'urn:li:image:fixture1','altText':'Test poster'},{'id':'urn:li:image:fixture2'}]}})
        def request(url,**kwargs):
            calls.append(url)
            if '/posts?' in url:return {'elements':[post]}
            return {'results':{'urn:li:image:fixture1':{'downloadUrl':'https://example.com/test1.png'},'urn:li:image:fixture2':{'downloadUrl':'https://example.com/test2.png'}}}
        provider=LinkedInProvider('143906318',connection,self.credentials,request=request)
        batch=provider.fetch(None)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(batch.posts[0]['media']),2)
        self.assertEqual(batch.posts[0]['media'][0]['alt'],'Test poster')

    def test_posting_scope_is_explicit_and_must_be_granted(self):
        from urllib.parse import urlparse,parse_qs
        session=self.session()
        url,nonce=self.oauth.begin(session)
        self.assertNotIn('w_organization_social',parse_qs(urlparse(url).query)['scope'][0])
        url,nonce=self.oauth.begin(session,publish=True)
        query=parse_qs(urlparse(url).query)
        self.assertIn('w_organization_social',query['scope'][0])
        with self.assertRaises(ValueError):self.oauth.finish(query['state'][0],nonce,'fixture-code')
        self.assertFalse(list(self.credentials.directory.glob('*.json')))
        original=self.oauth.request
        def grant_write(*args,**kwargs):
            result=original(*args,**kwargs)
            result['scope']+=',w_organization_social'
            return result
        self.oauth.request=grant_write
        url,nonce=self.oauth.begin(session,publish=True)
        self.oauth.finish(parse_qs(urlparse(url).query)['state'][0],nonce,'new-code')
        self.assertIn('w_organization_social',self.credentials.read(session['linkedin_choice']['connection'])['scope'])

    def test_oauth_binds_browser_state_session_and_consumes_code_once(self):
        session=self.session();url,nonce=self.oauth.begin(session);state=parse_qs(urlparse(url).query)['state'][0]
        self.assertNotIn('PRIVATE-CLIENT-SECRET',url)
        with self.assertRaises(ValueError):self.oauth.finish(state,'other-browser','code')
        self.assertEqual(self.calls,[])
        self.assertIs(self.oauth.finish(state,nonce,'code'),session)
        with self.assertRaises(ValueError):self.oauth.finish(state,nonce,'code')
        self.assertEqual(len(self.calls),1)
        self.oauth.pages(session);self.oauth.pages(session)
        self.assertEqual(len(self.calls),2) # Re-rendering selection never refetches.
        self.assertEqual(session['linkedin_choice']['pages'],{'143906318':'ASAP Test Lab'})

    def test_expired_denied_logged_out_or_missing_permissions_are_not_connected(self):
        for case in ('expired','denied','logout'):
            session=self.session();url,nonce=self.oauth.begin(session);state=parse_qs(urlparse(url).query)['state'][0]
            if case=='expired':self.oauth.pending[state]['expires']=self.now-1
            if case=='logout':session['authenticated']=False
            with self.assertRaises(ValueError):self.oauth.finish(state,nonce,'code',denied=case=='denied')
        self.assertEqual(self.calls,[])
        with self.assertRaises(ValueError):self.credentials.save_grant(dict(access_token='no-scope',expires_in=60,scope='r_basicprofile'))

    def test_one_pull_is_one_page_no_media_no_following_provider_links(self):
        connection=self.grant();self.calls.clear()
        provider=LinkedInProvider('143906318',connection,self.credentials,request=self.request)
        batch=provider.fetch(None)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(batch.posts[0]['text'],POST['commentary'])
        self.assertEqual(batch.posts[0]['links'],['https://example.com/news'])
        self.assertEqual(batch.posts[0]['media'],[])
        self.assertEqual(batch.checkpoint,str(POST['lastModifiedAt']))
        self.assertEqual(parse_qs(urlparse(self.calls[0][0]).query)['count'],['100'])
        conn=sqlite3.connect(':memory:')
        with closing(conn):
            with conn:store(conn,batch.posts);process_stored(conn);initialize(conn)
            with conn:store(conn,batch.posts);process_stored(conn)
            self.assertEqual(len(load_posts(conn)),1)
            self.assertEqual(publishable(conn),[])

    def test_refresh_is_once_and_preserves_absolute_refresh_expiry(self):
        connection=self.grant();value=self.credentials.read(connection)
        original=value['refresh_expires_at'];value['expires_at']=self.now-1;self.credentials.save(connection,value)
        self.calls.clear()
        self.assertEqual(self.credentials.access_token(connection),'PRIVATE-TOKEN')
        self.assertEqual(self.credentials.access_token(connection),'PRIVATE-TOKEN')
        self.assertEqual(len(self.calls),1)
        self.assertLessEqual(self.credentials.read(connection)['refresh_expires_at'],original)
        self.credentials.invalidate(connection)
        with self.assertRaises(ReconnectRequired):self.credentials.access_token(connection)
        self.assertEqual(len(self.calls),1)

    def test_401_blocks_subsequent_requests_and_429_is_not_retried(self):
        connection=self.grant(); calls=[]
        def unauthorized(*a,**kw):calls.append(1);raise HTTPError('https://api.linkedin.com',401,'denied',{},None)
        provider=LinkedInProvider('143906318',connection,self.credentials,request=unauthorized)
        with self.assertRaises(HTTPError):provider.fetch(None)
        with self.assertRaises(ReconnectRequired):provider.fetch(None)
        self.assertEqual(len(calls),1)
        connection=self.grant()
        def limited(*a,**kw):calls.append(1);raise HTTPError('https://api.linkedin.com',429,'limited',{'Retry-After':'60'},None)
        provider=LinkedInProvider('143906318',connection,self.credentials,request=limited)
        with self.assertRaises(HTTPError):provider.fetch(None)
        self.assertEqual(len(calls),2)

    def test_mismatched_organization_and_path_injection_rejected(self):
        connection=self.grant()
        provider=LinkedInProvider('999',connection,self.credentials,request=self.request)
        with self.assertRaises(ValueError):provider.fetch(None)
        with self.assertRaises(ValueError):LinkedInProvider('143906318','../../secrets',self.credentials)
        with self.assertRaises(ValueError):LinkedInProvider('https://evil.example',connection,self.credentials)

    def test_real_http_oauth_selection_fetch_and_approval_visibility(self):
        db=self.root/'store.sqlite3';config=self.root/'sources.json'
        config.write_text(json.dumps({'sources':[{'platform':'linkedin','enabled':False}]}))
        with closing(sqlite3.connect(db)) as conn:
            with conn:store(conn,[]);process_stored(conn);initialize(conn)
        def loader(path):
            sources=load_sources(path)
            for source in sources:
                source.provider.credentials=self.credentials;source.provider.request=self.request
            return sources
        runtime=AppRuntime(db,config,loader=loader)
        server=make_server(db,'fixture-password',port=0,runtime=runtime,linkedin_oauth=self.oauth)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.config['redirect_uri']='http://127.0.0.1:'+str(server.server_port)+'/linkedin/callback'
        cookies={}
        def http(path,data=None,callback=False):
            conn=HTTPConnection('127.0.0.1',server.server_port)
            sent={k:v for k,v in cookies.items() if not callback or k.startswith('asap_linkedin_')}
            headers={'Cookie':'; '.join(k+'='+v for k,v in sent.items())}
            body=urlencode(data).encode() if data is not None else None
            if body is not None:headers['Content-Type']='application/x-www-form-urlencoded'
            conn.request('POST' if data is not None else 'GET',path,body,headers)
            result=conn.getresponse();text=result.read().decode();status=result.status;location=result.getheader('Location')
            for key,value in result.getheaders():
                if key.lower()=='set-cookie':
                    parsed=SimpleCookie();parsed.load(value)
                    cookies.update({k:v.value for k,v in parsed.items()})
            self.last_headers=dict(result.getheaders())
            conn.close();return status,text,location
        _,login,_=http('/login')
        self.assertIn("form-action 'self' https://www.linkedin.com;",self.last_headers['Content-Security-Policy'])
        csrf=re.search('name="csrf" value="([^"]+)"',login)[1]
        self.assertEqual(http('/login',{'csrf':csrf,'password':'fixture-password'})[0],303)
        _,admin,_=http('/admin?view=sources&source_form=add&provider=linkedin')
        self.assertIn('Authenticate',admin);self.assertNotIn('access pending',admin.lower())
        csrf=re.search('name="csrf" value="([^"]+)"',admin)[1]
        self.assertEqual(http('/linkedin/connect',{'csrf':'bad'})[0],403)
        status,_,url=http('/linkedin/connect',{'csrf':csrf});self.assertEqual(status,303)
        state=parse_qs(urlparse(url).query)['state'][0]
        self.assertEqual(http('/linkedin/callback?'+urlencode({'state':state,'code':'fixture-code'}),callback=True)[0],200)
        self.assertEqual(len(self.calls),1) # Only code exchange; no hidden Page or post fetch.
        self.assertEqual(http('/linkedin/pages',{'csrf':csrf})[0],303)
        self.assertEqual(len(self.calls),2)
        _,choices,_=http('/linkedin/choose');self.assertIn('ASAP Test Lab',choices)
        self.assertEqual(http('/linkedin/select',{'csrf':csrf,'organization':'999'})[0],400)
        self.assertEqual(http('/linkedin/select',{'csrf':csrf,'organization':'143906318'})[0],303)
        saved=runtime.read_config()['sources'][0]
        self.assertFalse(saved['enabled']);self.assertEqual(saved['interval_seconds'],1800)
        runtime.tick();self.assertEqual(len(self.calls),2)
        result=runtime.fetch_now('linkedin:143906318')
        self.assertEqual(result['status'],'ok');self.assertEqual(result['new'],1)
        self.assertEqual(len(self.calls),3)
        _,review,_=http('/admin?view=pending')
        self.assertIn(html.escape(POST['commentary']),review)
        self.assertNotIn(POST['commentary'],http('/feed')[1])
        self.assertIn('>Approve</button>',review)
        self.assertNotIn('Administrator access only',review)
        self.assertEqual(http('/action',{'csrf':csrf,'platform':'linkedin','post_id':POST['id'],'action':'approve'})[0],303)
        published=http('/feed')[1]
        self.assertIn(html.escape(POST['commentary']),published)
        self.assertIn('ASAP Test Lab',published)
        self.assertIn('data-platform="linkedin"',published)
        self.assertNotIn('/action',published)
        self.assertNotIn('PRIVATE-TOKEN',published)
        self.assertIn('src="/feed"',http('/embed-demo')[1])
        self.assertEqual(http('/action',{'csrf':csrf,'platform':'linkedin','post_id':POST['id'],'action':'withdraw'})[0],303)
        self.assertNotIn(html.escape(POST['commentary']),http('/feed')[1])
        for path in ('/admin?view=sources','/admin?view=pending','/linkedin/choose'):
            text=http(path)[1]
            for secret in ('PRIVATE-TOKEN','PRIVATE-CLIENT-SECRET','PRIVATE-REFRESH'):
                self.assertNotIn(secret,text)
        with self.assertRaises(ValueError):configure_source(runtime.read_config(),dict(provider='linkedin',account='999'))
        with self.assertRaises(ValueError):configure_source(runtime.read_config(),dict(account='143906318',interval_seconds='1',page_size='100'),'linkedin:143906318')


if __name__=='__main__':unittest.main()
