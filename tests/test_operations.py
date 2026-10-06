"""FR-1/7/10: operational polling, allowlisted jobs and test-account boundaries."""
from contextlib import closing
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from src.app_runtime import AppRuntime
from src.dev_tools import DevTools, BlueskyTestPublisher
from src.polling import PollingSource, poll_due
from src.providers import FetchBatch
from src.manual_demos import demo_posts
from src.store_poc import store, process_stored
from src.web_editorial import initialize, publishable


class FakeProvider:
    platform='bluesky'
    account='asaptestlab.bsky.social'
    key='bluesky:'+account
    def __init__(self):self.calls=0
    def fetch(self,checkpoint):
        self.calls+=1
        p=next(p for p in demo_posts() if p['platform']=='bluesky')
        return FetchBatch([p,p],str(self.calls))


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'store.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn:
            store(conn,[]);process_stored(conn);initialize(conn)
        self.provider=FakeProvider()
        self.config=Path(self.temp.name)/'polling.local.json'
        self.config.write_text(json.dumps({'sources':[dict(platform='bluesky',account=self.provider.account,enabled=False,interval_seconds=1800)]}))
        def loader(path):
            row=json.loads(path.read_text())['sources'][0]
            return [PollingSource(self.provider,row['interval_seconds'],row['enabled'])]
        self.runtime=AppRuntime(self.db,self.config,loader=loader)
        self.addCleanup(self.runtime.stop)

    def test_runtime_config_changes_counts_and_manual_fetch_disabled(self):
        """Verifies FR-1/7: enable/interval/disable apply immediately; fetched vs new."""
        self.runtime.tick(0);self.assertEqual(self.provider.calls,0)
        config=self.runtime.read_config();config['sources'][0].update(enabled=True,interval_seconds=1800)
        self.runtime.save_config(config);self.runtime.tick(0)
        row=self.runtime.snapshot()[0]
        self.assertEqual((row['fetched_count'],row['new_count']),(2,1))
        config['sources'][0]['interval_seconds']=3;self.runtime.save_config(config)
        self.runtime.tick(2);self.assertEqual(self.provider.calls,1)
        self.runtime.tick(3);self.assertEqual(self.provider.calls,2)
        config['sources'][0]['enabled']=False;self.runtime.save_config(config)
        self.runtime.tick(6);self.assertEqual(self.provider.calls,2)
        result=self.runtime.fetch_now('bluesky');self.assertEqual(result['new'],0)
        with closing(sqlite3.connect(self.db)) as conn:self.assertEqual(publishable(conn),[])

    def test_fetch_now_queue_and_worker_shutdown(self):
        """Verifies FR-1/7: app-owned queue starts/stops without another process."""
        self.assertTrue(self.runtime.request_fetch('bluesky'))
        self.assertFalse(self.runtime.request_fetch('bluesky'))
        self.runtime.start()
        deadline=time.monotonic()+3
        while self.provider.calls==0 and time.monotonic()<deadline:time.sleep(.02)
        self.assertEqual(self.provider.calls,1)
        self.runtime.stop();self.assertFalse(self.runtime.running)
        with self.assertRaises(ValueError):self.runtime.request_fetch('linkedin')

    def test_regression_jobs_execute_existing_tests_and_persist(self):
        """Verifies FR-10: actual allowlisted subprocess test run with persisted output."""
        tools=DevTools(self.runtime,enabled=True)
        with self.assertRaises(ValueError):tools.submit('powershell arbitrary command')
        tools.submit('filter');tools.thread.join(30)
        row=tools.history()[0]
        self.assertEqual(row['status'],'PASS');self.assertIn('Ran ',row['output']);self.assertGreater(row['duration'],0)
        self.assertEqual(DevTools(self.runtime).history()[0]['id'],row['id'])
        with self.assertRaises(ValueError):DevTools(self.runtime).submit('all')

    def test_jobs_timeout_redaction_and_concurrency(self):
        """Verifies FR-10: timeout handling, secret masking and concurrent-run refusal."""
        tools=DevTools(self.runtime,enabled=True,timeout=1)
        tools.active=True
        with self.assertRaises(ValueError):tools.submit('all')
        tools.active=False
        with patch.dict(os.environ,{'ASAP_ADMIN_PASSWORD':'SYNTHETIC_PRIVATE_VALUE'}),patch('src.dev_tools.subprocess.run',side_effect=subprocess.TimeoutExpired('allowlisted',1,output=b'SYNTHETIC_PRIVATE_VALUE')):
            tools.submit('all');tools.thread.join(5)
            row=tools.history()[0]
            self.assertEqual(row['status'],'TIMEOUT');self.assertNotIn('SYNTHETIC_PRIVATE_VALUE',row['output'])

    def test_explicit_test_account_is_required_and_identity_checked(self):
        """Verifies FR-10: publisher never derives target from retrieval account."""
        calls=[]
        def transport(url,data,token=None):
            calls.append((url,data))
            if url.endswith('createSession'):
                return dict(handle='asaptestlab.bsky.social',did='did:plc:test',accessJwt='test-session')
            return dict(uri='at://did:plc:test/app.bsky.feed.post/unique')
        with patch('src.dev_tools.credentials',return_value=('','')):
            with self.assertRaises(ValueError):BlueskyTestPublisher(transport).publish('test')
        self.assertEqual(calls,[])
        with patch('src.dev_tools.credentials',return_value=('asaptestlab.bsky.social','test-app-password')):
            result=BlueskyTestPublisher(transport).publish('Unique test text')
            self.assertEqual(result['uri'],'at://did:plc:test/app.bsky.feed.post/unique')
        with patch('src.dev_tools.credentials',return_value=('wrong.bsky.social','test-app-password')):
            with self.assertRaises(ValueError):BlueskyTestPublisher(transport).publish('test')
        self.assertEqual(len(calls),3)

    def test_mocked_e2e_stores_exact_candidate_without_approval(self):
        """Verifies FR-1/2/3/4/10: publish→fetch→exact candidacy, never approval."""
        provider=self.provider
        class Publisher:
            def publish(inner,text):
                def fetch(checkpoint):
                    p=next(p for p in demo_posts() if p['platform']=='bluesky')
                    p.update(text=text,post_id='at://did:plc:test/app.bsky.feed.post/e2e')
                    return FetchBatch([p],'new')
                provider.fetch=fetch
                return dict(uri='at://did:plc:test/app.bsky.feed.post/e2e',url='https://bsky.app/profile/asaptestlab.bsky.social/post/e2e')
        with patch('src.dev_tools.credentials',return_value=(provider.account,'test-only')):
            tools=DevTools(self.runtime,enabled=True,publisher=Publisher())
            tools.submit('e2e-bluesky');tools.thread.join(5)
            self.assertEqual(tools.history()[0]['status'],'PASS')
            from src.console_ui import render_console
            from html import escape
            html=render_console([],[],dict(accent='#215e95',font_size=16,show_origin=1),self.runtime.read_config(),
                dict(csrf='test-csrf'),'testing',escape,lambda *args:'',self.runtime,tools)
            self.assertIn('View Bluesky post',html)
            self.assertNotIn('test-only',html)
            with closing(sqlite3.connect(self.db)) as conn:self.assertEqual(publishable(conn),[])


    def test_http_operations_are_authenticated_allowlisted_and_csrf_protected(self):
        """Verifies FR-7/10: browser controls cannot bypass login, CSRF or job allowlist."""
        import http.cookiejar
        import re
        import threading
        from urllib.request import build_opener, HTTPCookieProcessor, Request
        from urllib.parse import urlencode
        from urllib.error import HTTPError
        from src.web_app import make_server
        self.runtime.start()
        server=make_server(self.db,'local-test',port=0,runtime=self.runtime,dev_enabled=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)
        client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def get(path):return client.open(base+path).read().decode()
        def post(path,fields):return client.open(Request(base+path,data=urlencode(fields).encode())).read().decode()
        with self.assertRaises(HTTPError) as error:post('/fetch',dict(platform='bluesky',csrf='invalid'))
        self.assertEqual(error.exception.code,403)
        login=get('/admin');nonce=re.search('name="csrf" value="([^"]+)"',login).group(1)
        admin=post('/login',dict(csrf=nonce,password='local-test'))
        nonce=re.search('name="csrf" value="([^"]+)"',admin).group(1)
        self.assertIn('Polling Worker',admin)
        with self.assertRaises(HTTPError):post('/dev-task',dict(csrf=nonce,test_id='arbitrary command'))
        self.assertEqual(server.devtools.history(),[])
        post('/fetch',dict(csrf=nonce,platform='bluesky'))
        deadline=time.monotonic()+3
        while not self.provider.calls and time.monotonic()<deadline:time.sleep(.02)
        self.assertEqual(self.provider.calls,1)
        self.assertIn('Live source status',get('/admin?view=sources'))
        self.assertIn('Run All Regression Tests',get('/admin?view=testing'))


    def test_fetch_now_and_interval_changes_preserve_rate_limit_cooldown(self):
        """Verifies FR-1/7: manual fetch and short intervals cannot bypass HTTP 429."""
        from urllib.error import HTTPError
        def limited(checkpoint):
            self.provider.calls+=1
            raise HTTPError('https://provider.test/feed',429,'rate limited',{'Retry-After':'60'},None)
        self.provider.fetch=limited
        config=self.runtime.read_config();config['sources'][0].update(enabled=True,interval_seconds=3)
        self.runtime.save_config(config);self.runtime.tick(0)
        config['sources'][0]['interval_seconds']=1;self.runtime.save_config(config);self.runtime.tick(2)
        with closing(sqlite3.connect(self.db)) as conn:
            result=poll_due(conn,[PollingSource(self.provider,1,True)],3,force=True)
            self.assertEqual(result[0]['status'],'not_due')
            self.assertEqual(conn.execute('SELECT next_poll_at FROM source_poll_state').fetchone()[0],60)
        self.assertEqual(self.provider.calls,1)
