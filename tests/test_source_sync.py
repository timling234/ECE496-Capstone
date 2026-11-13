"""Targeted lifecycle synchronization checks using simulated provider responses."""
import copy
import sqlite3
import unittest
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
                payload=dict(p['raw'],commentary='Updated research seminar announcement',lastModifiedAt=2)
                return {'results':{p['post_id']:payload}}
        provider=Provider();source=PollingSource(provider,1800,True)
        result=poll_due(conn,[source],100,force=True)[0]
        self.assertEqual(result['updated'],1);self.assertEqual(items(conn)[0]['editorial_status'],'needs review');self.assertEqual(publishable(conn),[])
        decide(conn,p['platform'],p['post_id'],'approve')
        provider.state='error';result=poll_due(conn,[source],200,force=True)[0]
        self.assertEqual(result['unchecked'],1);self.assertEqual(len(publishable(conn)),1)
        provider.state='gone';result=poll_due(conn,[source],300,force=True)[0]
        self.assertEqual(result['unavailable'],1);self.assertTrue(items(conn)[0]['source_unavailable']);self.assertEqual(publishable(conn),[])
        provider.state='edit';result=poll_due(conn,[source],400,force=True)[0]
        self.assertFalse(items(conn)[0]['source_unavailable']);self.assertEqual(publishable(conn),[])

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
