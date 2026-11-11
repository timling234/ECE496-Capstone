"""No downloads: exercise local inventory, streamed pull, preference boundaries."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock,patch
from src.ai_settings import ModelManager,settings,save,initialize,CATALOG
from src.review_ai import LocalModel,POLICY


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/'prefs.sqlite3'
        self.manager=ModelManager(LocalModel('http://localhost:11434','fixture'))
        self.manager.recover(self.db)

    def session(self,response):
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False)
        session.get.return_value=response;session.post.return_value=response
        return session

    def test_inventory_excludes_cloud_and_remote_models_and_caches(self):
        response=Mock(status_code=200)
        response.iter_content.return_value=[json.dumps({'models':[{'name':'fixture:local','size':100},{'name':'gemma4:cloud','size':0},{'name':'hidden-remote','remote_host':'https://example.com','size':0}]}).encode()]
        session=self.session(response)
        with patch('src.ai_settings.requests.Session',return_value=session):
            self.assertEqual(self.manager.installed(),{'fixture:local':100})
            self.assertEqual(self.manager.installed(),{'fixture:local':100})
        session.get.assert_called_once()
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertFalse(session.trust_env)

    def test_preferences_require_installed_model_and_are_database_local(self):
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(settings(conn,'fixture')['auto_approve'],1)
            with self.assertRaises(ValueError):save(conn,dict(model='cloud',policy=POLICY),{'fixture':1})
            save(conn,dict(model='fixture',policy=POLICY,auto_approve='on',batch_limit=5),{'fixture':1})
            self.assertEqual(settings(conn)['model'],'fixture');self.assertEqual(settings(conn)['auto_reject'],0)
        with closing(sqlite3.connect(':memory:')) as other:self.assertEqual(settings(other,'default')['auto_approve'],1)

    def test_streamed_model_download_finishes_then_is_available_for_apply(self):
        name=next(iter(CATALOG))
        self.manager.installed=Mock(side_effect=[{}, {name:1234}])
        response=Mock(status_code=200)
        response.iter_lines.return_value=[b'{"status":"pulling","completed":50,"total":100}',b'{"status":"success"}']
        session=self.session(response)
        with patch('src.ai_settings.requests.Session',return_value=session):
            job=self.manager.download(self.db,name)
            self.assertTrue(self.manager.download_lock.acquire(timeout=3));self.manager.download_lock.release()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT status,progress FROM ai_model_downloads WHERE id=?',(job,)).fetchone(),('complete',100))
        self.assertEqual(session.post.call_args.kwargs['json'],{'model':name,'stream':True})
        self.assertFalse(session.post.call_args.kwargs['allow_redirects'])

    def test_failed_download_is_safe_and_releases_shared_slot(self):
        name=next(iter(CATALOG));self.manager.installed=Mock(return_value={})
        response=Mock(status_code=302);session=self.session(response)
        with patch('src.ai_settings.requests.Session',return_value=session):
            self.manager.download(self.db,name)
            self.assertTrue(self.manager.download_lock.acquire(timeout=3));self.manager.download_lock.release()
        with closing(sqlite3.connect(self.db)) as conn:self.assertEqual(conn.execute('SELECT status FROM ai_model_downloads').fetchone()[0],'error')

    def test_catalog_only_download_and_existing_model_does_not_pull_again(self):
        with self.assertRaises(ValueError):self.manager.download(self.db,'https://attacker.example/model')
        name=next(iter(CATALOG));self.manager.installed=Mock(return_value={name:100})
        self.assertIsNone(self.manager.download(self.db,name))
        self.manager.installed.return_value={};self.manager.download_lock.acquire()
        with self.assertRaises(ValueError):self.manager.download(self.db,name)
        self.manager.download_lock.release()
