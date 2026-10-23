# MSRG News integration — local implementation and deployment contract

FR-6/7/8/9/10. Living design, 2026-10-13. REF-MSRG-NEWS is a visual/template reference, not copied service code.

## What the output is

ASAP is a separate Python service with SQLite and a polling/notification worker. `/admin` is protected. `/feed` is a public HTML page that queries only approved current candidates and one selected representative per duplicate group. Pin precedes newest-first; manual numeric order was removed from the active UI/endpoint and public sorting (legacy values remain stored). Pin/unpin stays on the originating admin view.

The MSRG website is Hugo on GitHub Pages. GitHub Pages serves static files and cannot run our Python backend. Host ASAP separately on an always-running server with HTTPS; the website includes its `/feed` page in an iframe. Approval changes appear on the next feed load without a Hugo rebuild. The iframe does not use admin credentials, expose SQLite, or call platform APIs in visitors' browsers.

## Current MSRG template and exact insertion point

Reference inspected: https://github.com/MSRG/msrg.github.io/blob/main/layouts/index.html and https://msrg.github.io/ . The News `content-panel news-panel` currently conditionally embeds the Elfsight platform script and `elfsight-app-...` div using `$newsApp`. Replace that conditional embed block with the iframe below when the hosted ASAP URL is confirmed. Retain the existing News heading, outer panel, and LinkedIn link. Remove that widget block only; do not remove unrelated scripts. This repository contains instructions only; the MSRG repository has not been changed.

```html
<iframe
  src="https://YOUR-ASAP-HOST/feed"
  title="Approved MSRG news"
  loading="lazy"
  style="display:block;width:100%;height:620px;border:0;border-radius:12px"
></iframe>
```

Replace `YOUR-ASAP-HOST` with a real publicly reachable HTTPS hostname. `localhost` works only on the developer's own computer and is not a deployment URL. A different origin is fine: displaying HTML in an iframe does not require CORS. The host must allow framing for `/feed`; admin pages remain `X-Frame-Options: DENY`. If MSRG has a Content Security Policy, allow the ASAP hostname in its `frame-src`. Use HTTPS for both sites, and preserve the app's no-cache behavior for fresh publication state.

The local `/embed-demo` demonstrates that exact iframe relation in a white rounded News panel. `/feed` supplies horizontal responsive cards with platform/date, first available image, full scrollable text, and original link. This is a visual adaptation of the provided screenshot; it does not implement fake likes/comments/shares or claim LinkedIn ingestion works. LinkedIn remains API-access pending. Font size/link color/origin are set in Settings and rendered inside the iframe. Parent-site CSS cannot directly style a cross-origin iframe's contents. Height is fixed at 620px for this milestone; no cross-origin messaging or automatic height contract is assumed.

## Docker local packaging

From the repository, set `ASAP_ADMIN_PASSWORD` in the process environment and run:

```powershell
docker compose config --quiet
docker compose up --build -d
```

Open http://localhost:5000/admin and http://localhost:5000/embed-demo . Example sources start disabled. Data, source configuration and outbox persist in `asap-data` mounted at `/data`. Restarting containers preserves that volume; do not use `down -v` when retaining data. Existing local SQLite data is not automatically copied into the container. For migration, stop the original application, back up SQLite and configuration, copy into `/data`, and ensure ownership UID/GID 10001. X token files must be mounted read-only separately and referenced by their container path in source configuration; never include them in the image.

The image runs as non-root. Compose maps the service to loopback for local use and disables developer tools. For public deployment put an HTTPS reverse proxy in front of this loopback port, protect admin access at the deployment layer, preserve security headers and inject runtime secrets outside version control. Choose the hostname/hosting with the team; no remote deployment performed here.

## Email notification setup

In Settings enable Notifications, choose Email, enter one recipient, and save. The event is fixed: whenever a **new post first becomes a review candidate**. Each distinct platform/native ID is an event even if it joins an exact duplicate group. Existing candidates are not retroactively emailed. Re-fetch/reprocess does not repeat an event. Filtered content not yet a candidate does not notify; publication approval is separate. SMS is explicitly deferred and disabled by the user's decision.

Supply server environment variables: `ASAP_SMTP_HOST`, `ASAP_SMTP_FROM`, optionally `ASAP_SMTP_PORT` (587 default), `ASAP_SMTP_SECURITY` (`starttls` default or `ssl`, commonly port 465), `ASAP_SMTP_USERNAME`, `ASAP_SMTP_PASSWORD`. Never enter SMTP credentials in the admin browser or commit an environment file. Mail transport configuration is reported independently of opt-in status. One valid recipient is required when enabled.

Candidate event and outbox insertion share the SQLite transaction; worker delivery is independent of provider ingestion. Failures retain only exception type, retry with bounded exponential delay, and never change posts/approval state. Settings displays pending/sent counts and sanitized last failure. Turning notifications off pauses pending messages; re-enabling resumes them (their original recipient is retained). SMTP acceptance is recorded persistently; delivery is at-least-once across a crash between SMTP acceptance and the database sent marker. Actual inbox delivery needs configured SMTP and an authorized live test; offline injected-transport verification does not prove inbox receipt.

## Verification boundary

See tests/test_notifications.py and tests/test_integration_ui.py for candidate/replay/rollback/restart, retry/TLS settings, CSRF, Pin navigation, removed manual order, approved-only horizontal feed and iframe headers. Docker engine build/run and real SMTP delivery must be separately reported; file/config preparation alone does not close those deployment dependencies.


### Verified integration results (2026-10-13)

99 tests pass locally and inside the Python 3.12 Linux Docker image. Docker image build, non-root UID 10001, isolated web/worker startup, approved-state volume persistence across restart, and exclusion of token files/local databases from `/app` verified. Compose configuration validation passed. Browser verified the News iframe, Pin retaining Published, notification opt-in/address save and SMS disabled. This supersedes earlier Docker-engine-unavailable notes: the user started the engine and build/run verification was completed. Final public hosting/install and real SMTP inbox receipt remain external configuration/deployment work. No emails sent to a real recipient; no commits/pushes.

For HTTPS deployment set `ASAP_COOKIE_SECURE=1` so admin session cookies carry Secure. Keep 0 for loopback HTTP testing. The HTTPS proxy must permit only the intended public routes and preserve admin framing denial.
