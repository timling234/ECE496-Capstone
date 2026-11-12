"""FR-1/FR-7: provider-aware add/edit; local credential references remain private."""
import uuid
from .providers import BlueskyProvider, XProvider


def identity(source):
    return source['platform']+':'+source.get('account','')


def find_source(config, key):
    return next((s for s in config['sources'] if identity(s)==key),None)


def configure_source(config, fields, key=None):
    """Shared add/edit validation; never accepts credential values from HTML."""
    existing=find_source(config,key) if key else None
    if key and existing is None:raise ValueError('Source not found; refresh this page')
    platform=existing['platform'] if existing else fields.get('provider','')
    if platform not in ('x','bluesky','linkedin'):raise ValueError('Unsupported provider')
    name=fields.get('name',(existing or {}).get('name',platform)).strip() or platform
    if len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Source name must contain 1–80 characters on one line')
    enabled=fields.get('enabled')=='on'
    if existing and existing.get('connection_id') and fields.get('account','').strip()!=existing.get('account'):
        raise ValueError('Authenticate another account to change this connected source')
    account=fields.get('account','').strip()
    interval=int(fields.get('interval_seconds') or 1800)
    if not 1<=interval<=31536000:raise ValueError('Interval must be 1–31536000 seconds')
    page_size=int(fields.get('page_size') or (existing or {}).get('page_size',5))
    if existing and existing.get('draft'):
        if enabled:raise ValueError('Authenticate this source before enabling retrieval')
        if account:raise ValueError('Authenticate to select this source account')
        if not (5 if platform=='x' else 1)<=page_size<=100:raise ValueError('Invalid posts per request')
        if platform=='linkedin' and interval<1800:raise ValueError('LinkedIn polling must be at least 1800 seconds')
        existing.update(name=name,enabled=False,interval_seconds=interval,page_size=page_size)
        return existing
    if platform=='linkedin':
        if not existing or not existing.get('connection_id'):
            raise ValueError('Use Connect LinkedIn to add an authorized Page')
        if account != existing.get('account'):
            raise ValueError('Connect another LinkedIn Page to change the organization')
        if interval < 1800:raise ValueError('LinkedIn polling must be at least 1800 seconds')
        if not 1 <= page_size <= 100:raise ValueError('LinkedIn page size must be 1–100')
    elif platform=='x':XProvider(account,page_size=page_size)
    else:BlueskyProvider(account,page_size=page_size)
    replacement=dict(existing or {})
    replacement.update(name=name,platform=platform,account=account,enabled=enabled,interval_seconds=interval)
    if page_size is not None:replacement['page_size']=page_size
    new_key=identity(replacement)
    if any(identity(s)==new_key and s is not existing for s in config['sources']):raise ValueError('This provider/account is already configured')
    if existing:existing.clear();existing.update(replacement)
    else:config['sources'].append(replacement)
    return replacement


def add_platform(config,platform):
    """One disabled draft per platform. A provider click is sufficient to add it."""
    if platform not in ('x','bluesky','linkedin'):
        raise ValueError('Unsupported provider')
    draft=next((s for s in config['sources'] if s['platform']==platform and not s.get('account')),None)
    if draft is None:
        draft=dict(platform=platform,account='',enabled=False,interval_seconds=1800,page_size=5)
        config['sources'].append(draft)
    draft.setdefault('account','')
    draft.setdefault('name',platform)
    draft.update(draft=True,enabled=False)
    return draft
