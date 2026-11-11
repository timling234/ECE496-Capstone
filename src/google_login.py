"""Google OIDC authorization code flow; minimal scopes, state, nonce and PKCE."""
import base64
import hashlib
import os
from urllib.parse import urlencode


class GoogleLogin:
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None):
        self.client_id = client_id if client_id is not None else os.environ.get('GOOGLE_CLIENT_ID', '')
        self.client_secret = client_secret if client_secret is not None else os.environ.get('GOOGLE_CLIENT_SECRET', '')
        self.redirect_uri = redirect_uri or os.environ.get('GOOGLE_REDIRECT_URI', '')

    @property
    def ready(self):
        return bool(self.client_id and self.client_secret and self.redirect_uri.startswith('https://'))

    def authorize(self, state, nonce, verifier):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(dict(
            client_id=self.client_id, redirect_uri=self.redirect_uri, response_type='code',
            scope='openid email profile', state=state, nonce=nonce,
            code_challenge=challenge, code_challenge_method='S256'))

    def exchange(self, code, verifier, nonce):
        import requests
        from google.auth.transport.requests import Request
        from google.oauth2.id_token import verify_oauth2_token
        # Tokens are neither logged nor persisted. TLS verification stays enabled.
        response = requests.post('https://oauth2.googleapis.com/token', data=dict(
            client_id=self.client_id, client_secret=self.client_secret, code=code,
            code_verifier=verifier, redirect_uri=self.redirect_uri, grant_type='authorization_code'), timeout=15)
        response.raise_for_status()
        claims = verify_oauth2_token(response.json()['id_token'], Request(), self.client_id)
        import hmac
        if not hmac.compare_digest(str(claims.get('nonce', '')), nonce):
            raise ValueError('Google nonce mismatch')
        return claims
