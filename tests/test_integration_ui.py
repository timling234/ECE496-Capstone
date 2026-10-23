"""FR-6/7/8/9: real HTTP settings, pin navigation and News embedding."""
from contextlib import closing
import http.cookiejar
import re
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from src.store_poc import store,process_stored
from src.manual_demos import demo_posts
from src.web_editorial import initialize,decide
from src.web_app import make_server
from src.notifications import settings


class IntegrationUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'test.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn:
            store(conn,demo_posts());process_stored(conn);initialize(conn)
        self.server=make_server(self.db,'test-password',port=0)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        login=self.get('/login')
        self.csrf=re.search('name="csrf" value="([^"]+)"',login).group(1)
        admin=self.post('/login',dict(csrf=self.csrf,password='test-password'))
        self.csrf=re.search('name="csrf" value="([^"]+)"',admin).group(1)
    def get(self,path):
        with self.client.open(self.base+path) as response:return response.read().decode()
    def post(self,path,data):
        with self.client.open(Request(self.base+path,data=urlencode(data).encode())) as response:return response.read().decode()

    def test_pin_stays_published_and_manual_order_removed(self):
        """Verifies FR-6/7: pin stays Published; old manual order is no longer active."""
        self.post('/action',dict(csrf=self.csrf,platform='x',post_id='C',action='approve'))
        published=self.get('/admin?view=approved')
        self.assertNotIn('Manual order',published);self.assertNotIn('Save order',published)
        with self.client.open(Request(self.base+'/action',data=urlencode(dict(csrf=self.csrf,platform='x',post_id='C',action='pin',return_view='approved')).encode())) as response:
            self.assertTrue(response.url.endswith('/admin?view=approved'))
            self.assertIn('Unpin',response.read().decode())
        with self.assertRaises(HTTPError) as error:self.post('/order',dict(csrf=self.csrf,platform='x',post_id='C',position=1))
        self.assertEqual(error.exception.code,410)

    def test_notification_settings_csrf_persistence(self):
        """Verifies FR-8: protected settings, valid email persistence, SMS disabled."""
        page=self.get('/admin?view=settings')
        self.assertIn('Notifications',page);self.assertIn('SMS — not available yet',page)
        with self.assertRaises(HTTPError) as error:self.post('/notifications',dict(csrf='bad',enabled='on',channel='email',recipient='admin@example.org'))
        self.assertEqual(error.exception.code,403)
        self.post('/notifications',dict(csrf=self.csrf,enabled='on',channel='email',recipient='admin@example.org'))
        with closing(sqlite3.connect(self.db)) as conn:self.assertEqual(settings(conn)['recipient'],'admin@example.org')
        self.assertIn('admin@example.org',self.get('/admin?view=settings'))

    def test_news_frame_only_contains_approved(self):
        """Verifies FR-9: horizontal feed iframe, no admin actions or pending posts."""
        self.assertNotIn('Different announcement',self.get('/feed'))
        self.post('/action',dict(csrf=self.csrf,platform='x',post_id='C',action='approve'))
        feed=self.get('/feed')
        self.assertIn('news-track',feed);self.assertIn('Different announcement',feed)
        self.assertNotIn('Select &amp;',feed);self.assertNotIn('/action',feed)
        mock=self.get('/embed-demo');self.assertIn('src="/feed"',mock);self.assertIn('mock-news',mock)
        with self.client.open(self.base+'/feed') as response:self.assertIsNone(response.headers.get('X-Frame-Options'))

