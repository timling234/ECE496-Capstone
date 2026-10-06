# ASAP operations console

## Normal local operation

```powershell
python run_app.py
```

This now starts **both the HTTP application and its single polling worker**. Stop the older app once before restarting with this version. A second polling command/terminal is no longer part of normal operation. Do not run a separate polling worker against the same Store concurrently.

- Admin: http://localhost:5000/admin
- Feed: http://localhost:5000/feed
- Default Store: `.tmp/store_poc.sqlite3`
- Default runtime settings: `.tmp/polling.local.json`

Existing enabled/account/interval settings are preserved. New configurations default to disabled sources with 1800-second intervals. Admin **Sources** edits or Enable/Disable apply at runtime without process restart. Three seconds is allowed for short tests. An already active API request may finish when disabled; later scheduled requests stop. Fetch Now explicitly requests the selected configured source even when scheduled polling is disabled. X may consume API credits. HTTP 429 cooldowns remain enforced for manual fetch and interval changes.

The worker serializes requests and commits source records, filter/duplicate processing and checkpoint atomically. Failed requests retain checkpoints and report safe error type/HTTP status, with no response bodies, credentials or headers. Counts distinguish records fetched from distinct provider identities newly discovered in SQLite; an older previously unseen record can count as new. Scheduling still refreshes its overlapping Bluesky boundary record, so 1 fetched / 0 new is normal on unchanged feeds.

Sources shows health, polling mode/interval, attempt/success time, fetched/new counts, next due time and controls. Timestamps are explicitly UTC. Refresh status/results updates the display; changes never require another process. Dashboard shows worker/database/provider status and review counts. Other navigation: Review Queue, Published, Rejected, Duplicate Groups, Testing / Development and Settings.

## Development tools

Enable only for local development:

```powershell
$env:ASAP_DEV_TOOLS='1'
python run_app.py
```

With the switch unset or 0, the page contains no runnable development controls and the backend refuses development jobs. Authentication and CSRF remain required. Normal editorial controls do not depend on this switch.

Offline groups execute an explicit backend allowlist of existing unittest files. Run All uses the existing `run_tests.py`. No command strings, executable names, file paths or shell flags come from the browser. One development job runs at a time. Jobs run in background threads; regression subprocesses use `shell=False`, a 180-second timeout, captured/redacted output and an environment without credential variables. Results/FR metadata/duration/time persist in `dev_runs`. Interrupted jobs are identified after app restart. Output is capped at the last 16000 characters and marked when truncated. CLI `python run_tests.py` and `python run_demo.py` remain available.

Live X/Bluesky fetch jobs are marked separately and use the same ingestion pipeline. They do not approve posts.

## Explicit Bluesky TEST account

The publisher never infers a writing target from a retrieval source. Configure `ASAP_BSKY_TEST_ACCOUNT` and `ASAP_BSKY_APP_PASSWORD` in the launch environment, or run the one-time hidden-input helper:

```powershell
python run_app.py --configure-bluesky-test
```

Enter the explicitly designated test handle, such as `asaptestlab.bsky.social`, and that account's **app password** in your local terminal. The helper stores these only in ignored `.tmp/dev_credentials.json`. Never paste the password into chat or the web page; never commit the local file. Dev controls display only the handle and readiness. If these credentials are missing, publishing/E2E buttons are disabled and server-side requests are refused.

Publishing authenticates using `com.atproto.server.createSession`, checks the authenticated handle matches the explicit test handle, and creates an `app.bsky.feed.post` record in that authenticated DID's repo using `com.atproto.repo.createRecord`. Short-lived session tokens stay in process memory. Current publisher supports plain text up to 300 code points on bsky.social test handles. This is independent implementation following the [official post tutorial](https://docs.bsky.app/docs/tutorials/creating-a-post); no reference code copied.

Publish Test Post creates a real public Bluesky test-account post and reports URI/time/URL. Run Bluesky E2E generates unique text, publishes it, triggers fetch, then verifies that exact URI and text are stored as a review candidate. E2E requires the retrieval source to match the explicit test handle. Indexing is retried for up to 60 seconds; failure/delay is reported rather than silently passing. It **never approves or publishes to the ASAP public feed**. Real Bluesky test posts remain on Bluesky; no remote deletion/cleanup is automatic.

## X posting investigation

The repository uses an existing bearer-token file for read ingestion; it has no verified user-context posting credentials, OAuth authorization flow or write-scope validation. The official [authentication mapping](https://docs.x.com/fundamentals/authentication/guides/v2-authentication-mapping) lists POST /2/tweets for OAuth 1.0a user context or OAuth 2.0 authorization-code PKCE, not app-only authentication; OAuth 2.0 needs tweet.read, tweet.write and users.read. The [create-post endpoint](https://docs.x.com/x-api/posts/create-post) is the relevant API. A bearer string alone does not establish user-context write permission. X test posting is therefore pending those credentials/permissions and account entitlement/credits validation. No X test post was made, and paid access requirements were not inferred for this account.

## Verification evidence (2026-10-06)

- 81 offline tests pass, including actual child unittest execution, HTTP authentication/CSRF/allowlist, runtime enable/interval/disable, force fetch/counts, persisted jobs, timeout/redaction, mocked publisher identity checks/E2E and HTTP 429 cooldown protection.
- A browser-triggered full regression run passed with actual runner output and duration.
- Real browser Fetch Now for `asaptestlab.bsky.social`: **5 fetched / 2 new**. The newly discovered `New paper alert!` post appeared in Review Queue as `candidate / pending`, not automatically approved.
- Live interval changed to 3 seconds and enabled via Admin: successful fetch timestamps advanced without launching another process. Disable stopped scheduled polling; preview settings were restored to disabled / 1800 seconds.
- Browser verification used a copied Store/configuration, preserving the user's original approved/rejected decisions. Live network requests were real; no source posts were generated by mocks during this browser verification.
- Real publisher/E2E verification is **pending local test credentials**: neither an explicit test handle nor app password was available in the agent's environment/local ignored configuration. Mocked tests prove code paths, not real posting permission. LinkedIn remains an unrelated external API-access blocker.

Production hosting/Docker verification and unrelated FR closure work remain separate. No commit or push was performed.
