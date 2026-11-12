"""Workspace-local saved account choices and non-destructive source removal."""
from copy import deepcopy
from .linkedin import Credentials
from .source_auth import authentication


def remember(source, directory):
    if not source.get('connection_id'):
        return
    credentials=Credentials(directory/(source['platform']+'_credentials'))
    try:grant=credentials.read(source['connection_id'])
    except (ValueError,OSError):return
    if not isinstance(grant,dict):return
    accounts=grant.setdefault('source_accounts',{})
    accounts[source['account']]={k:source[k] for k in ('platform','account','authorized_account','label','connection_id','name') if k in source}
    credentials.save(source['connection_id'],grant)


def choices(config,directory):
    result={}
    for platform in ('x','bluesky','linkedin'):
        credentials=Credentials(directory/(platform+'_credentials'))
        for path in sorted(credentials.directory.glob('*.json')):
            try:
                grant=credentials.read(path.stem)
                for account,record in grant.get('source_accounts',{}).items():
                    if record.get('platform')!=platform or record.get('account')!=account:
                        continue
                    record=dict(record,connection_id=path.stem)
                    if authentication(record,directory)=='Authenticated':
                        result[(platform,record.get('authorized_account',account))]=record
            except (ValueError,OSError,AttributeError):
                continue
    # Existing grants predate the catalog. Their server-owned source metadata is
    # valid evidence too; browser requests never supply a credential/account pair.
    for source in config['sources']:
        if source.get('connection_id') and authentication(source,directory)=='Authenticated':
            result[(source['platform'],source.get('authorized_account',source['account']))]=deepcopy(source)
    return [dict(s,connection_ref=s['connection_id']+':'+s['account']) for s in result.values()]


def merge_bluesky(config,did,handle,connection):
    """Only call after handle -> DID is verified. Keep the old key/checkpoint."""
    matches=[s for s in config['sources'] if s['platform']=='bluesky' and
             (s.get('account') in (did,handle) or s.get('authorized_account')==did)]
    if not matches:
        return None
    keep=next((s for s in matches if s.get('account')==handle),matches[0])
    keep.update(connection_id=connection,authorized_account=did,label=handle or did)
    config['sources']=[s for s in config['sources'] if s not in matches or s is keep]
    return keep
