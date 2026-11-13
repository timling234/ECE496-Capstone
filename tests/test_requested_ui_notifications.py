"""Small checks for explicit test policy, feed structure, and notification events."""
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import Mock
from src import notifications as n
from src.review_ai import LocalModel
from src.linkedin_text import encode,decode
from src.demo_content import sample_posts
from src.feed_ui import feed_body
from src.web_app import esc,safe_url


class RequestedChangesTests(unittest.TestCase):
    def test_explicit_mock_guard_and_plain_text(self):
        cases=json.loads((Path(__file__).parents[1]/'config/ai_judgment_cases.json').read_text())['cases']
        model=LocalModel('http://127.0.0.1:11434','mock')
        model.generate=Mock(return_value=dict(recommendation='approve',reason='An ordinary research update.'))
        text=next(c['text'] for c in cases if c['id']=='explicit-long-mock-declaration')
        self.assertEqual(model.review(dict(text=text,platform='linkedin',created_at=None))['recommendation'],'reject')
        model.generate.assert_not_called()
        normal='Our paper evaluates software testing methods and includes a new benchmark.'
        self.assertEqual(model.review(dict(text=normal,platform='linkedin',created_at=None))['recommendation'],'approve')
        model.generate.assert_called_once()
        for text in ['Research (LLMs) | Chroma #SREGym @user [test] {body} \\ * _ ~',next(c['text'] for c in cases if c['id']=='msrg-original-3')]:self.assertEqual(decode(encode(text)),text)
        self.assertEqual(decode(r'{hashtag|\#ASAPTest}'),'#ASAPTest')
        from src.web_editorial import initialize,create_announcement,decide
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close);initialize(conn)
        blocked=create_announcement(conn,'ASAP MOCK POST — FOR TEST PURPOSE ONLY\nA plausible seminar update.')
        with self.assertRaises(ValueError):decide(conn,'manual',blocked,'approve')

    def test_feed_pages_and_notification_deduplication(self):
        html=feed_body(sample_posts('https://asap.surf'),dict(show_origin=1),esc,safe_url)
        self.assertEqual(html.count('<div class="news-page">'),2)
        for marker in ('news-prev','news-next','news-dots','news-author','news-share','Read more'):self.assertIn(marker,html)
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        n.save_settings(conn,True,'email','test@example.org',{e:True for e in n.EVENTS})
        for event in ('reauth','ai_review','duplicates'):
            n.queue_event(conn,event,'same-item','same-version')
            n.queue_event(conn,event,'same-item','same-version')
        conn.commit();sent=[]
        self.assertEqual(n.deliver_pending(conn,sender=lambda *args,**kw:sent.append(kw['event']),now=1),3)
        self.assertEqual(sent,['ai_review','reauth','duplicates'])
        n.queue_event(conn,'reauth','same-item','renewed-connection');conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE event='reauth'").fetchone()[0],2)
