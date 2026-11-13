"""Focused reshare contract: no original-author authorization or fake fallback."""
import copy
import sqlite3
import unittest
from unittest.mock import Mock
from src.linkedin import LinkedInProvider,normalize
from src.linkedin_reposts import hydrate
from src.duplicates import exact_text_groups
from src.store_poc import store,process_stored
from src.web_editorial import initialize,items,decide,publishable
from src.feed_ui import feed_body
from src.web_app import esc,safe_url

ROOT='urn:li:ugcPost:42'
ORIGINAL=dict(id=ROOT,author='urn:li:person:other',commentary='A real research seminar announcement.',publishedAt=1700000000000,lifecycleState='PUBLISHED',content={'media':{'id':'urn:li:image:fixture'}},**{'author~':{'name':'Research Author'}})
RESHARE=dict(id='urn:li:ugcPost:55',author='urn:li:organization:123',commentary='',publishedAt=1800000000000,lifecycleState='PUBLISHED',reshareContext={'parent':ROOT,'root':ROOT})

class ReshareTests(unittest.TestCase):
    def provider(self,allowed):
        def request(url,**kw):
            if '/images?' in url:return {'results':{'urn:li:image:fixture':{'downloadUrl':'https://example.org/photo.jpg'}}}
            return {'results':{ROOT:copy.deepcopy(ORIGINAL)},'errors':{}} if allowed else {'results':{},'errors':{ROOT:{'status':403}}}
        return LinkedInProvider('123','a'*32,Mock(),label='Test Organization',request=Mock(side_effect=request))

    def test_original_repost_and_multiple_repost_sources(self):
        ordinary=normalize(dict(ORIGINAL,author=RESHARE['author']),'123','Test Organization')
        self.assertFalse(ordinary['metadata']['is_repost']);self.assertEqual(ordinary['metadata']['attribution'],{})
        provider=self.provider(True);post=hydrate(provider,[copy.deepcopy(RESHARE)],'only-A-token')[0]
        md=post['metadata']
        self.assertEqual((md['author_name'],md['source_account_name']),('Research Author','Test Organization'))
        self.assertEqual(post['created_at'],normalize(ORIGINAL,'123')['created_at'])
        self.assertNotEqual(post['created_at'],md['reposted_at'])
        self.assertEqual(len(post['media']),1);self.assertEqual(provider.request.call_count,2)
        other=copy.deepcopy(post);other['post_id']='urn:li:ugcPost:56';other['account_id']='456';other['metadata']['source_account_name']='Second Organization'
        groups=exact_text_groups([post,other]);self.assertEqual(len(groups),1)
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        store(conn,[post,other]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
        decide(conn,'linkedin',post['post_id'],'approve')
        result=publishable(conn);self.assertEqual(len(result),1);self.assertEqual(len(result[0]['metadata']['repost_sources']),2)
        html=feed_body(result,{'show_origin':1},esc,safe_url)
        self.assertIn('Test Organization reposted',html);self.assertIn('Research Author',html);self.assertIn('Second Organization',html)

    def test_permission_denied_is_not_fabricated_or_publishable(self):
        provider=self.provider(False);post=hydrate(provider,[copy.deepcopy(RESHARE)],'only-A-token')[0]
        self.assertEqual(provider.request.call_count,1)
        self.assertEqual(post['metadata']['original_resolution'],'permission_denied')
        self.assertFalse(post['text']);self.assertEqual(post['media'],[]);self.assertIsNone(post['metadata'].get('original_published_at'))
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        store(conn,[post]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
        with self.assertRaises(ValueError):decide(conn,'linkedin',post['post_id'],'approve')
        self.assertEqual(publishable(conn),[])
