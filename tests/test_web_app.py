"""Acceptance tests for FR-6/7/9/11 browser vertical slice and session protection."""
from contextlib import closing
import http.cookiejar
import re
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from urllib.parse import urlencode
from src.manual_demos import demo_posts
from src.store_poc import store, process_stored
from src.web_editorial import initialize, items, decide, publishable, create_announcement, edit_announcement, set_order, save_presentation, presentation
from src.web_app import make_server


class EditorialWebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'test.sqlite3'
        self.conn=sqlite3.connect(self.db);self.addCleanup(self.conn.close)
        store(self.conn,demo_posts());process_stored(self.conn);self.conn.commit();initialize(self.conn)
        self.original=self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall()
    def test_lifecycle_and_group_switch(self):
        """Verifies FR-6/7/9: explicit approvals, one duplicate copy and withdrawal."""
        self.assertEqual(publishable(self.conn),[])
        decide(self.conn,'x','C','approve');self.assertEqual(len(publishable(self.conn)),1)
        decide(self.conn,'x','C','withdraw');self.assertEqual(publishable(self.conn),[])
        decide(self.conn,'x','A','approve')
        b=next(p for p in items(self.conn) if p['platform']=='bluesky')
        decide(self.conn,'bluesky',b['post_id'],'approve')
        self.assertEqual([(p['platform'],p['post_id']) for p in publishable(self.conn)],[('bluesky',b['post_id'])])
        decide(self.conn,'bluesky',b['post_id'],'reject');self.assertEqual(publishable(self.conn),[])
        self.assertEqual(self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall(),self.original)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM editorial_actions').fetchone()[0],6)
    def test_changed_source_requires_review_and_reopen_persists(self):
        """Verifies FR-7/9: stored approval persists, changed content is not published."""
        decide(self.conn,'x','C','approve')
        with closing(sqlite3.connect(self.db)) as reopened:self.assertEqual(len(publishable(reopened)),1)
        posts=demo_posts();next(p for p in posts if p['post_id']=='C')['text']='Updated content'
        with self.conn:store(self.conn,posts);process_stored(self.conn)
        self.assertEqual(publishable(self.conn),[])
    def test_manual_announcement_is_pending_until_approved(self):
        """Verifies FR-11: manual creation and shared approval/withdrawal lifecycle."""
        identity=create_announcement(self.conn,'Team announcement')
        self.assertEqual(publishable(self.conn),[])
        decide(self.conn,'manual',identity,'approve')
        self.assertEqual(publishable(self.conn)[0]['text'],'Team announcement')
        decide(self.conn,'manual',identity,'withdraw');self.assertEqual(publishable(self.conn),[])
    def test_browser_auth_csrf_and_public_visibility(self):
        """Verifies FR-7/9: actual HTTP login, CSRF, approval and feed removal."""
        server=make_server(self.db,'test-only-password',port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)
        client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def get(path):return client.open(base+path).read().decode()
        def post(path,data):return client.open(Request(base+path,data=urlencode(data).encode())).read().decode()
        login=get('/admin');self.assertIn('Admin sign in',login)
        csrf=re.search('name="csrf" value="([^"]+)"',login).group(1)
        client.open(base+'/favicon.ico').close() # Browser request must not rotate login session.
        admin=post('/login',{'csrf':csrf,'password':'test-only-password'})
        self.assertIn('Pending / Needs Review',admin)
        self.assertIn('Source configuration',admin)
        csrf=re.search('name="csrf" value="([^"]+)"',admin).group(1)
        with self.assertRaises(HTTPError) as blocked:post('/action',{'platform':'x','post_id':'C','action':'approve','csrf':'bad'})
        self.assertEqual(blocked.exception.code,403)
        self.assertNotIn('Different update',get('/feed'))
        post('/action',{'platform':'x','post_id':'C','action':'approve','csrf':csrf})
        text=next(p['text'] for p in demo_posts() if p['post_id']=='C')
        self.assertIn(text,get('/feed'))
        post('/action',{'platform':'x','post_id':'C','action':'withdraw','csrf':csrf})
        self.assertNotIn(text,get('/feed'))
        post('/sources',{'csrf':csrf,'x_account':'123','x_interval':'120','x_enabled':'on','bluesky_account':'team.bsky.social','bluesky_interval':'300'})
        import json
        configured=json.loads((self.db.parent/'polling.local.json').read_text())
        self.assertEqual(configured['sources'][0]['interval_seconds'],120)
        self.assertTrue(configured['sources'][0]['enabled'])
        before=(self.db.parent/'polling.local.json').read_bytes()
        with self.assertRaises(HTTPError):post('/sources',{'csrf':csrf,'x_account':'bad','x_enabled':'on'})
        self.assertEqual(before,(self.db.parent/'polling.local.json').read_bytes())
        self.assertIn('<iframe',get('/embed-demo'))
        with client.open(base+'/feed') as response:self.assertIsNone(response.headers.get('X-Frame-Options'))
        post('/logout',{'csrf':csrf})
        self.assertIn('Admin sign in',get('/admin'))
    def test_manual_edit_order_and_presentation(self):
        """Verifies FR-6/9/11: edits require review; order/settings do not alter sources."""
        identity=create_announcement(self.conn,'Original announcement')
        decide(self.conn,'manual',identity,'approve')
        edit_announcement(self.conn,identity,'Revised announcement')
        self.assertEqual(publishable(self.conn),[])
        self.assertEqual(self.conn.execute('SELECT text FROM manual_versions').fetchone()[0],'Original announcement')
        decide(self.conn,'manual',identity,'approve');decide(self.conn,'x','C','approve')
        set_order(self.conn,'x','C',1)
        self.assertEqual(publishable(self.conn)[0]['post_id'],'C')
        snapshot=self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall()
        save_presentation(self.conn,'#112233',20,False)
        self.assertEqual(presentation(self.conn),dict(accent='#112233',font_size=20,show_origin=0))
        self.assertEqual(snapshot,self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall())
        with self.assertRaises(ValueError):save_presentation(self.conn,'red;display:none',20,True)

    def test_pin_overrides_newest_without_approving(self):
        """Verifies FR-6/9: manual pin changes order, never publication eligibility."""
        decide(self.conn,'x','C','pin');self.assertEqual(publishable(self.conn),[])
        decide(self.conn,'x','C','approve');decide(self.conn,'x','A','approve')
        self.assertEqual(publishable(self.conn)[0]['post_id'],'C')
        decide(self.conn,'x','C','unpin')
        self.assertFalse(next(p for p in items(self.conn) if p['post_id']=='C')['pinned'])

    def test_html_escapes_content_and_rejects_script_urls(self):
        """Verifies FR-7/9: untrusted source content cannot inject HTML/URLs."""
        from src.web_app import card
        p=demo_posts()[0];p['text']='<script>alert(1)</script>';p['post_url']='javascript:alert(1)'
        rendered=card(p)
        self.assertNotIn('<script>',rendered);self.assertNotIn('javascript:',rendered)
        self.assertIn('&lt;script&gt;',rendered)
