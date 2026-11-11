# Stage 2: account portal on Jarvis

## Architecture decision — 2026-11-10

Use Flask with Waitress as the production WSGI server. Keep SQLite and the existing
provider/editorial pipeline on Jarvis. Do not add Supabase in this phase: a hosted
Auth/database dependency is unnecessary for the current single-server installation.
An eventual multi-instance installation would require shared storage, coordinated
polling and a fresh database/auth decision.

The Flask portal dispatches editorial requests to a transport adapter around the
existing handler methods. It does not start a second HTTP service or forward a
user-supplied URL. `make_server` remains only as a compatibility entry point for
existing offline socket tests/tools. Production `run_app.py` uses Flask/Waitress.
There is exactly one application process; do not deploy multiple WSGI workers with
independent pollers against these files.

## Routes and ownership

- `/`: ASAP landing page; `/register`, `/signin`: email/password accounts.
- `/app`: signed-in workspace overview and iframe snippet; `/account`: identity,
  explicit Google linking, sign-out.
- `/admin`: existing operational console. Portal users receive their own workspace.
  A separate legacy admin login at `/login` retains the original deployment's data.
- `/feed`, `/embed-demo`: original deployment's unchanged public identity.
- `/u/<opaque-account-id>/feed`, `/u/<opaque-account-id>/embed-demo`: each account's
  **public**, approved-only feed and iframe preview. Knowing a feed URL conveys no
  private review/configuration authority. There is no private tenant selector in
  query parameters or form data.

`/data/asap.sqlite3`, `/data/polling.local.json`, and `/data/linkedin_credentials/`
remain the original admin workspace. `/data/accounts.sqlite3` holds identities,
opaque session hashes, short-lived OAuth state and rate-limit buckets.
`/data/workspaces/<server-generated-id>/` contains each user's own `asap.sqlite3`,
`polling.local.json`, and `linkedin_credentials/`. The same native provider post ID
may exist independently in multiple users' Stores. Their decisions, duplicates,
notification outboxes, source checkpoints and presentation settings are independent.

A new account starts empty, with an unconnected LinkedIn placeholder and polling off.
No original admin grants/posts/settings are copied. X does not fall back to the
original admin's token: a server-admin-provisioned workspace-specific token is
required. Bluesky uses public author-feed reads. LinkedIn grants are saved under the
initiating account's directory. Email notifications can only target the account's
own Google-verified address; they start disabled. No test sends mail automatically.

## Authentication

Passwords use per-password random salt + scrypt (N=16384,r=8,p=1). Regular accounts
require 12–256 characters. The user-requested legacy admin password remains separate.
Sessions are random opaque cookies (Secure under HTTPS, HttpOnly, SameSite=Lax),
rotated after sign-in/linking, stored hashed with fixed eight-hour expiry, and revoked
on logout. CSRF protects mutations, including logout and explicit account linking.
Authentication and Google-start throttles persist across process restarts.
Registration is capped at 100 accounts for this single-server deployment.

Email/password registration does not itself verify email ownership. It never links
an existing account to Google merely because email strings match. Sign in with the
local password, then explicitly link a Google account with that same verified email.
The Google `sub` is the durable provider identity. Password recovery and
administrative account deletion are not part of this implementation.

## Google setup

Create a Google Cloud OAuth client of type **Web application**. Configure branding,
audience/test users as applicable, and these exact values:

- Authorized domain: `asap.surf`
- Authorized redirect URI: `https://asap.surf/auth/google/callback`
- Scopes: `openid email profile` only. No Gmail API permission is requested.
- Private `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `GOOGLE_REDIRECT_URI=https://asap.surf/auth/google/callback`.

Gmail SMTP app passwords are unrelated and cannot be used as OAuth client secrets.
If these settings are absent, Google sign-in is visibly unavailable and email/password
continues working; the app never substitutes an unverified or mock identity.

The authorization-code flow binds a single-use, ten-minute state to the initiating
browser session, uses nonce + PKCE S256, exchanges the code server-side with verified
TLS, and validates Google's ID token with `google-auth` (signature, audience, issuer,
expiry), then separately checks nonce and verified email. Tokens are not persisted.
The callback does not log codes/tokens/provider responses. A user who logs out before
completion cannot finish or link the old flow. LinkedIn keeps its own separate
callback and nonce; no change to LinkedIn scope requirements.

Official references: [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[Google server-side verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token),
[Flask production deployment](https://flask.palletsprojects.com/en/stable/deploying/).

## Deploy, test, backup

Install dependencies with `pip install -r requirements.txt`. `python run_tests.py`
runs the original offline suites and new account/isolation/OIDC tests without calling
real providers or SMTP. Production starts with `python run_app.py --host 0.0.0.0
--db /data/asap.sqlite3 --port 5000` inside Docker.

Jarvis: keep the existing Compose overrides and Caddy. Set `ASAP_COOKIE_SECURE=1`
and `ASAP_TRUST_PROXY=1` **only behind the single trusted Caddy proxy**, with the app
port bound to host loopback. Waitress retains forwarded headers in that explicitly
configured mode; Flask trusts exactly one proxy hop. Never expose port 5000/5050
through the router. User traffic and OAuth callbacks continue using port 443.

Back up all of `/data`, including accounts and every workspace, not only the original
Store. Stop the app first for a consistent multi-file snapshot, or use SQLite backup
for each database while coordinating config/grant writes. Protect backups like live
credentials. Rolling back to stage 1 preserves new account files but makes the portal
unavailable until stage 2 is restored; the original Store schema is unchanged.

Tests must cover two simultaneous users, cross-account forged post IDs, isolated
settings/sources/grants, approved-only public feeds, CSRF, cookie/session rotation,
logout and restart persistence, Google state/nonce/replay/claim validation, and the
original admin lifecycle. A mocked OAuth exchange is not real Google acceptance.

## Workspace navigation follow-up

Login now opens `/admin` directly; `/app` redirects there. Public Feed opens inside
the management shell with a copyable iframe snippet above its live preview.
**Mock Website** remains a separate sidebar destination (the existing per-account
`/u/<id>/embed-demo` route), for demonstrating how a feed will look within a target
integration website. Adapt that mock to each integration partner's requirements
when supplied. The current MSRG mock is an initial template, not the generic feed
configuration page.
