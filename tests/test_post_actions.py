"""Focused delete/refetch and bulk editorial checks; no provider requests."""
import json
import re
import unittest
import http.cookiejar
import threading
import sqlite3
import tempfile
from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from src.manual_demos import demo_posts
from src.web_editorial import initialize
from src.web_editorial import bulk_action, items, publishable, decide
from src.store_poc import store, process_stored
from src.web_app import make_server


class PostActionsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/'test.sqlite3'
        self.conn=sqlite3.connect(self.db);self.addCleanup(self.conn.close)
        store(self.conn,demo_posts());process_stored(self.conn);self.conn.commit();initialize(self.conn)

    def test_delete_refetch_and_bulk(self):
        original=next(p for p in items(self.conn) if (p['platform'],p['post_id'])==('x','C'))
        decide(self.conn,'x','C','approve')
        self.conn.execute('CREATE TABLE source_poll_state (platform TEXT,account TEXT,checkpoint TEXT,next_poll_at REAL)')
        self.conn.execute('INSERT INTO source_poll_state VALUES (?,?,?,?)',('x',original['account_id'],'999',123))
        self.conn.commit()
        self.assertEqual(bulk_action(self.conn,[['x','C']],'delete'),1)
        self.assertFalse(any(p['post_id']=='C' for p in items(self.conn)))
        self.assertEqual(self.conn.execute('SELECT checkpoint,next_poll_at FROM source_poll_state').fetchone(),(None,123))
        with self.conn:store(self.conn,[original]);process_stored(self.conn)
        fresh=next(p for p in items(self.conn) if p['post_id']=='C')
        self.assertEqual(fresh['editorial_status'],'pending')
        self.assertFalse(fresh['pinned'])
        keys=[[p['platform'],p['post_id']] for p in items(self.conn) if p['candidate_status']=='candidate']
        bulk_action(self.conn,keys,'approve')
        published=publishable(self.conn)
        groups=[p['group'] for p in published if p['group']]
        self.assertEqual(len(groups),len(set(groups)))
        bulk_action(self.conn,keys,'reject');self.assertEqual(publishable(self.conn),[])
        with self.assertRaises(ValueError):bulk_action(self.conn,[keys[0],['x','missing']],'delete')
        self.assertEqual(len(items(self.conn)),len(keys))

    def test_http_actions_and_selection(self):
        server=make_server(self.db,'test-only',port=0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)
        client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        login=client.open(base+'/admin').read().decode()
        csrf=re.search('name="csrf" value="([^"]+)"',login)[1]
        def post(data):return client.open(Request(base+'/posts-action',data=urlencode(data,doseq=True).encode()))
        client.open(Request(base+'/login',data=urlencode(dict(csrf=csrf,password='test-only')).encode())).close()
        html=client.open(base+'/admin?view=pending').read().decode()
        csrf=re.search('name="csrf" value="([^"]+)"',html)[1]
        for view in ('pending','approved','rejected'):
            page=client.open(base+'/admin?view='+view).read().decode()
            self.assertIn('id="post-bulk"',page)
        self.assertIn('aria-label="Delete post"',html)
        self.assertIn('form="post-bulk"',html)
        with self.assertRaises(HTTPError) as denied:post(dict(csrf='wrong',action='delete',post=json.dumps(['x','C'])))
        self.assertEqual(denied.exception.code,403)
        result=post(dict(csrf=csrf,action='delete',post=json.dumps(['x','C']),return_view='approved'))
        self.assertIn('view=approved',result.url)
        self.assertNotIn('data-post-id="C"',result.read().decode())
