# Polling and current runtime packaging

The existing API POCs and Store inspection remain available. New current-provider polling uses `src/providers.py` and `src/polling.py`. There is no default production frequency: enabled sources require an explicit positive `interval_seconds`. The example configuration keeps X, Bluesky and LinkedIn disabled. LinkedIn has no operational adapter yet; enabling it fails with access-pending status.

## Safe one-command checks

```powershell
python run_tests.py
python run_demo.py
```

Tests: 66 pass. In the menu choose **8** for the fake-clock polling demo, or **6** for all eight safe offline demos. Expected: at t=0 both fixture sources succeed; t=5 makes no fetch; t=10 X fails while Bluesky stores its new post; reopened SQLite retains X1/B2 checkpoints and three source rows. `RESULT: PASS`; temporary database removed. No real Store, cursor, token or API access occurs.

```powershell
python run_polling.py --once
```

Expected: `No enabled sources. LinkedIn API access pending. No API requests or Store changes.` The shipped configuration is deliberately inert, not a live demonstration.

## Configured polling

Copy `config/polling.example.json` to an ignored local configuration file such as `.tmp/polling.local.json`. Choose account(s), explicit intervals and enabled flags. Keep LinkedIn disabled while access is pending. X reads the existing ignored bearer-token file; a configured relative `token_file` resolves from the repository root. No token values go in configuration. First polling seeds one recent page, preserving POC bootstrap behavior; it does not bulk-import full history. Subsequent X polls paginate from `since_id`; Bluesky paginates to the previous observed author-feed boundary and refreshes that overlapping record. Pins are excluded from the chronological boundary, as in the public API default. A deleted Bluesky boundary causes the available pages to be reprocessed idempotently.

An explicit configuration alone does not start requests. Actual live commands additionally require `--live` and may consume X API credits:

```powershell
python run_polling.py --config .tmp/polling.local.json --once --live
python run_polling.py --config .tmp/polling.local.json --live
```

The second command runs until Ctrl+C. Configuration is read on startup; restart after changing it. This is one scheduler worker per database. No default polling frequency/budget was selected on Tim's behalf.

Each source's `source_poll_state` retains checkpoint, attempt/success times, safe error type and next due time. Source data, derived stages and checkpoint commit together. Failure preserves the previous checkpoint and successful data, records no raw error body, and does not prevent another source from polling. HTTP 429 retry/reset headers extend the wait. These are engineering safeguards, not notification or publication policy. Polling never automatically approves anything.

## Docker packaging and verification status

The Dockerfile packages the current standard-library runtime and verification commands as an unprivileged user. `/data` is the persistent database location. Sources remain disabled by default. `.dockerignore` excludes tokens, environment secrets, cursor files, SQLite data and temporary artifacts; the Dockerfile copies only source/test/config/entry-point paths. Credentials are supplied separately through read-only mounts and an explicit local configuration; no secret is baked into the image.

Docker build/run has **not been verified in this Codex session**: engine access was denied (`docker_engine` pipe), even though the Docker executable is installed. This is a verification-environment dependency, separate from LinkedIn access; FR-10 is not claimed Done. Once engine access is available, required checks are:

```powershell
docker build -t asap-mvp:local .
docker run --rm asap-mvp:local python run_tests.py
@('6', '0') | docker run --rm -i asap-mvp:local python run_demo.py
docker run --rm asap-mvp:local
```

Expected: build succeeds; 66 tests pass; all eight safe demos pass; default image exits without API requests because sources are disabled. Container/image verification and the project-license decision remain FR-10 closure work. This is local runtime packaging, not a deployed management UI, renderer or final MSRG installation.
