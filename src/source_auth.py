"""Credential status from local evidence only; never refresh or contact a provider."""
import time
from .linkedin import Credentials


def authentication(source, directory, now=None):
    now=time.time() if now is None else now
    platform=source['platform']
    connection=source.get('connection_id')
    if not connection:
        return 'Public access' if platform=='bluesky' else 'Not authenticated'
    try:
        grant=Credentials(directory/(platform+'_credentials')).read(connection)
        if not isinstance(grant,dict) or grant.get('revoked'):
            return 'Reconnect required'
        if platform=='bluesky':
            return 'Authenticated' if grant.get('identity_only') and grant.get('sub')==source.get('authorized_account',source.get('account')) else 'Reconnect required'
        if ((source.get('error_code')==401 or source.get('error_type')=='ReconnectRequired')
                and (source.get('last_attempt_at') or 0)>=grant.get('authenticated_at',0)):
            return 'Reconnect required'
        access_ok=bool(grant.get('access_token')) and grant.get('expires_at',0)>now
        refresh_ok=bool(grant.get('refresh_token')) and (grant.get('refresh_expires_at',0)>now if platform=='linkedin' else grant.get('refresh_expires_at',now+1)>now)
        return 'Authenticated' if access_ok or refresh_ok else 'Reconnect required'
    except (ValueError,OSError,TypeError):
        return 'Reconnect required'
