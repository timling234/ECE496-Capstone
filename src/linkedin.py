"""LinkedIn organization OAuth and bounded, read-only Page ingestion."""
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .linkedin_text import decode as plain_text

SCOPES = {'r_organization_social', 'rw_organization_admin'}
# LinkedIn invalidates earlier grants when the requested scope set changes.
# Both connection entry points must use this same app-wide permission bundle.
AUTH_SCOPES = SCOPES | {'w_organization_social'}
LOCK = threading.RLock()


class ReconnectRequired(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(url, token=None, data=None, version='202610'):
    """Fixed destinations only; credentials never follow redirects or enter errors."""
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc not in ('api.linkedin.com', 'www.linkedin.com'):
        raise ValueError('Invalid LinkedIn destination')
    headers = {'Accept': 'application/json', 'X-Restli-Protocol-Version': '2.0.0',
               'LinkedIn-Version': version}
    if 'ids=List(' in url:headers['X-RestLi-Method']='BATCH_GET'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request = Request(url, headers=headers, data=urlencode(data).encode() if data is not None else None)
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError('Invalid LinkedIn response')
        return result
    except HTTPError as error:
        safe_headers = {key: error.headers[key] for key in ('Retry-After',)
                        if error.headers and key in error.headers}
        raise HTTPError('https://api.linkedin.com', error.code, 'LinkedIn request failed', safe_headers, None) from None
    except (URLError, OSError, ValueError):
        raise ValueError('LinkedIn connection failed; try again later') from None


def settings():
    values = {}
    path = os.environ.get('ASAP_LINKEDIN_APP_FILE')
    if not path:
        default = Path(__file__).resolve().parents[1]/'.tmp'/'linkedin-app.json'
        path = str(default) if default.exists() else None
    if path:
        try:
            values = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            raise ValueError('LinkedIn server configuration is unavailable') from None
    return {key: os.environ.get(env) or values.get(key, '') for key, env in (
        ('client_id', 'LINKEDIN_CLIENT_ID'), ('client_secret', 'LINKEDIN_CLIENT_SECRET'),
        ('redirect_uri', 'LINKEDIN_REDIRECT_URI'))}


def validate_settings(config):
    uri = urlparse(config.get('redirect_uri', ''))
    local = uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1')
    if (not config.get('client_id') or not config.get('client_secret') or
            (uri.scheme != 'https' and not local) or not uri.netloc or uri.username or
            uri.password or uri.query or uri.fragment or uri.path != '/linkedin/callback'):
        raise ValueError('Configure LinkedIn client ID, secret and the registered /linkedin/callback URL on the server')


class Credentials:
    def __init__(self, directory, config_getter=settings, request=transport, clock=time.time):
        self.directory = Path(directory)
        self.config_getter, self.request, self.clock = config_getter, request, clock

    def path(self, connection):
        if not re.fullmatch(r'[a-f0-9]{32}', str(connection)):
            raise ValueError('Invalid LinkedIn connection')
        return self.directory / (connection + '.json')

    def read(self, connection):
        try:
            return json.loads(self.path(connection).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise ReconnectRequired('Reconnect LinkedIn') from None

    def save(self, connection, value):
        with LOCK:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = self.path(connection)
            temporary = path.with_suffix('.tmp')
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream)
            os.replace(temporary, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

    def save_grant(self, payload):
        scopes = set(re.split(r'[ ,]+', payload.get('scope', '')))
        if not SCOPES.issubset(scopes) or not payload.get('access_token'):
            raise ValueError('LinkedIn did not grant the required Page permissions')
        connection = secrets.token_hex(16)
        value = dict(payload)
        value['authenticated_at'] = self.clock()
        value['expires_at'] = self.clock() + int(payload['expires_in'])
        value['refresh_expires_at'] = self.clock() + int(payload.get('refresh_token_expires_in', 0))
        self.save(connection, value)
        return connection

    def organization(self,connection,account,request=transport):
        """Resolve the selected organization once per grant, never from display guesses."""
        grant=self.read(connection)
        cached=grant.get('organizations',{}).get(account)
        if cached:return cached
        data=request('https://api.linkedin.com/rest/organizations/'+account,token=self.access_token(connection))
        if str(data.get('id'))!=account:raise ValueError('Organization identity mismatch')
        name=data.get('localizedName')
        if not name:
            names=(data.get('name') or {}).get('localized',{})
            name=next(iter(names.values()),None)
        if not isinstance(name,str) or not name.strip():raise ValueError('Organization name unavailable')
        profile=dict(id='urn:li:organization:'+account,name=name)
        with LOCK:
            grant=self.read(connection);grant.setdefault('organizations',{})[account]=profile;self.save(connection,grant)
        return profile

    def access_token(self, connection):
        # One refresh at most, shared across sources connected with this grant.
        with LOCK:
            value = self.read(connection)
            if value.get('revoked'):
                raise ReconnectRequired('Reconnect LinkedIn')
            if value.get('expires_at', 0) > self.clock() + 300:
                return value['access_token']
            if not value.get('refresh_token') or value.get('refresh_expires_at', 0) <= self.clock():
                raise ReconnectRequired('Reconnect LinkedIn')
            config = self.config_getter()
            validate_settings(config)
            try:
                payload = self.request('https://www.linkedin.com/oauth/v2/accessToken', data={
                    'grant_type': 'refresh_token', 'refresh_token': value['refresh_token'],
                    'client_id': config['client_id'], 'client_secret': config['client_secret']})
            except HTTPError as error:
                if error.code in (400, 401, 403):
                    value['revoked'] = True
                    self.save(connection, value)
                    raise ReconnectRequired('Reconnect LinkedIn') from None
                raise
            value['access_token'] = payload['access_token']
            value['expires_at'] = self.clock() + int(payload['expires_in'])
            if payload.get('refresh_token'):
                value['refresh_token'] = payload['refresh_token']
            if 'refresh_token_expires_in' in payload:
                value['refresh_expires_at'] = min(value['refresh_expires_at'], self.clock() + int(payload['refresh_token_expires_in']))
            self.save(connection, value)
            return value['access_token']

    def invalidate(self, connection):
        with LOCK:
            value = self.read(connection)
            value['revoked'] = True
            self.save(connection, value)


class OAuth:
    def __init__(self, credentials, config_getter=settings, request=transport, clock=time.time):
        self.credentials, self.config_getter = credentials, config_getter
        self.request, self.clock = request, clock
        self.pending = {}
        self.lock = threading.RLock()

    def begin(self, session, publish=False):
        config = self.config_getter()
        validate_settings(config)
        requested_scopes=AUTH_SCOPES
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.lock:
            self.pending = {k: v for k, v in self.pending.items() if v['expires'] > self.clock()}
            if len(self.pending) >= 100:
                raise ValueError('Too many pending LinkedIn connections; try later')
            self.pending[state] = dict(nonce=nonce, session=session, expires=self.clock()+600, config=config, requested_scopes=requested_scopes,return_view='testing' if publish else 'sources')
        url = 'https://www.linkedin.com/oauth/v2/authorization?' + urlencode({
            'response_type': 'code', 'client_id': config['client_id'], 'redirect_uri': config['redirect_uri'],
            'scope': ' '.join(sorted(requested_scopes)), 'state': state})
        return url, nonce

    def finish(self, state, nonce, code, denied=False):
        with self.lock:
            pending = self.pending.get(state)
            if (not pending or not nonce or not secrets.compare_digest(pending['nonce'], nonce) or
                    pending['expires'] <= self.clock() or not pending['session'].get('authenticated') or
                    pending['session']['expires'] <= self.clock()):
                raise ValueError('LinkedIn connection expired; start again from Sources')
            self.pending.pop(state)
        session = pending['session']
        if denied or not code:
            raise ValueError('LinkedIn permission was not granted; nothing was connected')
        config = pending['config']
        payload = self.request('https://www.linkedin.com/oauth/v2/accessToken', data={
            'grant_type': 'authorization_code', 'code': code, **config})
        if not pending['requested_scopes'].issubset(set(re.split(r'[ ,]+',payload.get('scope','')))):
            raise ValueError('LinkedIn did not grant the requested permissions')
        connection = self.credentials.save_grant(payload)
        session['linkedin_choice'] = dict(connection=connection, pages={}, start=0, more=True,
                                          expires=self.clock()+600,return_view=pending['return_view'])
        return session

    def pages(self, session, more=False):
        choice = session.get('linkedin_choice')
        if not choice or choice['expires'] <= self.clock():
            raise ValueError('Connect LinkedIn again to choose a Page')
        if choice.get('loaded') and not more:
            return choice
        if not choice['more']:
            return choice
        token = self.credentials.access_token(choice['connection'])
        data = self.request('https://api.linkedin.com/rest/organizationAcls?' + urlencode({
            'q': 'roleAssignee', 'state': 'APPROVED', 'start': choice['start'], 'count': 100}), token=token)
        if not isinstance(data.get('elements'), list):
            raise ValueError('LinkedIn returned an invalid Page list')
        for item in data['elements']:
            urn = item.get('organization', '')
            match = re.fullmatch(r'urn:li:organization:(\d+)', urn)
            if match and item.get('state') == 'APPROVED' and item.get('role') in (
                    'ADMINISTRATOR', 'CONTENT_ADMIN', 'CONTENT_ADMINISTRATOR', 'DIRECT_SPONSORED_CONTENT_POSTER'):
                name = item.get('organization~', {}).get('localizedName')
                choice['pages'][match[1]] = name if isinstance(name, str) else 'LinkedIn Page ' + match[1]
        choice['loaded'] = True
        paging = data.get('paging', {})
        choice['start'] += len(data['elements'])
        choice['more'] = bool(paging.get('links') and any(link.get('rel') == 'next' for link in paging['links']))
        if isinstance(paging.get('total'), int):
            choice['more'] = choice['start'] < paging['total']
        return choice


def posting_connections(config,credentials):
    result=[]
    for source in config['sources']:
        if source.get('platform')!='linkedin' or not source.get('connection_id') or source.get('draft'):continue
        try:
            grant=credentials.read(source['connection_id'])
            scopes=set(re.split(r'[ ,]+',grant.get('scope','')))
            if grant.get('revoked') or not AUTH_SCOPES.issubset(scopes):continue
            access_ok=bool(grant.get('access_token')) and grant.get('expires_at',0)>credentials.clock()+300
            refresh_ok=bool(grant.get('refresh_token')) and grant.get('refresh_expires_at',0)>credentials.clock()
            if access_ok or refresh_ok:
                result.append(dict(account=source['account'],connection=source['connection_id'],label=source.get('label') or source['account'],expires_at=grant.get('expires_at'),authenticated_at=grant.get('authenticated_at',0)))
        except (ValueError,OSError,TypeError):continue
    return sorted(result,key=lambda row:row['authenticated_at'],reverse=True)


def connect_pages(runtime,choice,account=None,credentials=None):
    """Bind a validated Page grant immediately; preserve retrieval preferences."""
    from .source_config import find_source
    from .source_connections import remember
    if not choice or choice['expires']<=time.time() or not choice.get('loaded'):
        raise ValueError('Connect LinkedIn again to choose a Page')
    if account is not None and account not in choice['pages']:
        raise ValueError('Choose a Page returned by your LinkedIn authorization')
    with runtime.poll_lock, runtime.lock:
        config=runtime.read_config()
        accounts=([account] if account is not None else [s['account'] for s in config['sources'] if s.get('platform')=='linkedin' and s.get('account') in choice['pages']])
        if not accounts and len(choice['pages'])==1:accounts=list(choice['pages'])
        for selected in accounts:
            if credentials and (choice['pages'][selected].startswith('LinkedIn Page ') or choice['pages'][selected]=='LinkedIn organization'):
                try:choice['pages'][selected]=credentials.organization(choice['connection'],selected)['name']
                except HTTPError as error:
                    if error.code not in (403,404):raise
                    choice['pages'][selected]='LinkedIn organization'
            source=find_source(config,'linkedin:'+selected) or find_source(config,'linkedin:')
            if source is None:
                source=dict(platform='linkedin');config['sources'].append(source)
            source.update(account=selected,connection_id=choice['connection'],label=choice['pages'][selected])
            source.pop('draft',None)
            source.setdefault('enabled',False);source.setdefault('interval_seconds',1800);source.setdefault('page_size',100)
        if accounts:
            config['sources']=[s for s in config['sources'] if not (s['platform']=='linkedin' and not s.get('account'))]
            runtime.save_config(config)
            for source in config['sources']:
                if source.get('platform')=='linkedin' and source.get('account') in accounts:remember(source,runtime.config_path.parent)
            # Clear only obsolete authentication failures; retain rate-limit cooldowns.
            import sqlite3
            with sqlite3.connect(runtime.db,timeout=15) as conn:
                for selected in accounts:
                    conn.execute("UPDATE source_poll_state SET error_type=NULL,error_code=NULL WHERE source_key=? AND (error_code=401 OR error_type='ReconnectRequired')",('linkedin:'+selected,))
        return accounts


def normalize(post, account, label=None, image_assets=None, original=None, original_resolution="unverified"):
    identity = post['id']
    if not re.fullmatch(r'urn:li:(?:share|ugcPost):\d+', identity):
        raise ValueError('Invalid LinkedIn post identifier')
    timestamp = post.get('publishedAt') or post.get('createdAt')
    created = datetime.fromtimestamp(timestamp/1000, timezone.utc).isoformat() if timestamp is not None else None
    content = post.get('content') or {}
    if not isinstance(content, dict):
        raise ValueError('Invalid LinkedIn post content')
    article = content.get('article') or {}
    link = article.get('source')
    links = [link] if isinstance(link, str) and urlparse(link).scheme in ('https', 'http') else []
    media=[]
    image_items=(content.get('multiImage') or {}).get('images',[]) or ([content['media']] if content.get('media') else [])
    if article.get('thumbnail'):image_items=image_items+[{'id':article['thumbnail'],'altText':article.get('title') or 'Article thumbnail'}]
    for item in image_items:
        asset=(image_assets or {}).get(item.get('id'),{})
        url=asset.get('downloadUrl','')
        if isinstance(url,str) and urlparse(url).scheme=='https':
            media.append(dict(url=url,alt=item.get('altText') or 'LinkedIn post image',asset_id=item['id']))
    from .linkedin_reposts import original_id
    root=original_id(post);is_repost=bool(root)
    publisher=label if label and not label.startswith('LinkedIn Page ') else 'LinkedIn organization'
    author_id=post.get('author');author_name=publisher;original_date=created
    source_avatar=None
    metadata=dict(content=content,lastModifiedAt=post.get('lastModifiedAt'),source_label=publisher,source_account_name=publisher,source_account_id='urn:li:organization:'+account,is_repost=is_repost,attribution={})
    if is_repost:
        metadata.update(original_post_url='https://www.linkedin.com/feed/update/'+root+'/',original_post_id=root,parent_post_id=(post.get('reshareContext') or {}).get('parent'),reposted_at=created,reposted_by=dict(id=post.get('author'),name=publisher),repost_commentary=plain_text(post.get('commentary','')),original_resolution='available' if original else original_resolution)
        if original:
            resolved=normalize(original,account,label,image_assets)
            expanded=original.get('author~') or {}
            if not isinstance(expanded,dict):expanded={}
            author_id=original.get('author')
            author_name=expanded.get('localizedName') or expanded.get('name')
            if not isinstance(author_name,str):author_name=None
            if not author_name:
                first=expanded.get('localizedFirstName') or '';last=expanded.get('localizedLastName') or ''
                author_name=(first+' '+last).strip() or None
            source_avatar=expanded.get('profilePictureUrl') or expanded.get('avatar')
            original_date=resolved['created_at']
            metadata.update(original_post=original,original_published_at=original_date,attribution=dict(name=author_name or 'Original author unavailable',id=author_id,date=original_date,avatar=source_avatar))
            text=resolved['text'];media=resolved['media'];links=resolved['links'];created=original_date
        else:
            author_id=None;author_name=None;text=plain_text(post.get('commentary',''))
            metadata['original_published_at']=None
    else:text=plain_text(post.get('commentary',''))
    metadata.update(author_id=author_id,author_name=author_name,author_avatar=source_avatar)
    return dict(platform='linkedin',account_id=account,post_id=identity,created_at=created,text=text,post_url='https://www.linkedin.com/feed/update/'+quote(identity,safe=':')+'/',links=links,media=media,metadata=metadata,raw=post)



class LinkedInProvider:
    supports_post_lookup=True
    platform = 'linkedin'

    def __init__(self, account, connection, credentials, page_size=100, request=transport, label=None):
        if not isinstance(account, str) or not re.fullmatch(r'[0-9]+', account):
            raise ValueError('LinkedIn requires a numeric organization ID')
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('LinkedIn page size must be 1–100')
        credentials.path(connection)
        self.account, self.connection, self.credentials = account, connection, credentials
        self.page_size, self.request, self.label = page_size, request, label

    @property
    def key(self):
        return 'linkedin:' + self.account

    def fetch(self, checkpoint):
        from .providers import FetchBatch
        token = self.credentials.access_token(self.connection)
        try:
            data = self.request('https://api.linkedin.com/rest/posts?' + urlencode({
                'q': 'author', 'author': 'urn:li:organization:' + self.account,
                'count': self.page_size, 'sortBy': 'LAST_MODIFIED'}), token=token)
        except HTTPError as error:
            if error.code == 401:
                self.credentials.invalidate(self.connection)
            raise
        if not isinstance(data.get('elements'), list):
            raise ValueError('LinkedIn returned an invalid post list')
        elements=data['elements']
        for item in elements:
            if item.get('author')!='urn:li:organization:'+self.account:raise ValueError('LinkedIn returned a different organization')
        from .linkedin_reposts import hydrate
        posts=hydrate(self,[p for p in elements if p.get('lifecycleState')=='PUBLISHED'],token)
        # One recent window and at most one media batch. No pagination or retries.
        newest = max((p['raw'].get('lastModifiedAt', 0) for p in posts), default=0)
        return FetchBatch(posts, str(newest) if newest else checkpoint)
