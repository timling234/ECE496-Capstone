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
        self.assertIn('Test Organization',html);self.assertIn('Research Author',html)
        self.assertIn('photo.jpg',html);self.assertNotIn('<iframe',html)
        self.assertIn('data-read-more',html)

    def test_permission_denied_allows_manual_native_embed_but_not_ai_approval(self):
        provider=self.provider(False);post=hydrate(provider,[copy.deepcopy(RESHARE)],'only-A-token')[0]
        self.assertEqual(provider.request.call_count,1)
        self.assertEqual(post['metadata']['original_resolution'],'permission_denied')
        self.assertFalse(post['text']);self.assertEqual(post['media'],[]);self.assertIsNone(post['metadata'].get('original_published_at'))
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        store(conn,[post]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
        self.assertEqual(publishable(conn),[])
        from src.publishing_policy import recommendation
        self.assertEqual(recommendation(post)['recommendation'],'needs_review')
        decide(conn,'linkedin',post['post_id'],'approve')
        self.assertEqual(len(publishable(conn)),1)
        from src.linkedin_embed import embed_url
        self.assertFalse(embed_url(dict(post,post_id='urn:li:ugcPost:55?injected=1')))
        self.assertFalse(embed_url(dict(post,platform='x')))
        html=feed_body(publishable(conn),{'show_origin':1},esc,safe_url)
        self.assertNotIn('<iframe',html)
        self.assertIn('Original content is unavailable',html)
        self.assertNotIn('Research Author',html)

    def test_public_embed_text_cache_and_model_input_preserve_editorial_state(self):
        import tempfile,json
        from pathlib import Path
        from src.embed_review import prepare,RepostText,review_text
        from src.review_ai import LocalModel
        from src.publishing_policy import recommendation
        html='<article data-test-id="feed-reshare-content" data-attributed-urn="'+ROOT+'"><div data-test-id="feed-reshare-content__entity-lockup"><a data-tracking-control-name="public_post_embed_reshare_feed-actor-name">Research Author</a><time>1mo</time></div><img src="https://media.licdn.com/fixture.jpg"><p data-test-id="feed-reshare-content__commentary">A polished research update.<br>Seminar on Friday.</p></article>'
        post=hydrate(self.provider(False),[copy.deepcopy(RESHARE)],'token')[0]
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'test.sqlite3'
            with sqlite3.connect(db) as conn:
                store(conn,[post]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
                decide(conn,'linkedin',post['post_id'],'approve',actor='human')
            reader=Mock(return_value=html)
            prepare(db,[post],reader=reader)
            with sqlite3.connect(db) as conn:
                current=items(conn)[0]
                self.assertEqual(current['editorial_status'],'approved')
                self.assertEqual(current['text'],'')  # API provenance stays untouched.
                self.assertIn('Seminar on Friday.',review_text(current))
                self.assertIsNone(recommendation(current))
                rendered=feed_body([current],{'show_origin':1},esc,safe_url)
                self.assertIn('Research Author',rendered);self.assertIn('fixture.jpg',rendered)
                self.assertIn('1mo',rendered);self.assertNotIn('<iframe',rendered)
                self.assertIn('data-read-more',rendered)
            prepare(db,[current],reader=reader);reader.assert_called_once()
            model=LocalModel('http://localhost:11434','fixture')
            model.generate=Mock(return_value=dict(recommendation='approve',reason='Substantive repost.'))
            self.assertEqual(model.review(current)['recommendation'],'approve')
            payload=json.loads(model.generate.call_args.args[1])
            self.assertIn('Seminar on Friday.',payload['text']);self.assertFalse(payload['media_reviewed'])
            current['metadata']['embed_review']['text']='Another test from bluesky'
            self.assertEqual(recommendation(current)['recommendation'],'reject')
            for invalid in (html.replace(ROOT,'urn:li:ugcPost:999'),html.split('</p>')[0]):
                parser=RepostText({ROOT});parser.feed(invalid);parser.close()
                with self.assertRaises(ValueError):parser.text()
