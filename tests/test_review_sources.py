"""FR-1/3/5/6/7/9: independent source cards, review groups and per-account controls."""
import copy
import html
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from src.duplicates import exact_text_groups
from src.manual_demos import demo_posts
from src.store_poc import store, process_stored, load_posts
from src.web_editorial import initialize, items, decide, publishable
from src.web_app import card
from src.console_ui import render_console
from src.source_config import configure_source, identity
from src.app_runtime import AppRuntime
from src.polling import PollingSource
from src.providers import FetchBatch


class ReviewSourceTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.addCleanup(self.conn.close)
        posts=demo_posts()
        for p in posts:
            p['text']='Date: October 15, 2026' if p['post_id']!='C' else 'Date: October 16, 2026'
        next(p for p in posts if p['platform']=='bluesky')['text']='Date: October 15, 2026  '
        store(self.conn,posts);process_stored(self.conn);self.conn.commit();initialize(self.conn)
        self.original=self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall()
        self.config={'sources':[dict(platform='bluesky',account='test.bsky.social',interval_seconds=1800,enabled=False)]}

    def render(self,query=None):
        return render_console(items(self.conn),[],dict(accent='#215e95',font_size=14,show_origin=1),
            self.config,dict(csrf='test-csrf'),'pending',lambda v:html.escape(str(v or ''),quote=True),card,query=query)

    def test_different_dates_not_exact_and_all_source_fields_independent(self):
        """Verifies FR-2/3/5: dates remain significant; grouping never aliases source fields."""
        posts=load_posts(self.conn)
        groups=exact_text_groups(posts)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(next(iter(groups.values()))),2)
        self.assertFalse(any(('x','C') in group for group in groups.values()))
        before=copy.deepcopy(posts);exact_text_groups(posts);self.assertEqual(posts,before)
        rendered=self.render()
        for p in posts:
            self.assertEqual(rendered.count('data-post-id="'+html.escape(p['post_id'],quote=True)+'"'),1)
            self.assertIn(html.escape(p['post_url'],quote=True),rendered)
        self.assertIn('October 15',rendered);self.assertIn('October 16',rendered)
        self.assertEqual(self.original,self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall())

    def test_both_filters_groups_first_without_repeated_cards(self):
        """Verifies FR-5/7: independent checkboxes, numbered warning groups before ordinary items."""
        both=self.render(dict(filters_set=['1'],needs_review=['on'],duplicates=['on']))
        self.assertLess(both.index('class="duplicate-group"'),both.index('class="ordinary-review"'))
        self.assertIn('Group #1',both);self.assertNotIn('>Duplicate Groups</a>',both)
        self.assertEqual(both.count('data-post-id='),3)
        needs=self.render(dict(filters_set=['1'],needs_review=['on']))
        self.assertNotIn('class="duplicate-group"',needs);self.assertEqual(needs.count('data-post-id='),3)
        dup=self.render(dict(filters_set=['1'],duplicates=['on']))
        self.assertEqual(dup.count('data-post-id='),2);self.assertNotIn('class="ordinary-review"',dup)

    def test_atomic_selection_rejection_reasons_withdrawal_and_explicit_switch(self):
        """Verifies FR-6/7/9: reject alternatives atomically; withdrawal never restores them."""
        decide(self.conn,'x','A','approve')
        records=items(self.conn);other=next(p for p in records if p['platform']=='bluesky')
        self.assertEqual(other['editorial_status'],'rejected');self.assertEqual(other['editorial_reason'],'duplicate_not_selected')
        self.assertEqual([p['post_id'] for p in publishable(self.conn)],['A'])
        self.assertIn('PUBLISHED',card(next(p for p in records if p['post_id']=='A'),'csrf'))
        self.assertIn('REJECTED',card(other,'csrf'))
        decide(self.conn,'x','A','withdraw')
        self.assertEqual(next(p for p in items(self.conn) if p['platform']=='bluesky')['editorial_status'],'rejected')
        decide(self.conn,'bluesky',other['post_id'],'approve')
        self.assertEqual(len(publishable(self.conn)),1)
        self.assertEqual(self.original,self.conn.execute('SELECT * FROM posts ORDER BY platform,post_id').fetchall())
        self.assertTrue(self.conn.execute("SELECT 1 FROM editorial_actions WHERE action='duplicate_not_selected'").fetchone())

    def test_editorial_failure_rolls_back_all_members_and_audit(self):
        """Verifies FR-6/7: a failed group action cannot leave partial approvals/rejections."""
        self.conn.execute("CREATE TRIGGER deny_reason BEFORE INSERT ON editorial_reasons BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):decide(self.conn,'x','A','approve')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM editorial_decisions').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM editorial_actions').fetchone()[0],0)

    def test_explicit_empty_duplicate_state_and_nav(self):
        """Verifies FR-7: empty warning section remains visible with either checkbox selection."""
        self.conn.execute('DELETE FROM duplicate_candidates');self.conn.commit()
        self.assertIn('No possible duplicates detected',self.render())
        self.assertIn('No possible duplicates detected',self.render(dict(filters_set=['1'],duplicates=['on'])))
        result=self.render()
        positions=[result.index('>'+name+'</a>') for name in ['Dashboard','Review Queue','Sources','Testing / Development','Settings','Published','Rejected']]
        self.assertEqual(positions,sorted(positions))
        self.assertIn('Public Feed ↗',result);self.assertIn('Embedding Preview ↗',result)

    def test_source_add_edit_validation_and_credential_reference_preservation(self):
        """Verifies FR-1/7: shared provider-aware configuration, unique accounts, no secret input."""
        first=configure_source(self.config,dict(provider='x',account='123',interval_seconds='3',enabled='on',page_size='5'))
        first['token_file']='local-private-token-reference.txt'
        configure_source(self.config,dict(account='456',interval_seconds='1800',enabled='',page_size='10',token_file='injected'),identity(first))
        self.assertEqual(first['token_file'],'local-private-token-reference.txt')
        with self.assertRaises(ValueError):configure_source(self.config,dict(provider='x',account='456'))
        with self.assertRaises(ValueError):configure_source(self.config,dict(provider='linkedin',enabled='on'))
        with self.assertRaises(ValueError):configure_source(self.config,dict(provider='x',account='not-numeric'))

    def test_merged_source_rows_and_provider_aware_edit_do_not_expose_tokens(self):
        """Verifies FR-7: Add/Edit panel replaces duplicated bulk form, secrets remain private."""
        self.config['sources'].append(dict(platform='x',account='123',token_file='DO_NOT_SHOW_THIS_REFERENCE',enabled=False,page_size=5))
        def render(query):return render_console([],[],{},self.config,dict(csrf='test'),'sources',lambda v:html.escape(str(v or ''),quote=True),card,query=query)
        result=render({})
        self.assertIn('+ Add Source',result);self.assertIn('✎',result);self.assertNotIn('Source configuration</h2>',result)
        self.assertNotIn('DO_NOT_SHOW_THIS_REFERENCE',result)
        self.assertIn('Account / Handle',render(dict(source_form=['add'],provider=['bluesky'])))
        x=render(dict(edit_source=['x:123']))
        self.assertIn('Account / User ID',x);self.assertIn('X page size (5–100)',x)
        self.assertNotIn('DO_NOT_SHOW_THIS_REFERENCE',x)

    def test_multiple_accounts_fetch_by_key_not_platform_priority(self):
        """Verifies FR-1/7: correct account queue/status and explicit ambiguity refusal."""
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'store.sqlite3';config=Path(temp)/'sources.json'
            config.write_text(json.dumps({'sources':[]}))
            class Provider:
                platform='bluesky'
                def __init__(self,account):self.account=account;self.key='bluesky:'+account;self.calls=0
                def fetch(self,checkpoint):self.calls+=1;return FetchBatch([],checkpoint)
            a,b=Provider('a.bsky.social'),Provider('b.bsky.social')
            runtime=AppRuntime(db,config,loader=lambda path:[PollingSource(a,1800),PollingSource(b,1800)])
            runtime.fetch_now(b.key)
            self.assertEqual((a.calls,b.calls),(0,1))
            with self.assertRaises(ValueError):runtime.fetch_now('bluesky')
