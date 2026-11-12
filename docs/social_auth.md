# X and Bluesky Authenticate

Sources has Authenticate X and Authenticate Bluesky, as well as the existing
LinkedIn flow. These connect sources inside the current workspace; they do not
replace ASAP / Google account login. New connections start with polling disabled.
Fetch Now remains an explicit API operation and posts still require human approval.
Existing manually configured public Bluesky sources and legacy X bearer files work.

## X website setup (once, by the administrator)

In [X Developer Console](https://developer.x.com/), enable OAuth 2.0 for a Web App.
Register exactly `https://asap.surf/x/callback`. Set private server `.env` values
`X_CLIENT_ID` and `X_CLIENT_SECRET`, then recreate the app container with Compose.
Do not confuse OAuth client credentials with the existing app-only bearer token.
Do not commit credentials or paste tokens into source-account fields.

`ASAP_PUBLIC_URL` defaults to `https://asap.surf`; other deployments must change it
and register the corresponding callback. Scopes are `tweet.read users.read
offline.access`; no publishing permission. Authorization uses random state, S256
PKCE, a separate HttpOnly Lax callback cookie, a 10-minute limit, initiating-login
binding, and one-use consumption. The callback exchanges the code once and calls
`GET /2/users/me` once to bind the authorized account. User consent does not imply
X API product access or available credits. Fetching may still return 403 or 429.

Grants live in the selected workspace's `x_credentials/<connection>.json` (0600,
directory 0700). The existing single-worker loader reads that grant, never the
original administrator's token. Refresh happens once under a shared lock before
expiry, saves rotated tokens atomically, and requires reconnect on failure.
Reauthentication preserves the source and its polling preference. Editing cannot
swap a connected account ID; authenticate another account instead.

## Bluesky

No administrator client secret or app password is needed. Client metadata is
public at `/bluesky/client-metadata.json`; callback is `/bluesky/callback`.
The current flow explicitly supports **bsky.social hosted did:plc accounts**.
Other federated accounts can still be added as public author-feed sources.
Supporting arbitrary PDS/issuer and did:web discovery requires an SSRF-hardened
resolver; this release does not fetch arbitrary user-provided URLs.

We request only `atproto`, perform PAR + S256 PKCE + ES256 DPoP, verify callback
issuer, then verify token subject -> PLC document -> hosted PDS protected-resource
metadata -> matching authorization server. Authentication-only clients may end the
flow here under the AT Protocol specification. Tokens and DPoP private keys are
not retained. Only the verified DID, authentication time, and identity scope are
stored in `bluesky_credentials/`. Public author-feed ingestion continues through
the existing public endpoint and requires no posting or private-account access.

Normal network operations have no automatic retry. Bluesky's explicit
`use_dpop_nonce` 400/401 challenge permits exactly one nonce-bound retry with a new
signed proof. Request bodies and tokens are excluded from browser errors and logs.
Destinations are HTTPS operator allowlists, redirects disabled, timeouts bounded,
and JSON responses capped at 1 MiB. Pending flows expire; a process restart
cancels unfinished flows but retains completed source connections.

## Validation

15 new offline tests cover real ES256 signatures, PAR/nonce handling, permissions,
CSRF, wrong login/cookie/state, denial/expiry/logout/replay, source isolation,
credential persistence, token refresh, identity/issuer/PDS rejection and legacy
administrator compatibility. Full offline suite: **132 passing**. Updated an old
navigation assertion to the user-approved name Mock Website.

Implementation did not make real token exchanges, profile/feed retrievals or send
mail. One public Bluesky authorization metadata GET was used for protocol checking;
public documentation/source reads are separate. User consent and live X app setup
remain acceptance steps, and no live authentication success is claimed.

Protocol references:
- [X OAuth 2.0 with PKCE](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code)
- [AT Protocol OAuth specification](https://atproto.com/specs/oauth)
- [AT Protocol OAuth patterns](https://atproto.com/guides/oauth-patterns)
- [Bluesky official Python cookbook](https://github.com/bluesky-social/cookbook/tree/main/python-oauth-web-app)


## Return to Sources and authentication badges

A verified social callback reissues the existing legacy administrator bearer as an
HttpOnly Lax cookie with its original remaining lifetime. This retains login on
the redirect to Sources when the original Strict cookie was withheld by a browser;
portal accounts keep their existing login binding. No new session or extended
expiry is created, and every mutation still requires CSRF. Invalid callbacks,
wrong nonces, expired/logged-out sessions and replay cannot restore a login.

Authentication badges are based only on each workspace's local grant records.
Authenticated is green and independent of polling being Disabled. Missing/expired
or revoked grants show Reconnect required; plain public Bluesky sources show Public
access. Checking a badge makes no provider requests or token refreshes. Fresh
reauthentication supersedes older fetch-authentication errors; current errors still
require reconnect. Connected rows offer Re-authenticate.

## Source management update

The Add Source panel uses three platform icon links and server-selected connected
accounts. It has no manual account/handle field or nested authentication controls.
Authenticate from the outer Sources controls first. OAuth normally adds its source
automatically; the Add panel can restore an account removed from Sources using its
saved grant. Existing accounts are edited rather than duplicated. Posts per request
(previously page size) lives in Advanced settings and defaults to 5 where applicable.
It is an API batch limit, not the public feed's display count; catch-up retrieval
can still paginate. Existing configured sizes are preserved.

Remove stops retrieval after an active fetch completes. Queued commands for a
removed source are skipped. Posts, approvals, source checkpoints, rate-limit state
and grants are retained; deletion does not revoke platform access or withdraw old
posts. Saved choices are restricted to the current workspace's credential catalog;
form fields cannot select a foreign account or arbitrary credential path.

Bluesky consent verifies a DID's advertised handle through one forward
resolveHandle lookup, then reuses an existing matching handle source. The source
retains its old key/settings/checkpoint while `authorized_account` pins retrieval
to the verified DID. This prevents a handle and DID becoming two sources. An
already-created duplicate was repaired with one identity lookup, preserving all
posts and the original polling state.


## Provider-first source creation (current flow)

Clicking a platform icon submits a CSRF-protected POST to `/source-add`, creates
one disabled, unauthenticated source draft, and returns directly to Sources. A
second click reuses that platform's pending draft. GETs never create sources.
Authenticate is the last action on each source row; there are no global
Authenticate buttons or additional account-selection steps in Add Source.

Drafts contain no account or credentials, are skipped by the worker, and cannot
be enabled or fetched. Successful OAuth consumes the draft and binds the verified
account; choosing an already-connected account reuses its row rather than making
a duplicate. New LinkedIn workspaces' original placeholder is reused. Source edits
keep the settings-only form. The older saved-grant restore endpoint remains
server-validated, but it is no longer a prerequisite to adding a platform row.

Source rows support a workspace-local `name` (1–80 characters), defaulting to
`x`, `bluesky`, or `linkedin`. Edit it through the row pencil / Source name field.
Names affect the management label only; identity, account, grants, polling state
and stored posts remain separate. Draft names survive authentication.
