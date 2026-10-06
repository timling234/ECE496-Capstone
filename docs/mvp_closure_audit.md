# MVP closure audit

Current audit: 73 tests pass via `python run_tests.py`; branch `dev`; existing work preserved. No commits/pushes authorized. This audit replaces optional-enhancement-driven yellow statuses. Historical milestone logs remain historical.

## Acceptance boundaries and remaining required work

| FR | Closure result / remaining acceptance work | Classification |
| --- | --- | --- |
| FR-1 | X/Bluesky configurable scheduled ingestion, pagination, atomic checkpoints, independent failure handling and safe status reporting are implemented and verified. | LinkedIn: ⏸ EXTERNAL BLOCKER — API access pending. Production default polling frequency still needs confirmation; runtime accepts explicit intervals. |
| FR-2 | Shared ten fields for currently accessible X/Bluesky text/link/image posts, missing optional fields, retained originals; normalization fixtures/demos pass. | Done for current MVP. LinkedIn mapping/validation externally blocked, not a blocker for the common model. |
| FR-3 | Durable current raw/common records, separate processing/editorial state, provider-ID uniqueness, reopen, rollback and replay with decisions preserved; tests pass. | Done for current MVP. Source-version archives are a deferred enhancement, not a current closure gate. |
| FR-4 | Generic configurable stage; empty rules allow all; injected predicates evaluate candidacy; originals and approval are unchanged; tests pass. | Done. Keyword/tag rules deferred. Required administrator removal/rejection belongs to FR-7; feed exclusion belongs to FR-9. |
| FR-5 | Exact nonempty text groups after conservative whitespace normalization, both providers supported; persisted membership, rerun/source preservation verified; no automated selection. | Done for exact-match MVP. Fuzzy/AI similarity deferred. One selected visible copy remains required in FR-6/9. |
| FR-6 | Browser selection, atomic replacement, single-post approval, deterministic newest-first, pin and manual numeric order verified. | 🟢 Done for agreed MVP. |
| FR-7 | Single-admin environment password, protected sessions/CSRF, review/actions/history and source/interval configuration verified. | 🟢 Done for local MVP; hosting remains FR-10. |
| FR-8 | Real delivery adapter, recipient configuration, new-review-item deduplication, retries/failure visibility and review link. | Required implementation remains; notification channel pending. Live delivery may require external credentials, but adapter/tests can be completed locally. |
| FR-9 | Approved-only public renderer, supported text/links/media, accent/font/origin controls and embedding page verified. | 🟢 Done for local renderer MVP; actual MSRG installation remains deployment/integration work. |
| FR-10 | Provider interface, disabled configuration example, installation notes and automated test/demo workflow verified; Docker packaging prepared. | Docker image build/run unverified due to engine access denial; permissive license decision pending. |
| FR-11 | Manual announcements create/edit/approve/withdraw, prior text retained, shared review model verified. | 🟢 Done; scope confirmed by current instruction. |
| FR-12 | Independent site feeds if included. | Decide include in MVP versus explicitly Deferred. |

Deferred enhancements do not block Done: fuzzy/AI duplicate matching, concrete keyword/tag policies, automatic platform ranking, additional unsupported-provider features, generalized multi-user systems (subject to the authentication choice), and source-version archives. FR-11/12 are not silently deferred; their scope awaits Tim's answer.

Original provider data is never edited by filtering/detection/editorial actions. Current ingestion stores the latest provider snapshot per native identity. If changed-source review policy requires additional snapshots, implement that necessary support with FR-6/7 instead of claiming the current store already archives all versions.

## Earlier decision batch — historical recommendations; confirmations below take precedence

This earlier batch is historical. The current browser milestone confirms single-admin authentication, editorial controls, newest-first ordering, local mock feed and manual announcements. Do not treat those choices as unanswered. Only remaining unconfirmed topics may require future clarification.

| Topic / FR | Recommended MVP decision | Alternative |
| --- | --- | --- |
| Management/authentication (FR-7) | Responsive web management console; one administrator login with password supplied via environment, protected sessions and CSRF. No self-registration. | Institutional SSO / multiple administrator identities now. |
| Editorial lifecycle (FR-6/7) | Review one announcement at a time: duplicate group chooses one representative; ungrouped post can be approved; explicit atomic representative switch; reject announcement or withdraw approval; all actions logged. Re-fetch alone never auto-approves. | Require withdrawal before switching; specify different rejection/approval granularity. |
| Source edits (FR-6/7) | Material source-content changes invalidate publication eligibility and require review again; ordinary re-fetch of unchanged content preserves approval. | Keep edited content approved until an administrator withdraws it. |
| Feed order (FR-6) | Newest source time first, with administrator pin/order overrides and deterministic tie-breaking. No platform priority. | Strict manual ordering or another specified ordering. |
| Polling (FR-1) | Configurable 30-minute default per enabled source; source must be explicitly enabled before live polling. | Hourly, 15-minute, or another frequency/budget. |
| Notifications (FR-8) | SMTP email once per new review item, duplicates combined, linked to review queue; configurable recipient and environment-held credentials. Test with a local mail capture server. | Webhook or another named channel. |
| Website/deployment boundary (FR-9/10) | Separately hosted Docker app serves a responsive iframe and public approved-only feed. Verify locally using an embedding page; production domain/site embedding is coordinated with Thomas and tracked as an external installation dependency if unavailable. | Require a specified live production host/site installation before accepting the MVP delivery boundary. |
| FR-11 / FR-12 scope | Include manual announcements (original specification); defer multi-site support beyond the single MSRG MVP. | Defer both, or include both now. |
| One-hour objective (O-1) | Measure API-available content → review-ready and notification dispatch ≤1 hour under normal operation; report provider latency and human approval separately. | Measure final public website appearance, including manual approval time. |
| Project license (FR-10) | MIT, following the permissive-license project requirement. | Apache-2.0 or another agreed permissive license. |

LinkedIn is retained as an external dependency; no simulated implementation is counted as LinkedIn support. No fallback behavior needs to be invented to complete the accessible-provider MVP.

## Execution after decisions

Complete schedulable current-provider ingestion and provider interface; finish the authenticated review/editorial lifecycle; add notification delivery and approved-only public feed/iframe; complete Docker/configuration/documentation and chosen scope items. Run acceptance tests/demos and turn each FR green as soon as its own agreed MVP criteria pass. Do not wait for unrelated FRs or optional enhancements to close a verified component. Stop only for a genuinely new material decision or unavailable external dependency, and continue independent work.

## LinkedIn dependency clarification (2026-10-05)

The Community Management API application has been submitted. LinkedIn remains in the planned architecture as **⏸ EXTERNAL BLOCKER — API access pending**. This dependency does not prevent closure of FR-2 through FR-11 for their agreed MVP boundaries.

The [restricted-use documentation](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-09) is recorded for separate policy review. It does not change the current implementation plan. No alternative LinkedIn retrieval work is planned now. If access is granted, continue the planned API integration and validation; approval itself is not blanket permission for downstream public-feed use. If rejected, revisit policy as a possible reason and then evaluate compliant integration paths.

## Verified polling increment

The suite passes 66 tests. X/Bluesky adapters and the single-worker scheduler support explicit account/interval configuration, incremental pagination, atomic storage/processing/checkpoint updates, independent source failures, persisted restart scheduling and HTTP 429 retry timing. Empty configuration is disabled and performs no live requests or database changes. No production polling frequency has been selected. See [polling and deployment](polling_and_deployment.md).

Docker packaging is prepared, but image build/run is unverified: this session cannot access the Docker engine, and the permission interface could not represent its named-pipe path. This is a local verification limitation separate from LinkedIn. The outstanding product-decision batch remains unanswered.

## Browser vertical slice (2026-10-05)

The immediate priority is now a usable browser management console and public feed. Single-admin environment-password login, protected sessions, CSRF, no SSO and no multi-admin are explicitly confirmed. Do not reopen those decisions. Approve/reject/withdraw and duplicate representative selection are implemented; selecting another representative atomically removes the former representative's publication eligibility. Rejection applies to the selected source item and does not silently reject its related records. No automatic source priority exists.

`run_app.py` starts a loopback-only server over the existing `.tmp/store_poc.sqlite3`. Source provenance is separate from `editorial_decisions`, `editorial_actions`, and `feed_order`. The public read model requires both current candidacy and editorial approval, with at most one visible copy per current duplicate group. A content fingerprint prevents changed content from inheriting approval. The initial service API remains compatible; browser decisions take precedence over older service decisions.

FR-6: newest-first deterministic default, manual pin and explicit numeric order are verified. FR-7: protected review views, editorial actions/history and source/interval configuration are verified. Saved source settings are used on polling-worker restart, never by an implicit live fetch. FR-9: approved-only HTML, source text/time/platform/links/images, presentation controls and iframe embedding route are verified locally. FR-11: creation, editing with retained prior text, approval and withdrawal are verified. These MVP components are Done. Production hosting and actual MSRG installation are still outstanding deployment/integration work; this result makes no production deployment claim.

Implementation: `src/web_app.py`, `src/web_editorial.py`, `run_app.py`. No new external REF code/reference was used. Existing exact-match processing and SQLite provenance are reused. `tests/test_web_app.py` verifies the HTTP session/CSRF/editorial path, regression for browser favicon requests, group switching, source preservation, persistence, manual edits, order, presentation and configuration. Full suite: **73 tests pass**. Browser verification used a disposable copy of the six real stored X/Bluesky posts: approve → public image/link appears; withdraw → disappears. Two preview-only manual announcements verified duplicate selection → exactly one public copy. Original Store source records remained unchanged.

Run instructions: [browser application](browser_application.md). Existing outstanding notification/deployment/scope decisions are recorded separately; already confirmed console/lifecycle/manual-announcement choices are no longer pending.
