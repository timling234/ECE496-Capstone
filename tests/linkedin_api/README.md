# LinkedIn member read-only smoke test

This is an independent live diagnostic, not a LinkedIn feed adapter.
It calls GET /v2/me, GET /rest/memberCreatorPostAnalytics (total impressions),
and, when the member ID is available, GET /rest/posts for that member.
A 403 from personal_posts is a denied read, not an empty feed or a successful integration.
The app currently offers r_basicprofile and r_member_postAnalytics, but not r_member_social.

## Run

Generate a member token for ASAP Test with r_basicprofile and r_member_postAnalytics.
Run from the repository root:

    python tests/linkedin_api/linkedin_member_smoke.py

Paste the token at the hidden prompt. Alternatively use LINKEDIN_ACCESS_TOKEN,
or --token-file .tmp/linkedin_access_token.txt (ignored by .gitignore).
Do not pass the token itself on the command line, commit it, or paste it in chat.
The diagnostic performs at most three GET requests and makes no posts or edits.
It stops after a profile 401. It does not follow redirects with credentials.
Private response data is written to .tmp/linkedin-member-smoke.json;
remove it after the test and do not publish it. No token is stored in the report.
Exit 0 means profile retrieval succeeded; inspect every endpoint status separately.
An impressions result is statistics, not post text. The personal-post check reads
only the first page of ten posts; it is not a complete history export.

## References checked 2026-11-07

- https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/post-statistics?view=li-lms-2026-10
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-10

## Validation status

Live verification completed on 2026-11-07 (API version 202610):

| Check | Result |
|---|---|
| GET /v2/me | HTTP 200; authenticated member profile returned |
| GET /rest/memberCreatorPostAnalytics?q=me&queryType=IMPRESSION&aggregation=TOTAL | HTTP 200; aggregate impressions returned |
| GET /rest/posts?q=author for authenticated member | HTTP 403 ACCESS_DENIED (serviceErrorCode 100); no post text retrieved |

The token exchange returned scopes r_basicprofile,r_member_postAnalytics,
an access lifetime of 5,183,999 seconds (about 60 days), and a refresh token
with about 365 days remaining. Automatic refresh eligibility is confirmed for
this grant, but no automatic-refresh implementation or refresh call was tested.
Credentials are retained only under ignored .tmp; no client secret is retained
by this diagnostic. Private profile/statistics are excluded from this document.

The official embedded token-generator window stalled. A standard top-level
OAuth authorization with the same scopes and existing registered LinkedIn
callback succeeded after verifying state and exchanging a fresh code on the
server side. The earlier failed code was not reused for the successful exchange.

Offline checks passed: member URN encoding, preservation of denied-read status,
401 short circuit, redirect blocking, and fixed API host validation.
The existing application still has no LinkedIn ingestion adapter; it remains
disabled. This smoke test does not establish MSRG Page access or public-feed use.


## Organization post retrieval: verified 2026-11-07

ASAP Test Lab (organization ID 143906318) was verified using one list request.
A single test post was published through the LinkedIn Page UI, as the Page:

- Marker: ASAP-LI-ORG-20261107-01
- Post URN: urn:li:share:7524964445090123776
- Post URL: https://www.linkedin.com/feed/update/urn:li:share:7524964445090123776/
- OAuth scope actually returned: r_organization_social (no posting/admin scope requested)
- GET /rest/posts?q=author&author=urn%3Ali%3Aorganization%3A143906318&count=10&sortBy=LAST_MODIFIED
- API version: 202610
- HTTP 200; one post returned; author and marker both matched the test post.
- Exactly one organization-list request was made; no retries or organization lookup.
- Access token TTL: 5,183,999 seconds; refresh token returned with 31,536,059 seconds remaining.

Run from the repository root only when another live check is needed:

    python tests/linkedin_api/linkedin_org_smoke.py

The script uses .tmp/linkedin_org_access_token.txt or LINKEDIN_ORG_ACCESS_TOKEN.
It performs exactly one GET, saves the private response to .tmp/linkedin-org-smoke.json,
and returns success only when the expected marker belongs to the configured organization.
Use --organization and --expected-marker to test a different authorized Page/post.
All tokens, refresh tokens, metadata, and raw responses are under ignored .tmp.
The one-time authorization-code/client-secret exchange file was removed immediately.

This demonstrates organization post text retrieval for this Page. It does not
establish access to MSRG, member post retrieval, media download, pagination,
background ingestion, automated token refresh, or permitted public-feed use.
The smoke test left automatic LinkedIn polling disabled. See docs/linkedin_integration.md and docs/JARVIS_HANDOFF.md for the integrated application and deployment status.
Changing OAuth scopes may invalidate previously issued member-test tokens;
no additional member calls were made to check that because API quota is conserved.

Quota discipline: default to one live request per endpoint per requested check.
Inspect stored responses before considering retries; no unattended polling for these diagnostics.
