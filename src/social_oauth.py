"""Read-only X OAuth and Bluesky identity-only OAuth.

Bluesky public author feeds require no token. We request only `atproto`, verify
DID -> hosted PDS -> issuer, and discard tokens after authentication. Hosted
bsky.social accounts (did:plc) are supported; arbitrary federated URLs are never
fetched. See docs/social_auth.md for protocol references and deliberate limits.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from .linkedin import Credentials, ReconnectRequired
from .source_connections import merge_bluesky, remember

LOCK = threading.RLock()
X_SCOPES = 'tweet.read users.read offline.access'
BSKY = 'https://bsky.social'


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def challenge(verifier):
    return b64(hashlib.sha256(verifier.encode()).digest())


def destination(url):
    """Fixed operators only, including Bluesky's hosted PDS shard domain."""
    p = urlparse(url)
    fixed = p.hostname in ('api.x.com', 'bsky.social', 'plc.directory')
    shard = bool(re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.host\.bsky\.network', p.hostname or ''))
    if p.scheme != 'https' or p.port not in (None, 443) or p.username or p.password or p.fragment or not (fixed or shard):
        raise ValueError('Unsupported authorization server')


def transport(method, url, *, data=None, headers=None, auth=None):
    destination(url)
    try:
        # Never redirect bearer tokens, authorization codes, or client credentials.
        with requests.request(method, url, data=data, headers=headers, auth=auth,
                              timeout=(5, 20), allow_redirects=False, stream=True) as response:
            raw = bytearray()
            for chunk in response.iter_content(8192):
                raw.extend(chunk)
                if len(raw) > 1048576:
                    raise ValueError('Provider response too large')
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError('Invalid provider response')
            return response.status_code, payload, dict(response.headers)
    except (requests.RequestException, ValueError, OSError):
        raise ValueError('Provider connection failed; return to Sources and try again later') from None


def require_ok(result):
    status, payload, headers = result
    if not 200 <= status < 300 or payload.get('error') or payload.get('errors'):
        # No provider error body/token ever enters logs or HTML.
        raise HTTPError('https://provider.invalid', status, 'Provider request failed',
                        {k: v for k, v in headers.items() if k.lower() in ('retry-after', 'x-rate-limit-reset')}, None)
    return payload


def origin():
    value = os.environ.get('ASAP_PUBLIC_URL', 'https://asap.surf').rstrip('/')
    p = urlparse(value)
    if p.scheme != 'https' or not p.netloc or p.path or p.query or p.fragment or p.username or p.password:
        raise ValueError('Configure a public HTTPS ASAP_PUBLIC_URL')
    return value


class XCredentials(Credentials):
    def __init__(self, directory, request=transport, clock=time.time):
        super().__init__(directory, clock=clock)
        self.http = request

    def access_token(self, connection):
        with LOCK:
            grant = self.read(connection)
            if grant.get('revoked'):
                raise ReconnectRequired('Reconnect X')
            if grant.get('expires_at', 0) > self.clock() + 60:
                return grant['access_token']
            if not grant.get('refresh_token'):
                raise ReconnectRequired('Reconnect X')
            try:
                payload = x_token({'grant_type':'refresh_token', 'refresh_token':grant['refresh_token']}, self.http)
                validate_x_token(payload)
            except HTTPError as error:
                if error.code==429 or error.code>=500:
                    raise
                raise ReconnectRequired('Reconnect X') from None
            except Exception:
                raise ReconnectRequired('Reconnect X') from None
            grant.update(payload, expires_at=self.clock()+int(payload['expires_in']))
            self.save(connection, grant)
            return grant['access_token']


def x_token(data, http):
    client, secret = os.environ.get('X_CLIENT_ID', ''), os.environ.get('X_CLIENT_SECRET', '')
    if not client or not secret:
        raise ValueError('X website authorization is not configured by the administrator yet')
    return require_ok(http('POST', 'https://api.x.com/2/oauth2/token', data=data, auth=(client, secret)))


def validate_x_token(payload):
    if (str(payload.get('token_type', '')).lower() != 'bearer' or not payload.get('access_token')
            or not set(X_SCOPES.split()).issubset(str(payload.get('scope', '')).split())
            or not 0 < int(payload.get('expires_in', 0)) <= 31536000):
        raise ValueError('X did not grant the requested read permissions')


def dpop(key, url, nonce=''):
    nums = key.public_key().public_numbers()
    public = {'kty':'EC', 'crv':'P-256', 'x':b64(nums.x.to_bytes(32,'big')), 'y':b64(nums.y.to_bytes(32,'big'))}
    now = int(time.time())
    claims = dict(jti=secrets.token_urlsafe(24), htm='POST', htu=url, iat=now, exp=now+60)
    if nonce:
        claims['nonce'] = nonce
    compact = lambda value: b64(json.dumps(value,separators=(',',':')).encode())
    encoded = compact({'typ':'dpop+jwt', 'alg':'ES256', 'jwk':public})+'.'+compact(claims)
    r, s = decode_dss_signature(key.sign(encoded.encode(), ec.ECDSA(hashes.SHA256())))
    return encoded+'.'+b64(r.to_bytes(32,'big')+s.to_bytes(32,'big'))


class SocialOAuth:
    def __init__(self, http=transport, clock=time.time):
        self.http, self.clock = http, clock
        self.lock = threading.RLock()
        self.pending = {}

    def bluesky_metadata(self):
        return dict(client_id=origin()+'/bluesky/client-metadata.json', client_name='ASAP',
                    client_uri=origin(), application_type='web', scope='atproto',
                    redirect_uris=[origin()+'/bluesky/callback'], response_types=['code'],
                    grant_types=['authorization_code'], token_endpoint_auth_method='none',
                    dpop_bound_access_tokens=True)

    def bsky_post(self, pending, endpoint, data):
        url = BSKY+'/oauth/'+endpoint
        for attempt in range(2):
            result = self.http('POST', url, data={'client_id':self.bluesky_metadata()['client_id'], **data},
                               headers={'DPoP':dpop(pending['key'], url, pending.get('nonce',''))})
            status, payload, headers = result
            nonce = next((v for k,v in headers.items() if k.lower()=='dpop-nonce'), '')
            if nonce:
                pending['nonce'] = nonce
            # A protocol-required nonce challenge is the only automatic retry.
            if attempt == 0 and status in (400,401) and payload.get('error')=='use_dpop_nonce' and nonce:
                continue
            return require_ok(result)

    def begin(self, platform, session, workspace, owner):
        if platform not in ('x','bluesky'):
            raise ValueError('Unsupported provider')
        if platform=='x' and not (os.environ.get('X_CLIENT_ID') and os.environ.get('X_CLIENT_SECRET')):
            raise ValueError('X website authorization is not configured by the administrator yet')
        state, verifier, cookie = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        pending = dict(platform=platform, session=session, workspace=workspace, owner=owner,
                       verifier=verifier, cookie=cookie, expires=self.clock()+600)
        args = dict(response_type='code', redirect_uri=origin()+'/'+platform+'/callback',
                    state=state, code_challenge=challenge(verifier), code_challenge_method='S256')
        if platform=='x':
            url = 'https://x.com/i/oauth2/authorize?'+urlencode(dict(args, client_id=os.environ['X_CLIENT_ID'], scope=X_SCOPES))
        else:
            pending['key'] = ec.generate_private_key(ec.SECP256R1())
            par = self.bsky_post(pending, 'par', dict(args, scope='atproto'))
            if not isinstance(par.get('request_uri'),str) or not par['request_uri'].startswith('urn:ietf:params:oauth:request_uri:'):
                raise ValueError('Invalid authorization response')
            if int(par.get('expires_in',0))<=0:
                raise ValueError('Expired authorization request')
            # PAR URI expires before use; an already-started consent screen may
            # take longer (e.g. MFA). Keep our login-bound callback window 10 min.
            url = BSKY+'/oauth/authorize?'+urlencode(dict(client_id=self.bluesky_metadata()['client_id'], request_uri=par['request_uri']))
        with self.lock:
            self.pending = {s:p for s,p in self.pending.items() if p['expires']>self.clock()}
            # One outstanding request per login and platform, globally bounded.
            self.pending = {s:p for s,p in self.pending.items() if not (p['session'] is session and p['platform']==platform)}
            if len(self.pending)>=200:
                raise ValueError('Too many authorization requests; try later')
            self.pending[state] = pending
        return url, cookie

    def consume(self, platform, state, cookie, owner):
        with self.lock:
            p = self.pending.get(state)
            if (not p or p['platform']!=platform or p['owner']!=owner
                    or not cookie or not secrets.compare_digest(cookie,p['cookie'])):
                raise ValueError('Return to Sources in the account that started this connection')
            del self.pending[state]
        if (p['expires']<=self.clock() or not p['session'].get('authenticated')
                or p['session']['expires']<=self.clock()):
            raise ValueError('Connection expired; start again from Sources')
        return p

    def complete(self, pending, code, issuer=''):
        platform = pending['platform']
        if platform=='x':
            payload = x_token(dict(grant_type='authorization_code', code=code,
                                   redirect_uri=origin()+'/x/callback', code_verifier=pending['verifier']), self.http)
            validate_x_token(payload)
            user = require_ok(self.http('GET','https://api.x.com/2/users/me',
                                       headers={'Authorization':'Bearer '+payload['access_token']})).get('data',{})
            account = str(user.get('id',''))
            if not re.fullmatch(r'[0-9]{1,30}',account):
                raise ValueError('X account could not be verified')
            label = str(user.get('username') or account)[:256]
            credentials = XCredentials(pending['workspace'].db.parent/'x_credentials')
            payload['expires_at'] = self.clock()+int(payload['expires_in'])
            payload['authenticated_at'] = self.clock()
        else:
            if issuer!=BSKY:
                raise ValueError('Bluesky authorization issuer did not match')
            payload = self.bsky_post(pending,'token',dict(grant_type='authorization_code',code=code,
                                    redirect_uri=origin()+'/bluesky/callback',code_verifier=pending['verifier']))
            account = payload.get('sub','')
            if (not re.fullmatch(r'did:plc:[a-z2-7]{24}',account)
                    or payload.get('token_type','').lower()!='dpop' or not payload.get('access_token')
                    or 'atproto' not in str(payload.get('scope','')).split()):
                raise ValueError('Bluesky identity could not be verified')
            doc = require_ok(self.http('GET','https://plc.directory/'+account))
            if doc.get('id')!=account:
                raise ValueError('Bluesky identity did not match')
            service = next((s for s in doc.get('service',[]) if s.get('id') in ('#atproto_pds',account+'#atproto_pds')
                            and s.get('type')=='AtprotoPersonalDataServer'), {})
            pds = service.get('serviceEndpoint','')
            destination(pds)
            parsed = urlparse(pds)
            if parsed.path not in ('','/') or parsed.query or not (parsed.hostname=='bsky.social' or parsed.hostname.endswith('.host.bsky.network')):
                raise ValueError('Use a bsky.social hosted account; other servers can be added as public sources')
            resource = require_ok(self.http('GET',pds.rstrip('/')+'/.well-known/oauth-protected-resource'))
            if (resource.get('resource','').rstrip('/')!=pds.rstrip('/') or BSKY not in resource.get('authorization_servers',[])):
                raise ValueError('Bluesky account authorization server did not match')
            metadata = require_ok(self.http('GET',BSKY+'/.well-known/oauth-authorization-server'))
            if metadata.get('issuer')!=BSKY:
                raise ValueError('Bluesky issuer metadata did not match')
            handle=next((a[5:] for a in doc.get('alsoKnownAs',[]) if isinstance(a,str) and re.fullmatch(r'at://[a-z0-9.-]+',a)),None)
            if handle:
                resolved=require_ok(self.http('GET',BSKY+'/xrpc/com.atproto.identity.resolveHandle?'+urlencode({'handle':handle})))
                if resolved.get('did')!=account:raise ValueError('Bluesky handle did not match the authorized identity')
            label = handle or account
            # Identity-only auth ends here. No need to retain access/refresh tokens.
            payload = dict(sub=account, authenticated_at=self.clock(), scope='atproto', identity_only=True, aliases=[handle] if handle else [])
            credentials = Credentials(pending['workspace'].db.parent/'bluesky_credentials')
        runtime = pending['workspace'].runtime
        if not runtime:
            raise ValueError('Source runtime required')
        with runtime.lock:
            config = runtime.read_config()
            source = next((s for s in config['sources'] if s['platform']==platform and s.get('account')==account),None)
            if platform=='bluesky' and handle:
                old=next((s for s in config['sources'] if s['platform']==platform and s.get('account')==handle),None)
                source=old or source
            if source is None:
                source=next((s for s in config['sources'] if s['platform']==platform and s.get('draft')),None)
            connection = source.get('connection_id') if source else None
            connection = connection or secrets.token_hex(16)
            credentials.save(connection,payload)
            if source is None:
                source = dict(platform=platform,account=account,enabled=False,interval_seconds=1800,page_size=5)
                config['sources'].append(source)
            # Consume a draft even when reauth resolves to an existing account.
            config['sources']=[s for s in config['sources'] if not (s['platform']==platform and s.get('draft') and s is not source)]
            source.pop('draft',None)
            if not source.get('account'):source['account']=account
            source.update(connection_id=connection,label=label)
            if platform=='bluesky':
                source=merge_bluesky(config,account,handle,connection) or source
            remember(source,runtime.config_path.parent)
            runtime.save_config(config)
        return source
