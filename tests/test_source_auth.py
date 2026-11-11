"""Local-only authentication badges are independent of polling or public access."""
from pathlib import Path
import tempfile
import unittest
from src.linkedin import Credentials
from src.source_auth import authentication


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.connection='c'*32

    def source(self,platform,grant):
        Credentials(self.root/(platform+'_credentials')).save(self.connection,grant)
        return dict(platform=platform,account='fixture',connection_id=self.connection,enabled=False)

    def test_verified_x_is_green_even_with_polling_off_and_refreshable_expiry(self):
        s=self.source('x',dict(access_token='fixture',expires_at=200))
        self.assertEqual(authentication(s,self.root,100),'Authenticated')
        self.assertEqual(authentication(s,self.root,300),'Reconnect required')
        s=self.source('x',dict(access_token='old',expires_at=0,refresh_token='private'))
        self.assertEqual(authentication(s,self.root,300),'Authenticated')
        s['error_code']=401
        self.assertEqual(authentication(s,self.root,300),'Reconnect required')
        s=self.source('x',dict(access_token='new',expires_at=900,authenticated_at=500))
        s.update(error_code=401,last_attempt_at=400)
        self.assertEqual(authentication(s,self.root,600),'Authenticated')
        s['last_attempt_at']=550
        self.assertEqual(authentication(s,self.root,600),'Reconnect required')

    def test_linkedin_refresh_expiry_and_revocation(self):
        s=self.source('linkedin',dict(access_token='old',expires_at=0,refresh_token='private',refresh_expires_at=200))
        self.assertEqual(authentication(s,self.root,100),'Authenticated')
        self.assertEqual(authentication(s,self.root,300),'Reconnect required')
        s=self.source('linkedin',dict(access_token='current',expires_at=999,revoked=True))
        self.assertEqual(authentication(s,self.root,100),'Reconnect required')

    def test_public_bluesky_does_not_claim_authentication(self):
        s=dict(platform='bluesky',account='fixture',enabled=False)
        self.assertEqual(authentication(s,self.root),'Public access')
        s=self.source('bluesky',dict(identity_only=True,sub='fixture',authenticated_at=100))
        self.assertEqual(authentication(s,self.root),'Authenticated')
        s['account']='someone-else'
        self.assertEqual(authentication(s,self.root),'Reconnect required')

    def test_missing_malformed_grants_and_plain_x_tokens_are_not_oauth_proof(self):
        self.assertEqual(authentication(dict(platform='x',account='fixture',token_file='any'),self.root),'Not authenticated')
        s=dict(platform='x',account='fixture',connection_id=self.connection)
        self.assertEqual(authentication(s,self.root),'Reconnect required')
        Credentials(self.root/'x_credentials').save(self.connection,[])
        self.assertEqual(authentication(s,self.root),'Reconnect required')
        s['connection_id']='../../other-workspace'
        self.assertEqual(authentication(s,self.root),'Reconnect required')
