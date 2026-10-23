"""FR-8: persistent candidate events, opt-in settings and isolated SMTP retries."""
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src import notifications as n
from src.store_poc import store, process_stored
from src.manual_demos import demo_posts


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'test.sqlite3'
        self.conn=sqlite3.connect(self.db);self.addCleanup(self.conn.close)
        store(self.conn,[]);process_stored(self.conn);self.conn.commit()
        self.sender=MagicMock()

    def enable(self):n.save_settings(self.conn,True,'email','admin@example.org')
    def ingest(self):
        with self.conn:store(self.conn,demo_posts());process_stored(self.conn)

    def test_new_candidates_and_repeated_fetch(self):
        """Verifies FR-8: each new candidate queues once; replay does not repeat."""
        self.enable();self.ingest();count=len(demo_posts())
        self.assertEqual(n.summary(self.conn)['pending'],count)
        self.ingest();self.assertEqual(n.summary(self.conn)['pending'],count)
        self.assertEqual(n.deliver_pending(self.conn,self.sender,now=10),count)
        self.assertEqual(n.deliver_pending(self.conn,self.sender,now=20),0)
        self.assertEqual(self.sender.call_count,count)

    def test_disabled_and_no_retrospective_delivery(self):
        """Verifies FR-8: disabled events and old candidates are not backfilled."""
        self.ingest();self.enable();self.ingest()
        self.assertEqual(n.summary(self.conn)['pending'],0)

    def test_rollback_and_restart(self):
        """Verifies FR-3/8: candidate event rolls back; committed outbox persists."""
        self.enable()
        self.conn.execute('BEGIN')
        store(self.conn,demo_posts());process_stored(self.conn)
        self.conn.rollback()
        self.assertEqual(n.summary(self.conn)['pending'],0)
        self.ingest()
        with closing(sqlite3.connect(self.db)) as reopened:
            self.assertEqual(n.summary(reopened)['pending'],len(demo_posts()))

    def test_retry_does_not_change_posts(self):
        """Verifies FR-8: failure persists sanitized type and retries after delay."""
        self.enable();self.ingest()
        before=self.conn.execute('SELECT * FROM posts').fetchall()
        bad=MagicMock(side_effect=RuntimeError('SECRET SMTP RESPONSE'))
        self.assertEqual(n.deliver_pending(self.conn,bad,now=10),0)
        self.assertEqual(n.summary(self.conn)['error'],'RuntimeError')
        self.assertEqual(n.deliver_pending(self.conn,self.sender,now=11),0)
        self.assertEqual(n.deliver_pending(self.conn,self.sender,now=70),len(demo_posts()))
        self.assertEqual(self.conn.execute('SELECT * FROM posts').fetchall(),before)
        self.assertNotIn('SECRET',str(self.conn.execute('SELECT * FROM notification_outbox').fetchall()))

    def test_settings_validation_and_paused_queue(self):
        """Verifies FR-8: only a valid email channel can be enabled; disable pauses."""
        for address in ('','bad','a@example.org\r\nBcc: bad@example.org','a@b.org,b@c.org'):
            with self.assertRaises(ValueError):n.save_settings(self.conn,True,'email',address)
        with self.assertRaises(ValueError):n.save_settings(self.conn,True,'sms','123')
        self.enable();self.ingest();n.save_settings(self.conn,False,'email','admin@example.org')
        self.assertEqual(n.deliver_pending(self.conn,self.sender,now=10),0)
        self.sender.assert_not_called()

    def test_filtered_posts_do_not_notify(self):
        """Verifies FR-4/8: only becoming a candidate creates a notification."""
        from src.relevance import mark_candidates
        self.enable()
        with self.conn:
            store(self.conn,demo_posts());mark_candidates(self.conn,demo_posts(),[lambda p:False])
        self.assertEqual(n.summary(self.conn)['pending'],0)
        with self.conn:process_stored(self.conn)
        self.assertEqual(n.summary(self.conn)['pending'],len(demo_posts()))

    def test_smtp_tls_and_credentials_do_not_enter_settings(self):
        """Verifies FR-8: authenticated TLS transport, injected environment secrets."""
        env={'ASAP_SMTP_HOST':'smtp.example.org','ASAP_SMTP_FROM':'asap@example.org','ASAP_SMTP_USERNAME':'user','ASAP_SMTP_PASSWORD':'test-secret'}
        with patch.dict('os.environ',env,clear=True),patch('src.notifications.smtplib.SMTP') as smtp:
            n.send_email('admin@example.org','bluesky','native-id')
            client=smtp.return_value.__enter__.return_value
            client.starttls.assert_called_once()
            client.login.assert_called_once_with('user','test-secret')
            message=client.send_message.call_args.args[0]
            self.assertEqual(message['To'],'admin@example.org')
            self.assertNotIn('test-secret',message.as_string())
        self.assertNotIn('password',n.settings(self.conn))

