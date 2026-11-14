"""Focused checks for embed platform selection, real timestamps and interval bounds."""
import unittest
from html import escape
from src.feed_options import filter_posts,controls,feed_url
from src.source_config import configure_source
from run_polling import load_sources
import tempfile,json
from pathlib import Path

class FeedOptionsTests(unittest.TestCase):
    def test_selection_and_chronological_order(self):
        posts=[dict(platform='bluesky',post_id='old',created_at='2026-10-06T00:00:00Z',pinned=1),dict(platform='x',post_id='x',created_at='2026-11-14T10:00:00-05:00'),dict(platform='linkedin',post_id='li',created_at='2026-11-14T14:00:00+00:00')]
        self.assertEqual([p['post_id'] for p in filter_posts(posts,{})],['x','li','old'])
        self.assertEqual([p['post_id'] for p in filter_posts(posts,{'platforms':['linkedin,bluesky']})],['li','old'])
        self.assertEqual(filter_posts(posts,{'platforms':['none']}),[])
        self.assertEqual(feed_url('https://asap.surf/u/alice/feed',['x']),'https://asap.surf/u/alice/feed?platforms=x')
        rendered=controls('https://asap.surf/u/alice/feed',{'feed_layout':['separate']},escape)
        self.assertEqual(rendered.count('data-public-feed-frame'),3)
        for platform in ('x','bluesky','linkedin'):self.assertIn('/u/alice/feed?platforms='+platform,rendered)
        self.assertEqual(controls('https://asap.surf/feed',{},escape).count('data-public-feed-frame'),1)

    def test_linkedin_interval_180_is_valid(self):
        source=dict(platform='linkedin',account='123',connection_id='a'*32,interval_seconds=1800)
        config={'sources':[source]};fields=dict(account='123',interval_seconds='180')
        self.assertEqual(configure_source(config,fields,'linkedin:123')['interval_seconds'],180)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'polling.json';path.write_text(json.dumps({'sources':[dict(source,enabled=True)]}))
            self.assertEqual(load_sources(path)[0].interval_seconds,180)
        with self.assertRaises(ValueError):configure_source(config,dict(fields,interval_seconds='179'),'linkedin:123')
