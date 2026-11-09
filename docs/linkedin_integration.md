# LinkedIn organization connection and ingestion

Implemented 2026-11-07. Community Management Development Tier was approved.
The prior live smoke test retrieved the ASAP Test Lab post with one request.
This integrated browser flow has been verified with local mocked LinkedIn responses;
it has not yet been authorized live with this application's own callback URL.

## One-time server setup

The server needs the existing developer application's Client ID, Client Secret,
and a callback URL registered under that same application's Auth settings.
The developer portal token-generator callback is not this application's callback.

Local configuration (hidden secret prompt, ignored .tmp/linkedin-app.json):

    python run_app.py --configure-linkedin

Register the exact callback, for example:

    https://localhost:5171/linkedin/callback

Use localhost consistently in both the app URL and callback, or consistently use
127.0.0.1; do not mix hosts because session cookies are host-bound. LinkedIn's
portal must accept and list the exact local URL before testing. For a hosted
installation use HTTPS, e.g. https://asap.example.org/linkedin/callback, terminate
TLS at your proxy, and set ASAP_COOKIE_SECURE=1. Do not use a LAN/public HTTP URL.
Use the existing developer app; no additional app is needed. An admin authorized
to grant access must approve the requested permissions in LinkedIn.

Alternatively supply LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET and
LINKEDIN_REDIRECT_URI in the server environment (Compose forwards these values).
ASAP_LINKEDIN_APP_FILE can select a private JSON config using the same lowercase
keys client_id, client_secret, redirect_uri. Never commit actual credentials.

## User flow

1. Start python run_app.py and sign into the admin console.
2. Sources -> + Add Source -> LinkedIn -> Choose provider -> Authenticate.
3. Sign in on LinkedIn and approve Page access. This requests r_organization_social
   for posts and rw_organization_admin to discover the Pages the member administers.
   The latter scope is broader than read-only despite being used only for a GET.
4. LinkedIn returns to this application's /linkedin/callback. Click Load my Pages,
   then Connect this Page for one of the returned organization Pages. The Page list
   is cached during selection; refreshing the screen does not call LinkedIn again.
   If names are not returned, the numeric Page ID and View Page link identify it.
5. The source is saved with polling DISABLED. Click Fetch Now to pull one recent
   page (up to 100 posts) into the Store and administrator Review Queue.
6. To connect another Page, repeat Authenticate; connections may share the same
   authorized member, but every chosen Page must appear in the authorization's
   eligible Page list. Existing Page reconnection disables polling until re-enabled.

The connecting member needs an appropriate Page role. This discovery flow uses
rw_organization_admin, so use a Page administrator with the required organization
admin privileges. An account that only follows a Page cannot connect it. Personal
member-post reading is not supported. No posting scopes or API writes are used.

## Quota and supported data

- No post request occurs on OAuth return, Page selection or screen refresh.
- Load my Pages makes one organizationAcls request. Load more is explicit when
  LinkedIn indicates another page. Repeat screen views reuse the cached response.
- Fetch Now makes one posts request, no implicit retries, pagination, or media calls.
  A due credential refresh can add one token-endpoint request before the post GET.
- Pulls read a recent window of at most 100 posts, sorted by last modification.
  This is not a full historical sync: a burst larger than the window can be missed.
- Text, original permalink, timestamps, article links, content metadata and raw
  payload are retained. Image/video URNs stay in metadata; binaries are not fetched.
- Native post URNs are upserted; a repeated pull updates content without duplicate rows.
- Automatic polling is opt-in with a minimum 1800-second interval. At one Page this
  is up to 48 post requests/day; multiple Pages share the member/app daily quotas.
  HTTP 429 cooldown is handled by the existing scheduler. There is no hidden retry.
- Expiring access tokens refresh at most once under a shared lock, when a valid
  refresh token exists. Expired/revoked credentials require Authenticate.
  Refresh and access lifetime remain controlled by LinkedIn; no unlimited tokens.

Tokens are server-side files under the config directory's linkedin_credentials/,
with opaque connection IDs in source config. Keep this directory private, backed
up with the deployment's private data, and never serve or commit it. OAuth state
is short-lived, single-use, and bound to a separate HttpOnly Lax nonce cookie and
the initiating authenticated admin session. Existing admin cookies remain Strict.
Server logs omit request URLs and credentials. Tokens never enter browser HTML.
Restarting the server during authorization requires beginning the connection again.

## Local demo review and Feed

The current installation is a local demo. LinkedIn organization posts use the same
Approve / Reject / Withdraw flow as the other platforms. A fetched post starts
pending, becomes visible in the local Feed only after approval, and disappears
from that Feed after withdrawal. There is no LinkedIn-specific publication gate.
This change does not deploy the application or publish content back to LinkedIn.

## Verification

    python -m unittest discover -s tests -p test_linkedin.py -v
    python run_tests.py

Tests use temporary local databases and mocked provider data, not real credentials
or LinkedIn quota. Coverage includes callback state/cookie/session binding, replay
and denial, Page selection allowlisting, source persistence, default-disabled polling,
one-page fetching, idempotent Store writes, refresh expiry, 401/429, credential
redaction, and approval/withdrawal visibility in the local Feed.

Official references:
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/organization-access-control-by-role?view=li-lms-2026-10
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-10
- https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-10


Public Feed integration verification: authenticated organization ingestion enters
the existing review workflow; an approved record is rendered in /feed with its
LinkedIn source Page label and original permalink. /embed-demo embeds that same
feed, and withdrawal removes the record from both views on refresh. No admin
forms or credentials are rendered in the public response. The Sources button
is named Authenticate for both first-time connections and reauthorization.


## Local HTTPS requirement verified in developer portal

The LinkedIn developer portal rejected http://localhost:5170/linkedin/callback
as an invalid redirect URL. Use HTTPS for the local callback. The launcher now
supports an additional HTTPS listener sharing the same sessions, database and
single polling worker:

    python run_app.py --port 5170 --https-port 5171 --tls-cert .tmp/localhost-demo-cert.pem --tls-key .tmp/localhost-demo-key.pem

Use a localhost certificate trusted by your browser. Certificate trust installation
is a separate explicit user action. Never commit certificates' private keys or
disable TLS verification. Register the HTTPS callback and configure the same URI
in the private LinkedIn server settings.
