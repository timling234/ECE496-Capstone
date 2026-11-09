"""One-request LinkedIn organization post retrieval smoke test."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from linkedin_member_smoke import retrieve

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'ASAP-LI-ORG-20261107-01'


def check(token, organization, marker=MARKER, version='202610', getter=retrieve):
    if not organization.isascii() or not organization.isdigit():
        raise ValueError('Organization must be a numeric ID')
    params = urlencode({'q': 'author', 'author': 'urn:li:organization:' + organization,
                        'count': 10, 'sortBy': 'LAST_MODIFIED'})
    response = getter('/rest/posts?' + params, token, version)
    data = response.get('data', {})
    posts = data.get('elements') if isinstance(data, dict) else None
    matches = [p for p in (posts or []) if isinstance(p, dict)
               and p.get('author') == 'urn:li:organization:' + organization
               and marker in p.get('commentary', '')]
    return {'checked_at': datetime.now(timezone.utc).isoformat(),
            'organization': organization, 'api_version': version,
            'expected_marker': marker, 'list_requests': 1,
            'http_status': response['http_status'],
            'response_shape_valid': isinstance(posts, list),
            'returned_count': len(posts) if isinstance(posts, list) else None,
            'matched_post_ids': [p.get('id') for p in matches],
            'marker_found': bool(matches), 'response': response}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--organization', default='143906318')
    parser.add_argument('--expected-marker', default=MARKER)
    parser.add_argument('--api-version', default='202610')
    parser.add_argument('--token-file', type=Path, default=ROOT/'.tmp/linkedin_org_access_token.txt')
    args = parser.parse_args()
    if len(args.api_version) != 6 or not args.api_version.isdigit():
        parser.error('API version must be YYYYMM')
    if not args.expected_marker:
        parser.error('Expected marker cannot be empty')
    try:
        token = os.environ.get('LINKEDIN_ORG_ACCESS_TOKEN', '').strip() or args.token_file.read_text(encoding='utf-8-sig').strip()
        if not token or any(c.isspace() for c in token):
            raise ValueError('Invalid token')
        result = check(token, args.organization, args.expected_marker, args.api_version)
    except (OSError, ValueError):
        print('Invalid organization or token configuration; no successful read claimed.')
        return 2
    output = ROOT/'.tmp/linkedin-org-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2).replace(token, '[REDACTED]'), encoding='utf-8')
    summary = {k: result[k] for k in ('list_requests', 'http_status', 'returned_count', 'marker_found', 'matched_post_ids')}
    print(json.dumps(summary))
    print('Private response: .tmp/linkedin-org-smoke.json')
    return 0 if result['http_status'] == 200 and result['marker_found'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
