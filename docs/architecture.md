# ASAP high-level architecture — living design

This is a living design, revised as implementation and stakeholder feedback provide evidence. Requirements: [functional_requirements.md](functional_requirements.md). External inspiration: [design_references.md](design_references.md). Component progress does not imply completion of a whole FR.

## Component status

| Component | Status | Evidence / remaining work |
| --- | --- | --- |
| X / Bluesky adapters | 🟢 Done | Configurable accounts, shared normalized output and incremental pagination verified with mocked API responses. |
| Common normalization | 🟢 Done | X/Bluesky MVP mappings verified; LinkedIn validation alone is externally blocked. |
| SQLite ingest store | 🟢 Done | Current payload/common fields/state, restart, idempotency, replay and rollback verified; version archives deferred. |
| Scheduler / provider contract | 🟢 Done | Explicit intervals, atomic per-source checkpoints, restart scheduling, failure isolation and rate-limit waits verified. |
| Docker packaging | 🟡 In Progress | Files prepared; image build/run verification blocked by local engine access. |
| LinkedIn adapter | ⏸ External Blocker | API access unavailable; current-provider work continues independently. |
| Relevance stage | 🟢 Done | Configurable default-pass-through stage verified; actual keyword/tag rules deferred; admin actions belong to FR-7. |
| Duplicate candidates | 🟢 Done | Exact matching/persistence verified; fuzzy strategy deferred; selection/public rendering belong to FR-6/9. |
| Explicit representative selection | 🟢 Done | Browser selection/replacement verified; single approved representative; no platform priority. |
| Admin UI / authentication / replacement / withdrawal / order | 🟢 Done | Confirmed single-admin login/session/CSRF, editorial controls, pin/order and source configuration verified. |
| Notifications | ❓ Decision Needed | Channel and recipients require confirmation. |
| Customizable iframe renderer | 🟢 Done | Local approved-only feed and embedding route; configurable link color/font/origin; production installation remains deployment work. |
| Developer verification harness | 🟢 Done | Root test runner and FR-1–5 menu verified; this completed utility does not mean whole FR-10 is Done. |
| Manual announcements | 🟢 Done | Create/edit/review/approve/withdraw and prior-text retention verified. |
| Site separation | ❓ Decision Needed | Multi-site scope still recorded separately. |

Uses the FR status legend, including External Blocker and Deferred. Current MVP components close when their criteria pass; required administrator/rendering behavior remains with its own components. See [mvp_closure_audit.md](mvp_closure_audit.md) for the remaining acceptance work and decision batch. The diagram below shows intended flow, not implemented coverage.

## Current baseline

`tests/x_api/x_api_test.py` polls X and maintains its own latest-ID cursor; `tests/bluesky_api/bluesky_api.py` reads a public author feed; `src/store_poc.py` fetches both, normalizes into shared fields, upserts SQLite, then runs default filtering and exact duplicate grouping. These data components remain POCs; the scheduler, final adapter contract, admin backend and public feed are unimplemented. LinkedIn access remains gated by platform approval.

`load_posts(conn)` restores common fields, raw objects, metadata, and stored state offline. `--inspect` opens the existing database read-only and reports counts without APIs. The current suite has 33 passing tests (readback originally had ten); the previously inspected real database contained three records per provider. Repeat imports still replace the latest source snapshot, so immutable source-version history is unimplemented. Processing leaves source rows untouched; reserved editorial fields are preserved, but no administrator workflow exists.

## Proposed components and flow

```text
Configured accounts + refresh schedule
                 |
         Provider adapters (X, Bluesky, LinkedIn when authorized)
                 | raw provider records + fetch diagnostics
         Normalization/validation
                 | common post + original payload
         Durable ingest store (idempotent source identity)
                 |
         Rule evaluation / relevance candidates
                 |
         Duplicate candidate groups
                 |
         Review queue + notification ------> Administrator
                 |                             |
                 +<--- approve / reject / withdraw / order
                 |
         Published feed read model
                 |
         Website integration / responsive renderer
```

The store also holds configuration, source/fetch state, decision history, and publication state, though these need not be in one table. Manual announcements (if retained) enter after provider ingestion, through validation and review. A later provider can be added behind the same raw-to-common contract. The management backend is a control plane for configuration and decisions, not a one-time stage in a linear pipeline.

## Ordering decision

Implemented path: ingest → normalize → store → default relevance → exact-text duplicate candidates. `process_stored` also supports offline replay via `--reprocess`, opening an existing database only and rerunning derived stages. Detection consumes the complete current candidate set and replaces only `duplicate_candidates` memberships. `exact_text_groups` is a separate replaceable strategy; whitespace-only normalization is case/punctuation sensitive and excludes empty text. Source records and publication state are unchanged by processing. Stable group IDs identify candidate groups, not publication representatives. These increments are verified by 24 offline tests and an isolated SQLite demo; administrator workflow and public output remain unimplemented.

Current FR-4 MVP decision (architecture B): the relevance stage always runs after storage. Empty rules allow every ingested post to become a candidate. `src/relevance.py:mark_candidates` persists derived candidate/filtered status independently of `posts.publication_status`; no approval occurs here. Configured predicate extensions can evaluate posts, but no keyword/tag/provider rule is implemented. Source payloads are preserved. Sixteen offline tests verify the current pipeline and state separation. Administrator transitions and actual rule configuration remain future decisions.

The proposed `Fetch → Normalize → Store → Filter → Deduplicate → Prioritize → Manage → Publish` is a useful sketch but hides two important distinctions:

1. **Persist provenance before curation.** Save original provider payload and a normalized representation before relevance and duplicate decisions. Changed rules can then be rerun without paying for or waiting on another API call. Preserve the original object unchanged; update versioned derived decisions separately. If normalization fails, retain a safe failed-ingest record/diagnostic where feasible so it can be examined or retried.
2. **Separate ingestion from publication.** Filtering and deduplication produce candidates and explanations; administrator review controls approval and representative selection. Priority/order is a property of the published feed and its editorial decisions, not a mandatory ranking stage that must run before management. Notify after an item becomes reviewable, and publish only approved items.

Suggested operational sequence: **fetch → validate/normalize → durable ingest → evaluate relevance → propose duplicate groups → queue/notify → administrator decision → render approved feed**. Re-evaluation starts from durable ingest and updates derived results without overwriting the original or an explicit administrator decision. Same-platform native-ID uniqueness prevents re-ingestion duplicates; cross-platform semantic duplicates require a distinct policy and review.

## Data boundaries (conceptual)

Implemented Option A increment: `src/editorial.py` records an explicit choice in separate `group_approvals` (group ID, selected provider/native ID, actor, UTC timestamp). One row per group, idempotent same-choice retries, candidate/member validation, and conflict blocking are verified. Source rows, relevance results and duplicate memberships are untouched. Legacy source-table publication fields remain for POC compatibility and are not the new selection store. The service requires a caller-supplied trusted actor; it is not authentication or a public endpoint. The future feed read model must validate recorded selections against current processing state; this increment exposes no publishable feed. Replacement/revocation and changed-content handling remain workflow decisions.

- **Source account/config:** provider, stable account ID, enabled state, refresh policy, auth reference, last fetch status/cursor. Credentials live in secret storage/environment, never in post rows or logs.
- **Ingested post:** provider/native ID, account, source time, fetch time, common text/URL/links/media, original provider payload, normalization version.
- **Derived assessment:** relevance result and rationale, potential duplicate group, suggested representative, rule version, evaluation time.
- **Editorial state:** pending/approved/rejected/withdrawn, selected representative, display order, decision actor/time. Explicit decisions survive repeat imports.
- **Delivery state:** notification id/status and public-feed publication state.

SQLite is reasonable for a single-instance initial deployment and aligns with the September 22 discussion. Keep a small repository interface so storage can change later if multi-site concurrency requires it. Historical data is retained initially, consistent with meeting feedback; retention policy remains a later decision.

## Interfaces and verification

Current Option A milestone: 44 tests pass. `python run_demo.py` option 7 (also included in option 6) uses a temporary database to show a fixture operator selecting X A, retaining Bluesky B as unselected, and blocking a second conflicting selection. Either provider can be selected in service tests. Reopen, rollback, source/processing preservation and replay preservation are verified. No new external reference was used.

Primary developer entry points: `python run_tests.py` recursively runs unittest test modules under `tests/`, reports normal results, and returns nonzero on failure/import errors. `python run_demo.py` provides FR-1–5 menu paths plus all safe offline demos. Synthetic records and temporary SQLite databases show schema conversion, restart/idempotency, preserved editorial state, candidate/approval separation, exact duplicate groups, and offline replay. Only the explicitly confirmed live FR-1 option accesses APIs. Thirty-three tests pass; live menu controls are mocked in automated verification. See [manual_sanity.md](manual_sanity.md).

## FR-9 renderer boundary — Thomas stakeholder feedback

The target is Thomas's static MSRG site: [repository](https://github.com/MSRG/msrg.github.io), [preview](https://msrg.github.io/). Tim relayed Thomas's request for iframe presentation customization on 2026-10-05. A configurable iframe is the currently expected integration; approved feed data will eventually be exposed to it. Planned settings include colors, font sizes, and whether website/source origin is displayed. Renderer settings are independent presentation configuration, never edits to raw/normalized source records, relevance results, duplicate groups, or approval state. Hiding an origin label changes the view only; provenance remains stored. The final embedding/data-delivery/hosting contract is open until integration work. No renderer, settings UI, or website changes are implemented in this milestone.

## Interface contracts

- Each provider adapter returns source identity, raw records, and fetch diagnostics. Normalization maps records into the common model. Provider failures should be visible and should not erase stored content.
- Ingest is idempotent on `(provider, native_id)`; an explicit edit to editorial state is never silently reset by re-fetch.
- Review actions require an authorized administrator. Public output queries approved, non-withdrawn representatives only.
- Test fixtures cover each provider mapping; temporary SQLite tests cover re-import and decision preservation; workflow tests cover notification exactly once, rejection/withdrawal, duplicate representative selection, and public-feed exclusion. End-to-end timing measures O-1 separately from platform availability and human response.

## Open decisions / dependencies

LinkedIn access and account ownership; final iframe integration contract with Thomas; notification channel; actual relevance rules; fuzzy duplicate policy; replacement/withdrawal workflow after the approved Option A initial selection; changed-source handling; manual-announcement and multi-site MVP scope; administrator authentication; feed ordering; measurement boundary for the one-hour target. Keep these explicit in the proposal rather than treating draft choices as confirmed requirements.

## Traceability convention

Use concise tags at meaningful boundaries, for example `# FR-2: Common post representation`. If design inspiration is relevant, add a separate `# REF-HORIZON-01: provider contract` and explain adaptation in `design_references.md`. Tests use names/docstrings such as `test_normalize_x` — `Verifies FR-2`. Do not annotate every line or use a REF tag as evidence of stakeholder need.

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
