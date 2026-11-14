"""Targeted lifecycle synchronization checks using simulated provider responses."""
import copy
import sqlite3
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from src.providers import FetchBatch
from src.polling import poll_due, PollingSource
from src.store_poc import store, process_stored
from src.web_editorial import initialize, items, decide, publishable
from src.manual_demos import demo_posts


class SourceSyncTests(unittest.TestCase):
    def test_edit_unavailable_and_recovery(self):
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        p=copy.deepcopy(demo_posts()[0]);p.update(platform='linkedin',account_id='123',post_id='urn:li:share:1')
        p['raw']={'id':p['post_id'],'author':'urn:li:organization:123','commentary':p['text'],'lifecycleState':'PUBLISHED','publishedAt':1,'lastModifiedAt':1}
        store(conn,[p]);process_stored(conn);conn.commit();initialize(conn);decide(conn,p['platform'],p['post_id'],'approve')
        class Credentials:
            def access_token(self,_):return 'mock-only'
        class Provider:
            key='linkedin:123';platform='linkedin';account='123';label='Mock';connection='mock';credentials=Credentials();supports_post_lookup=True
            state='edit'
            def fetch(self,checkpoint):return FetchBatch([],checkpoint)
            def request(self,url,token=None):
                if self.state=='error':raise HTTPError(url,403,'forbidden',{},None)
                if self.state=='gone':return {'results':{},'errors':{p['post_id']:{'status':404}}}
                if self.state=='repost_gone' and 'viewContext=READER' in url:
                    return {'results':{},'errors':{'urn:li:ugcPost:999':{'status':404}}}
                payload=dict(p['raw'],commentary='Updated research seminar announcement',lastModifiedAt=2)
                if self.state=='repost_gone':payload.update(commentary='',reshareContext={'root':'urn:li:ugcPost:999','parent':'urn:li:ugcPost:999'})
                return {'results':{p['post_id']:payload}}
        provider=Provider();source=PollingSource(provider,1800,True)
        with patch('src.source_profile.refresh') as refresh_profile:
            result=poll_due(conn,[source],100)[0]
        self.assertTrue(refresh_profile.call_args.kwargs['force'])
        self.assertEqual(result['updated'],1);self.assertEqual(items(conn)[0]['editorial_status'],'needs review');self.assertEqual(publishable(conn),[])
        decide(conn,p['platform'],p['post_id'],'approve')
        provider.state='error';result=poll_due(conn,[source],200,force=True)[0]
        self.assertEqual(result['unchecked'],1);self.assertEqual(len(publishable(conn)),1)
        provider.state='gone';result=poll_due(conn,[source],300,force=True)[0]
        self.assertEqual(result['unavailable'],1);self.assertEqual(len(publishable(conn)),1)
        task=next(q for q in items(conn) if q['metadata'].get('deletion_sync'))
        from src.ai_automation import analyze
        self.assertEqual(analyze(None,[task])[0]['recommendation'],'approve')
        poll_due(conn,[source],350,force=True)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM deletion_tasks').fetchone()[0],1)
        decide(conn,task['platform'],task['post_id'],'reject')
        self.assertEqual(len(publishable(conn)),1)
        provider.state='edit';poll_due(conn,[source],400,force=True)
        self.assertFalse(any(q['metadata'].get('deletion_sync') for q in items(conn)))
        with self.assertRaises(ValueError):decide(conn,task['platform'],task['post_id'],'approve')
        provider.state='repost_gone';result=poll_due(conn,[source],500,force=True)[0]
        self.assertEqual(result['unavailable'],1);self.assertEqual(len(publishable(conn)),1)
        task=next(q for q in items(conn) if q['metadata'].get('deletion_sync'))
        from src.console_ui import render_console
        from src.web_app import esc,card
        from src.web_editorial import presentation,bulk_action
        rendered=render_console(items(conn),[],presentation(conn),{'sources':[]},{'csrf':'fixture'},'pending',esc,card)
        self.assertIn('Deletion sync requested',rendered)
        bulk_action(conn,[(task['platform'],task['post_id'])],'approve',actor='ai:fixture')
        self.assertEqual(publishable(conn),[])
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0],0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM deletion_tasks WHERE status='approved'").fetchone()[0],1)



    def test_bounded_bluesky_lookup_and_x_errors(self):
        from src.source_sync import lookup
        from src.providers import BlueskyProvider, XProvider
        from pathlib import Path
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        originals=[]
        for i in range(30):
            p=copy.deepcopy(demo_posts()[0]);p.update(platform='bluesky',account_id='did:plc:mock',post_id='at://did:plc:mock/app.bsky.feed.post/'+str(i));originals.append(p)
        store(conn,originals);process_stored(conn);conn.commit();initialize(conn)
        calls=[]
        def transport(url):
            calls.append(url)
            return {'feed':[]} if 'getAuthorFeed?' in url else {'posts':[]}
        provider=BlueskyProvider('did:plc:mock',transport=transport)
        result=poll_due(conn,[PollingSource(provider,1800,True)],1,force=True)[0]
        self.assertEqual(len(calls),2);self.assertEqual(result['unavailable'],25);self.assertEqual(result['unchecked'],5)
        x=XProvider('123',Path('/unused'),transport=lambda *a:{'errors':[{'resource_id':'1','type':'https://api.twitter.com/2/problems/resource-not-found'},{'resource_id':'2','type':'not-authorized'}]},token_getter=lambda:'mock')
        found,gone=lookup(x,[dict(post_id='1'),dict(post_id='2')])
        self.assertEqual(gone,['1']);self.assertEqual(found,[])
