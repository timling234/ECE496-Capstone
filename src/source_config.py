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
    enabled=fields.get('enabled')=='on'
    if existing and existing.get('connection_id') and fields.get('account','').strip()!=existing.get('account'):
        raise ValueError('Authenticate another account to change this connected source')
    account=fields.get('account','').strip()
    interval=int(fields.get('interval_seconds') or 1800)
    if not 1<=interval<=31536000:raise ValueError('Interval must be 1–31536000 seconds')
    page_size=int(fields.get('page_size') or (existing or {}).get('page_size',5))
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
    replacement.update(platform=platform,account=account,enabled=enabled,interval_seconds=interval)
    if page_size is not None:replacement['page_size']=page_size
    new_key=identity(replacement)
    if any(identity(s)==new_key and s is not existing for s in config['sources']):raise ValueError('This provider/account is already configured')
    if existing:existing.clear();existing.update(replacement)
    else:config['sources'].append(replacement)
    return replacement
