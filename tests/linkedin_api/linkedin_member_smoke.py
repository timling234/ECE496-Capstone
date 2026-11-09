"""Read-only LinkedIn member API smoke test; no application/feed integration."""
import argparse
import getpass
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[2]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the bearer token to another destination.

def retrieve(path, token, version, opener=None):
    if not path.startswith(('/v2/', '/rest/')) or any(c in token for c in '\r\n'):
        raise ValueError('Invalid request path or token')
    request = Request('https://api.linkedin.com' + path, headers={
        'Authorization': 'Bearer ' + token,
        'LinkedIn-Version': version,
        'X-Restli-Protocol-Version': '2.0.0',
        'Accept': 'application/json',
    }, method='GET')
    opener = opener or build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return {'http_status': response.status, 'data': json.load(response)}
    except HTTPError as error:
        try:
            payload = json.loads(error.read(65536))
        except (ValueError, UnicodeError):
            payload = {}
        # Do not persist arbitrary error bodies or any credential reflection.
        return {'http_status': error.code, 'error': {
            k: payload[k] for k in ('status', 'serviceErrorCode', 'code') if k in payload
        }}
    except (URLError, OSError, ValueError):
        return {'http_status': None, 'error': {'code': 'TRANSPORT_OR_JSON_ERROR'}}

def smoke(token, version='202610', getter=retrieve):
    results = {'checked_at': datetime.now(timezone.utc).isoformat(),
               'api_version': version, 'profile': getter('/v2/me', token, version)}
    if results['profile']['http_status'] == 401:
        return results
    params = urlencode({'q': 'me', 'queryType': 'IMPRESSION', 'aggregation': 'TOTAL'})
    results['post_impressions'] = getter('/rest/memberCreatorPostAnalytics?' + params, token, version)
    member_id = results['profile'].get('data', {}).get('id')
    if member_id:
        params = urlencode({'q': 'author', 'author': 'urn:li:person:' + member_id,
                            'count': 10, 'sortBy': 'LAST_MODIFIED'})
        results['personal_posts'] = getter('/rest/posts?' + params, token, version)
    else:
        results['personal_posts'] = {'skipped': 'No authenticated member ID returned'}
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path, help='Ignored local token file; never pass token values as arguments')
    parser.add_argument('--api-version', default='202610')
    args = parser.parse_args()
    if len(args.api_version) != 6 or not args.api_version.isdigit():
        parser.error('API version must be YYYYMM')
    try:
        token = (args.token_file.read_text(encoding='utf-8-sig').strip() if args.token_file
                 else os.environ.get('LINKEDIN_ACCESS_TOKEN', '').strip() or getpass.getpass('LinkedIn access token (hidden): ').strip())
        if not token or any(c.isspace() for c in token):
            raise ValueError('Invalid token')
    except (OSError, ValueError, EOFError):
        print('Token unavailable or invalid; no request sent.')
        return 2
    results = smoke(token, args.api_version)
    # API data stays in the ignored local directory. Never save the token.
    output = ROOT / '.tmp' / 'linkedin-member-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(results, ensure_ascii=False, indent=2).replace(token, '[REDACTED]')
    output.write_text(serialized, encoding='utf-8')
    for name in ('profile', 'post_impressions', 'personal_posts'):
        if name in results:
            result = results[name]
            print(name + ': ' + ('HTTP ' + str(result['http_status']) if 'http_status' in result else result['skipped']))
    print('Private response: .tmp/linkedin-member-smoke.json')
    return 0 if results['profile']['http_status'] == 200 else 1

if __name__ == '__main__':
    raise SystemExit(main())
