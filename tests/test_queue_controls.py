"""Focused checks for queue filtering and continuous review without repeat inference."""
import sqlite3
import unittest
from html import escape
from unittest.mock import Mock
from tests import test_ai_automation as fixtures
from src.console_ui import render_console
from src.publishing_policy import recommendation
from src.web_editorial import edit_announcement


class QueueControlsTests(unittest.TestCase):
    setUp=fixtures.AutomationTests.setUp
    add=fixtures.AutomationTests.add
    configure=fixtures.AutomationTests.configure
    finish=fixtures.AutomationTests.finish
    def test_placeholder_rule(self):
        self.assertEqual(recommendation({'text':'Another test from bluesky'})['recommendation'],'reject')
        for text in ['test2','This is a test.']:
            self.assertEqual(recommendation({'text':text})['recommendation'],'reject')
        self.assertIsNone(recommendation({'text':'Our software testing paper was accepted. Join our seminar.'}))

    def test_continuous_review_does_not_repeat_unchanged_advice(self):
        post_id=self.add();self.configure(False,False)
        self.reviewer.tick(self.db);self.model.review.assert_not_called()
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT INTO ai_queue_preferences VALUES (1,1)')
        self.reviewer.next_queue_check={};self.reviewer.tick(self.db);self.finish()
        self.model.review.assert_called_once()
        self.reviewer.next_queue_check={};self.reviewer.tick(self.db);self.finish()
        self.model.review.assert_called_once()
        with sqlite3.connect(self.db) as conn:edit_announcement(conn,post_id,'Updated seminar announcement: tomorrow at 4 PM.','alice')
        self.reviewer.next_queue_check={};self.reviewer.tick(self.db);self.finish()
        self.assertEqual(self.model.review.call_count,2)

    def test_platform_filter_and_fetch_order(self):
        posts=[]
        for platform,created,fetched in [('x','2026-01-03','2026-01-01'),('bluesky','2026-01-02','2026-01-03'),('linkedin','2026-01-01','2026-01-02')]:
            posts.append(dict(platform=platform,post_id=platform,created_at=created,fetched_at=fetched,editorial_status='pending',group=None))
        def render(query):
            return render_console(posts,[],{'accent':'#123456','font_size':14,'show_origin':1},{'sources':[]},{'csrf':'test'},'pending',escape,lambda p,c:'CARD_'+p['platform'],query=query)
        html=render({'platforms_set':['1'],'provider_x':['on'],'provider_linkedin':['on'],'sort':['fetched_at'],'direction':['asc']})
        self.assertNotIn('CARD_bluesky',html)
        self.assertLess(html.index('CARD_x'),html.index('CARD_linkedin'))
        html=render({})
        self.assertLess(html.index('CARD_x'),html.index('CARD_bluesky'))
        self.assertLess(html.index('CARD_bluesky'),html.index('CARD_linkedin'))
