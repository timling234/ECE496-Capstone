# Manual verification — FR-1 through FR-5

Closure policy: FR-2–5's agreed MVP components are now Done based on the verified behaviors below. Some earlier "not yet implemented" gaps are optional/deferred, not closure blockers. Required administrator and renderer work remains with FR-6/7/9. See [MVP closure audit](mvp_closure_audit.md) for exact boundaries, dependencies, and the pending decision batch.

## Primary commands

From the ECE496 repository root:

```powershell
python run_tests.py
python run_demo.py
```

The test runner currently reports `Ran 81 tests` and `OK`. It returns nonzero if a test fails or cannot import. It discovers unittest modules in all subfolders of `tests/` using `test_*.py` or `*_test.py`; existing API POC scripts are not automatically executed as live requests.

The menu has FR-1 through FR-5, **6. Run all safe offline demos**, and **0. Exit**. Option 6 runs simulated ingestion, normalization, storage, filtering, duplicate detection and offline replay. Every offline path uses fixtures and temporary databases. No credentials, APIs, real Store or cursors are used. The temporary databases are removed afterward.

If this machine has no `python` command, set this session-only PowerShell alias once, then use the same primary commands:

```powershell
Set-Alias -Name python -Value 'C:\Users\lingt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## FR-1 — Source ingestion

**WHAT IT MEANS:** Retrieve posts from selected source accounts so they can enter our common pipeline.

**CURRENTLY IMPLEMENTED:** X = implemented POC; Bluesky = implemented POC. Live menu option 1 lets you choose X, Bluesky or both, then requires affirmative confirmation. It retrieves up to three posts per selected provider, prints only counts and saves to an isolated temporary SQLite database. Option 6 demonstrates simulated X/Bluesky ingestion without API access.

**NOT YET IMPLEMENTED:** LinkedIn = pending external API approval. Scheduler = not implemented. Final account configuration/provider contract and operational retry handling remain incomplete.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **1**, then **1 = X**, **2 = Bluesky**, or **3 = Both**; enter **y** to confirm live requests. Choose **0** or decline confirmation to cancel. X requests may consume API credits. The existing ignored X token file is required for X; the Bluesky path uses public reads.

**EXPECTED:** A clear LIVE warning followed by `x: retrieved N post(s)` / `bluesky: retrieved N post(s)` and temporary stored-row count. A successful request may return zero posts. Authentication/network failures show a failure type and `RESULT: FAIL`, without printing credentials or response bodies. For safe offline verification choose **6**: `FR-1 ... SIMULATED`, X=1 and Bluesky=1, `RESULT: PASS`. Simulation is not evidence of current live API health.

**INSPECT:** The live demo reports counts from its temporary database and deletes it afterward. No actual Store/cursor changes. To inspect previously ingested real data read-only:

```powershell
python src/store_poc.py --inspect
```

Expected: source counts (original POC: X=3, Bluesky=3); no API calls or writes.

## FR-2 — Common normalization

**WHAT IT MEANS:** Different provider formats become one set of fields that later stages can read.

**CURRENTLY IMPLEMENTED:** X and Bluesky mappings produce `platform`, `account_id`, `post_id`, `created_at`, `text`, `post_url`, `links`, `media`, `metadata`, and `raw`.

**NOT YET IMPLEMENTED:** LinkedIn mapping, complete type/schema validation and full provider-format coverage.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **2** (or **6** for all offline paths).

**EXPECTED:** Two labelled records, `X record -> common fields` and `Bluesky record -> common fields`, show the same ten field names. Both retain `New paper published`, the same example paper link, image details, provider metadata and original provider record. `Same common schema: PASS`, `Raw provider records retained: PASS`, `RESULT: PASS`.

**INSPECT:** Read each printed field. Source platform/account/native ID/URL legitimately differ; shared schema does not mean identical provider identity. Printed raw data is synthetic fixture data only.

## FR-3 — SQLite storage and idempotency

**WHAT IT MEANS:** Posts survive database reopen; re-importing the same provider/native ID updates that row without resetting editorial state.

**CURRENTLY IMPLEMENTED:** SQLite write/readback, unique provider/native identity, repeat-import upsert, preservation of existing publication/priority fields, offline derived-stage replay.

**NOT YET IMPLEMENTED:** Original source-version history, administrator decision history, deployment-grade migration/operations.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **3**.

**EXPECTED:** `Rows after first import: 3; after repeat import: 3`. Reopened rows show X A, Bluesky B and X C. The demo seeds an existing editorial fixture on A solely to test preservation: `publication=approved, priority=7` remains after repeat import. `Readback after reopen: PASS`, `No extra source row: PASS`, `Editorial state preserved: PASS`, `RESULT: PASS`.

**INSPECT:** Printed values are queried from temporary SQLite before and after re-import. The seeded approved state is fixture setup, not a new approve UI or product workflow. No real post is approved.

## FR-4 — Default filtering

**WHAT IT MEANS:** Relevance evaluation happens before review candidacy. Passing relevance is separate from publication approval.

**CURRENTLY IMPLEMENTED:** Empty rules allow every stored post; derived candidate state is separate from source/publication state. A predicate extension interface exists, without actual keyword/tag rules.

**NOT YET IMPLEMENTED:** Actual rule configuration, keyword/tag policies, administrator inclusion/removal controls.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **4**.

**EXPECTED:** `empty rules -> all posts pass -> review candidates`; three SQLite states show `candidate` with publication `pending`. `Source posts preserved: PASS`, `Candidate != approved; publication pending: PASS`, `RESULT: PASS`.

**INSPECT:** Printed state rows join the separate `relevance` and `posts` tables. Original source rows are compared before/after filtering. Existing publication decisions would be preserved; filtering never approves or resets them.

## FR-5 — Exact duplicate candidates

**WHAT IT MEANS:** Matching announcement text can be grouped for review while preserving each source record.

**CURRENTLY IMPLEMENTED:** Exact matching after trimming/collapsing whitespace. Case and punctuation are preserved; empty text is not grouped. Cross-platform matches persist separately in `duplicate_candidates`.

**NOT YET IMPLEMENTED:** Fuzzy similarity thresholds, automatic representative choice, administrator selection/approval and source priority. None is inferred from group membership.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **5**.

**EXPECTED:**

```text
X post A       -> duplicate group 1
Bluesky post B -> duplicate group 1
X post C       -> no duplicate group
Source posts preserved: PASS
Review candidates preserved: PASS
Publication still pending: PASS
RESULT: PASS
```

**INSPECT:** The demo reopens SQLite and joins source rows with duplicate memberships. Human-readable group 1 corresponds to the same stored group ID for A and B. C has no membership. All three source posts remain stored; all remain pending. No representative is assigned. The original module-based demo remains available internally.

## Offline reprocessing

**WHAT IT MEANS:** Re-evaluate saved content through default relevance and exact duplicate stages without re-fetching an API.

**CURRENTLY IMPLEMENTED:** `--reprocess` requires an existing database and updates only derived stages. Missing databases fail without creation. Source rows and publication decisions are preserved.

**NOT YET IMPLEMENTED:** User-defined processing configuration/history.

**COMMAND:**

```powershell
python run_demo.py
```

Choose **6**. The last offline section is reprocessing.

**EXPECTED:** `review candidates: 3; duplicate candidate groups: 1`, `Source rows and publication decisions unchanged; no API calls.`, `SQLite readback: 3 candidates; 1 duplicate group`, and `RESULT: PASS`. Final summary: `ALL SAFE OFFLINE DEMOS: PASS`.

**INSPECT:** Reported counts are read from the temporary database after replay. A source/editorial snapshot is compared before/after. Replay of real data is intentionally separate: `python src/store_poc.py --reprocess --db <existing-database-path>` modifies derived tables on that chosen database; use option 6 for safe manual verification first.

## FR-6/FR-7 — One representative per duplicate group (Option A)

**WHAT IT MEANS:** An administrator explicitly chooses one group member for editorial approval. A duplicate group does not approve anything by itself.

**CURRENTLY IMPLEMENTED:** Internal service validates current candidate membership and stores one selected provider/native ID plus actor/time in a separate `group_approvals` table. Either provider can be selected. Same-choice retries are idempotent. A conflicting second choice is blocked. Re-import/reprocessing preserve the recorded decision and original source rows.

**NOT YET IMPLEMENTED:** Administrator UI/authentication, changing/revoking an existing approval, ungrouped-item controls, feed ordering, notifications and website publication. The actor parameter records attribution; it does not authenticate a user. This is a fixture demonstration, not a real administrative endpoint.

**COMMAND:**

```powershell
python run_tests.py
python run_demo.py
```

Choose **7** for the selection demo, or **6** to include it with every safe offline demo.

**EXPECTED:**

```text
Duplicate group: X A + Bluesky B. Neither is automatically approved.
Fixture operator explicitly selects X A (no platform priority).
X post A -> selected representative, editorial approval recorded
Bluesky post B -> not selected, not automatically rejected
X post C -> no approval recorded
Exactly one persisted representative: PASS
Second distinct selection blocked: PASS
Original source rows preserved: PASS
RESULT: PASS
```

**INSPECT:** The demo closes/reopens temporary SQLite and reads `group_approvals`: selected X A, actor `demo-admin`, one approval row. Legacy source-table publication fields stay pending; the new editorial record is separate. No renderer or public-feed query consumes it yet. Source rows are compared before/after and the temporary database is removed. Approval replacement is intentionally blocked until that workflow is confirmed.

## Scheduled polling sanity check

Run `python run_demo.py` and choose **8**. The temporary-database fixture verifies initial ingestion, skipping sources before they are due, X failure while Bluesky continues, and persisted scheduling after reopening. Expected final checkpoints: X1 and B2; three original source posts; all six checks PASS. Option **6** now runs all eight offline demos. No live APIs are called.

`python run_polling.py --once` uses the shipped disabled configuration: no enabled sources, no API requests and no Store changes. Docker verification remains pending; see [polling and deployment](polling_and_deployment.md).

## Browser vertical slice (2026-10-05)

The immediate priority is now a usable browser management console and public feed. Single-admin environment-password login, protected sessions, CSRF, no SSO and no multi-admin are explicitly confirmed. Do not reopen those decisions. Approve/reject/withdraw and duplicate representative selection are implemented; selecting another representative atomically removes the former representative's publication eligibility. Rejection applies to the selected source item and does not silently reject its related records. No automatic source priority exists.

`run_app.py` starts a loopback-only server over the existing `.tmp/store_poc.sqlite3`. Source provenance is separate from `editorial_decisions`, `editorial_actions`, and `feed_order`. The public read model requires both current candidacy and editorial approval, with at most one visible copy per current duplicate group. A content fingerprint prevents changed content from inheriting approval. The initial service API remains compatible; browser decisions take precedence over older service decisions.

FR-6: newest-first deterministic default, manual pin and explicit numeric order are verified. FR-7: protected review views, editorial actions/history and source/interval configuration are verified. Saved source settings are used on polling-worker restart, never by an implicit live fetch. FR-9: approved-only HTML, source text/time/platform/links/images, presentation controls and iframe embedding route are verified locally. FR-11: creation, editing with retained prior text, approval and withdrawal are verified. These MVP components are Done. Production hosting and actual MSRG installation are still outstanding deployment/integration work; this result makes no production deployment claim.

Implementation: `src/web_app.py`, `src/web_editorial.py`, `run_app.py`. No new external REF code/reference was used. Existing exact-match processing and SQLite provenance are reused. `tests/test_web_app.py` verifies the HTTP session/CSRF/editorial path, regression for browser favicon requests, group switching, source preservation, persistence, manual edits, order, presentation and configuration. Full suite: **73 tests pass**. Browser verification used a disposable copy of the six real stored X/Bluesky posts: approve → public image/link appears; withdraw → disappears. Two preview-only manual announcements verified duplicate selection → exactly one public copy. Original Store source records remained unchanged.

Run instructions: [browser application](browser_application.md). Existing outstanding notification/deployment/scope decisions are recorded separately; already confirmed console/lifecycle/manual-announcement choices are no longer pending.

## Operational admin milestone (2026-10-06)

Current operation is now **one command: `python run_app.py`**. The app owns a single runtime polling worker, reads saved settings continuously, and applies source/account/enabled/interval changes without a second terminal or restart. The current default is 1800 seconds, explicitly confirmed by the operational-console request; 3 seconds remains valid for short testing. Fetch Now, live source status, fetched/new counts, safe errors, worker/dashboard health and a compact engineering console are implemented. This supersedes earlier instructions requiring a separate polling process or restart to apply Admin settings.

FR-1/7 runtime controls are verified with real browser Bluesky fetching: 5 fetched / 2 newly discovered; the new paper post becomes a pending review candidate. Three-second scheduled polling and disabling were browser-verified. Existing editorial/provenance logic is retained. FR-10 development tooling uses real allowlisted tests with timeout/redaction, persisted results and no arbitrary shell input. The suite passes 81 tests. Real test publishing and candidate E2E are implemented and mock-verified, but their live verification is blocked only by missing explicit local Bluesky test credentials. Do not count mocked publishing as a successful real write. Development controls default off (`ASAP_DEV_TOOLS=1` explicitly enables them).

Implementation boundaries: `src/app_runtime.py` (worker/configuration), `src/polling.py` (status/count migration and force/cooldown), `src/console_ui.py` / `src/web_app.py` (protected console/controls), `src/dev_tools.py` (allowlisted jobs/explicit test publisher), `run_app.py` (single launch/local credential helper), `tests/test_operations.py` (acceptance/security). No Horizon code is used in these new components; existing provider/model/detection concepts remain referenced separately. Official Bluesky protocol documentation and X authentication mapping are recorded in design references.

See [operations console](operations_console.md) for current run/setup instructions, acceptance evidence and X posting investigation. LinkedIn remains **⏸ EXTERNAL BLOCKER — API access pending**. No LinkedIn alternatives, keyword rules, fuzzy duplicate policy, source priority, production deployment, commit or push were introduced.
