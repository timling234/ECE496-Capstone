# ASAP functional requirements — living design

## Quick status

This table tracks progress. The detailed requirements and traceability below remain the authoritative rationale. Update this living document when implementation evidence or stakeholder decisions change; preserve FR IDs.

| FR | Function | Status | Short note |
| --- | --- | --- | --- |
| FR-1 | Source ingestion | ⏸ External Blocker | X/Bluesky configurable scheduled ingestion, pagination, atomic checkpoints and failure isolation verified. LinkedIn API access pending. |
| FR-2 | Common post representation | 🟢 Done | X/Bluesky MVP text/link/image records map to the ten common fields and retain raw data; fixtures/demo verified. LinkedIn validation: ⏸ External Blocker. |
| FR-3 | Persistent provenance and state | 🟢 Done | Current raw/normalized records and processing/editorial state persist; repeat import and replay preserve decisions; restart/rollback verified. Version archives are beyond this MVP. |
| FR-4 | Relevance filtering stage | 🟢 Done | Configurable predicate stage; empty rules allow all candidates, with source and approval state untouched. Admin actions belong to FR-7. |
| FR-5 | Duplicate candidate detection | 🟢 Done | Exact whitespace-normalized text groups across platforms; originals preserved, no automatic selection. Selection/public rendering belong to FR-6/9. |
| FR-6 | Selection and ordering | 🟢 Done | Browser representative selection/replacement, newest-first feed, pin and manual order verified; no automatic platform priority. |
| FR-7 | Management and approval | 🟢 Done | Single-admin login/session/CSRF, review views, approve/reject/withdraw, source/interval configuration and action history verified locally. |
| FR-8 | Administrator notification | ❓ Decision Needed | Core scope accepted; channel and recipients unresolved. |
| FR-9 | Public feed delivery | 🟢 Done | Local approved-only mock renderer and iframe route; text/links/media, configurable accent/font/origin verified. Actual MSRG installation remains deployment work. |
| FR-10 | Extensibility and deployment | 🟡 In Progress | Provider interface and test/demo harness verified; Docker prepared but engine verification blocked; license decision pending. |
| FR-11 | Manual announcements | 🟢 Done | Included by current instruction: create/edit/review/approve/withdraw; edits retain previous text and require re-review. |
| FR-12 | Multiple sites | ❓ Decision Needed | Confirm scope and implementation timing. |

Status legend: 🟢 Done = agreed MVP acceptance criteria implemented and reasonably verified; 🟡 In Progress = required implementation remains; ⚪ Planned = current scope/design, implementation not started; 🔴 Rejected = explicitly removed; ❓ Decision Needed = blocking scope/design confirmation; ⏸ External Blocker = unavailable external dependency, tracked at the affected subrequirement; 🔵 Deferred = enhancement outside current MVP. Optional sophistication does not prevent closure. The authoritative closure boundaries and complete remaining work are recorded in [mvp_closure_audit.md](mvp_closure_audit.md).

## Detailed requirements

Status: proposed, 2026-10-05. These are design targets, not claims of completed features. Source keys: S1 = `docs/references/Detailed_requirements_doc_MSRG _ ASFA – A Simple Feed Aggregator.pdf`; S2 = `docs/meeting_minutes/2026-09-22_proposal_ppt_feedback.md`; S3 = `docs/meeting_minutes/2026-09-24-proposal-meeting-and-feedback.md`; S4 = `docs/meeting_minutes/2026-09-24_proposal_admin_meeting.md`. Resolve scope questions below before treating this as the final proposal baseline.

| ID / name | Description and stakeholder rationale | Acceptance criteria (proposed) | Scope | Components |
| --- | --- | --- | --- | --- |
| FR-1 Source ingestion | Retrieve posts from configured organization accounts on X, Bluesky, and LinkedIn. MSRG needs one feed across its platforms (S1, S3). | For each enabled, authorized source, ingest new text, link, and image posts; record source identity and fetch outcome; an unavailable provider does not corrupt previously stored posts. LinkedIn acceptance depends on platform approval. | MVP; LinkedIn is a gated dependency | Scheduler, provider adapters |
| FR-2 Common post representation | Convert accessible providers' MVP text/link/image posts into common fields for downstream processing (S2, S3). | X/Bluesky fixtures produce platform/account/native ID/source time/text/URL/links/media/metadata/raw; missing optional fields are tolerated; originals remain available. Current-provider validation passes. LinkedIn mapping/validation resumes once access is granted. | MVP complete for accessible providers; LinkedIn subtask externally blocked | Normalizers, post model |
| FR-3 Persistent provenance and state | Persist current provider payloads, common fields and derived/editorial state independently of processing (S2). | Restart retains records; same provider/native ID creates one source row; current raw object is retrievable and untouched by processing; repeat import/replay preserve recorded decisions; stored processing can be rerun; failed transactions roll back. | MVP complete; historical source-version archives deferred | SQLite repository, processing state |
| FR-4 Relevance filtering stage | Always evaluate relevance before review candidacy (Tim's architecture B). Broader curation/removal remains required in FR-7 and public-feed exclusion in FR-9. | No rules allows all; configured predicates evaluate before candidacy; source records are untouched; candidacy never creates/reset approval. Concrete keyword/tag rules are not required for this MVP. | MVP complete | Rule evaluation, candidate state |
| FR-5 Duplicate candidate detection | Flag exact whitespace-normalized text matches within/across sources for review, preserving originals (Tim's conservative initial MVP). | Nonempty exact matches share stable candidate groups; case/punctuation remain significant; repeated processing is idempotent and clears stale derived membership; source/relevance/editorial state is preserved; no automatic representative choice. FR-6 enforces selection; FR-9 must display only the selected approved copy. | MVP complete for exact matching; fuzzy strategies deferred | Candidate grouping; dependent selection/rendering remain required elsewhere |
| FR-6 Selection and ordering | Provide a defensible choice among equivalent posts and stable feed order; alternative platforms may be available sooner than LinkedIn (S2, S4). | Administrator can select the representative of a duplicate group and order approved items; feed ordering is deterministic. Any automatic platform priority is configurable and requires stakeholder approval. | MVP manual selection/order; automatic ranking is optional | Review controls, feed query |
| FR-7 Management and approval | Let an authorized administrator configure sources and refresh intervals, inspect candidates, and approve, reject, or withdraw publication (S1–S3). | An administrator can perform those actions through a maintainable backend; unauthenticated users cannot change publication state; changes are recorded. Credentials are not displayed or stored in post content. | MVP | Admin backend, configuration, access control |
| FR-8 Administrator notification | Alert an administrator when new relevant items need review, as agreed in proposal feedback (S3). | A new reviewable item triggers one notification through the selected channel; repeat polls do not send duplicate alerts; failed delivery is visible/retryable. Channel and recipients are TBD. | MVP | Notification service, event/outbox |
| FR-9 Public feed delivery | Expose/render approved posts to Thomas's new static MSRG website. Iframe rendering is the currently stakeholder-requested/expected approach; presentation must support configurable colors, font sizes, and display of website/source origin (S1, S3, S5). | Future renderer displays only approved content with usable text/links/media. Colors, font sizes and origin visibility change presentation without modifying provenance, relevance, duplicate membership or editorial state. Final integration contract is agreed with Thomas at the integration milestone. The local mock renderer and embedding page are implemented; production installation is separate deployment work. | MVP, planned | Feed read model, iframe renderer, independent presentation configuration |
| FR-10 Extensibility and deployment | Keep provider integrations modular and make the service maintainable in Docker (S1). | A new provider can map into the common model without changing existing provider code; documented configuration and a test harness run in a container. | MVP architecture/deployment | Adapter interface, config, deployment |
| FR-11 Manual announcements | Allow administrators to add non-social announcements, requested in the original specification (S1). | An authorized user can create, edit, approve, and withdraw a manual item in the same public feed. | MVP confirmed in current vertical-slice instruction | Admin backend, post model |
| FR-12 Multiple sites | Support independently curated feeds for MSRG and another site such as QSCC (S1). | Different site configurations yield separate approved outputs without cross-site leakage. | Extension pending proposal scope | Site configuration, publication state |

## Project objective and measurement

**O-1: reduce the approximately 48-hour current delay to approximately one hour.** This is an outcome measure, not a standalone software function. Proposed measurable boundary: time from a post becoming available through an authorized provider API to its appearance in the administrator review queue with a notification, under normal provider operation. Measure p95 over a representative test set; target ≤60 minutes. Report provider publication-to-API availability separately. Time waiting for a human approval and final publication is recorded separately because it is outside the automated pipeline. Stakeholders must confirm this boundary and measurement method (S3, S4).

## Scope decisions for review

1. LinkedIn was part of the original success definition, yet API approval remains pending. Retain FR-1 as a target and define a transparent fallback demonstration if access is denied; do not claim LinkedIn complete.
2. Iframe is now the expected website approach following S5; the exact integration contract remains open. Manual-announcement and multi-site MVP commitments still need confirmation.
3. Define the notification channel, candidate relevance rules, duplicate adjudication policy, administrator identity, and acceptable publication ordering before implementation.
4. Security, responsiveness, latency, licensing, and maintainability also need non-functional requirements; this document only lists functions and one project outcome.

## Requirements traceability matrix

| Stakeholder need / evidence | FR | Architecture component | Current implementation | Verification / test |
| --- | --- | --- | --- | --- |
| Multi-platform retrieval (S1, S3) | FR-1 | Adapters, scheduler | `src/providers.py`, `src/polling.py`, `run_polling.py`, disabled example configuration | `tests/test_polling.py`: incremental pagination, checkpoint rollback, restart, rate-limit waits and source failure isolation; offline demo option 8; LinkedIn API access pending |
| Shared fields (S2, S3) | FR-2 | Normalizer/model | `src/store_poc.py:normalize_x/normalize_bluesky` proof of concept | `tests/test_store_poc.py:NormalizationTests`: X/Bluesky synthetic mappings and missing optional fields verified; LinkedIn TBD |
| Original/normalized/state storage (S2) | FR-3 | SQLite repository | `src/store_poc.py:store/load_posts`, read-only `--inspect`, default offline `--reprocess` | `tests/test_store_poc.py:StoreTests`: restart persistence, JSON roundtrip, idempotency, provider identity, editorial-field preservation, rollback, offline readback, read-only inspection and default replay verified; source/decision history TBD |
| Relevance and removal (S1, S3) | FR-4 | Rules, review state | `src/relevance.py:mark_candidates`; default stage in `store_poc.py` | `tests/test_relevance.py` and mocked ingestion: pass-through, source preservation, candidate/approval separation verified; admin removal TBD |
| One visible copy (S1–S3) | FR-5 | Duplicate candidates, review | `src/duplicates.py`: independent exact-match grouping after relevance | `tests/test_duplicates.py`: cross-platform groups, conservative normalization, original preservation, reversible state and strategy boundary verified; representative/output TBD |
| Representative choice/order (S2, S4, S6) | FR-6 | Internal selection service; future review UI/feed query | `src/editorial.py:approve_representative/get_group_approval`; separate `group_approvals` | `tests/test_editorial.py`: one representative, either provider, idempotency, invalid member blocking; replacement/order TBD |
| Administrator control (S1–S3, S6) | FR-7 | Editorial persistence; future authenticated management backend | Trusted internal service records actor/time and validates candidate membership; demo option 7 uses fixtures only | `tests/test_editorial.py`: persistence, rollback, source/derived preservation and replay; production auth/UI/reject/withdraw TBD |
| New-content alert (S3) | FR-8 | Notification/outbox | TBD | TBD |
| Website display and customizable iframe (S1, S3, S5) | FR-9 | Feed output, renderer, independent presentation config | TBD; requirements/design updated only | TBD |
| Modular, deployable system (S1) | FR-10 | Adapter contract, Docker, test harness | Provider interface; root verification entrypoints; Dockerfile and .dockerignore | Provider and harness tests pass; Docker build/run unverified because engine access is denied; license pending |
| Non-social announcement (S1) | FR-11 | Manual item flow | TBD | TBD |
| Independent site feeds (S1) | FR-12 | Site publication state | TBD | TBD |

Traceability convention: put `FR-n: name` once at a meaningful module/class/function boundary; test names or docstrings say `Verifies FR-n`. Reference IDs are kept separately in `design_references.md`. Do not claim an FR is verified solely because a proof of concept runs.

## Verified increments — 2026-10-05

The entries below are historical milestone reports; their earlier yellow statuses are superseded by the current Quick status and closure audit. No requirement for administrator controls or public-feed correctness was dropped: these are owned by FR-6/7/9 rather than duplicated in the filtering/detection component closure criteria.

1. Offline normalization/Store regression baseline: 7 tests passed using synthetic posts and temporary databases.
2. Stored common-data readback and read-only inspection: full suite now 10 tests passed. Inspection of the existing database reported X=3 and Bluesky=3 without an API call. FR-2/3 remain In Progress; no full FR became Done.

Current Store retains the latest raw object and normalized representation for each provider/native ID; repeat imports replace source fields. It preserves reserved editorial columns but does not retain prior source versions or decision history. These limitations are not covered by a claim of full provenance implementation.

## FR-4 MVP decision — architecture B

Tim approved an always-present relevance stage with an empty default rule configuration. No rules means allow all ingested posts as review candidates. Configured rules evaluate content before candidacy; no real keyword/tag/source rules are defined yet. Passing relevance never approves publication. Conceptual states remain `ingested → candidate → approved`; the final transition requires a separately designed administrator workflow.

`src/relevance.py` stores derived `candidate`/`filtered` state separately, leaving source rows and publication state untouched. The extension interface accepts boolean predicates and requires all supplied predicates to pass. User-facing rule configuration and combination semantics remain to be confirmed when actual rules are introduced. No Horizon code or filtering policy was copied.

FR-4 milestone verification: 16 offline tests pass, including five relevance tests and a mocked fetch → store → candidate integration test. Full FR-4 remains In Progress because administrator inclusion/exclusion/withdrawal is not implemented.

## FR-5 initial engineering default and offline replay

Exact matching trims and collapses whitespace while preserving case, punctuation and Unicode spelling. Empty text never creates a group. This reversible first strategy is not permanent product policy. Cross-platform matches are stored in `duplicate_candidates` with stable `exact-v1` text-hash IDs; no raw/source rows are merged or deleted, no representative is chosen, and approval state is untouched. The legacy `posts.duplicate_group` column is not used by detection. All current relevance candidates form the stage input; re-evaluation replaces only derived candidate memberships. Fuzzy thresholds and representative/publication behavior remain Decision Needed.

FR-5 verification: 22 tests passed after detection. The subsequent offline replay increment brought the suite to 24 passing tests. `store_poc.py --reprocess` reruns default pass-through and exact grouping from an existing Store without APIs, preserving source rows and editorial fields. Missing databases fail without being created. Source-version/decision history remains unimplemented. FR-3/4/5 stay In Progress.

Manual sanity guide: [manual_sanity.md](manual_sanity.md). The deterministic demo uses a temporary database and never touches `.tmp/store_poc.sqlite3`.

## Verification usability and FR-9 stakeholder update

Primary developer commands are `python run_tests.py` and `python run_demo.py`. The menu has individual FR-1–5 paths; option 6 runs simulated FR-1, FR-2–5 and offline replay safely. Live FR-1 is separately labelled and requires provider selection and confirmation; it stores results only in a temporary database, makes no cursor changes, and prints no credentials or live post contents. The suite has 33 passing tests including the preserved 24-test baseline. All safe offline demo paths pass; live controls are tested with mocked providers, not represented as a new live API verification.

S5 = Thomas's presentation-customization feedback relayed by Tim in this conversation on 2026-10-05. Target repository: [MSRG/msrg.github.io](https://github.com/MSRG/msrg.github.io); preview: [msrg.github.io](https://msrg.github.io/). Iframe rendering is expected, with configurable colors, font sizes and origin display. These are display settings independent of original data and processing/editorial state. Final integration details remain open and no rendering code was added.

Executed menu option 6 through the root entry point: simulated FR-1 and FR-2–5 plus offline replay all reported PASS. SHA-256 checks before/after confirmed the real Store and existing cursor files unchanged. FR-6/7 implementation awaits the administrator decision: one representative per duplicate group versus independent post approvals with advisory grouping.

## FR-6/FR-7 Option A decision and first increment

S6 = Tim chose Option A: an administrator explicitly selects exactly one representative from a duplicate group for approval. Grouping and filtering alone never approve anything. Non-selected members are retained and are not automatically rejected. No platform priority is imposed. Ungrouped-item approvals, replacement/revocation, ordering, administrator UI/authentication and actual publishing remain unimplemented.

`src/editorial.py` is an internal selection service, not an authenticated endpoint. `approve_representative` requires an existing source and current review-candidate membership in the requested duplicate group. It records one selected identity with actor/time in separate `group_approvals`; a group-ID primary key prevents two representative rows. Repeating the same choice preserves the first record. A conflicting second choice is blocked, rather than silently replacing approval, until that workflow is confirmed.

New decisions do not update legacy `posts.publication_status`, `duplicate_group` or priority fields; source provenance, relevance and duplicate memberships remain unchanged. `group_approvals` holds the new Option A editorial decision. Reading this recorded decision is not a public-feed eligibility check; the future publication read model must account for current relevance/membership. Replay retains recorded decisions and does not publish or reinterpret obsolete groups automatically.

Verification: `python run_tests.py` reports 44 passing tests. Option 7 in `python run_demo.py` demonstrates an explicit fixture choice, reopened SQLite decision readback, blocked second choice and source preservation. Option 6 includes it alongside all prior offline paths. FR-6/7 remain In Progress; no production administrator workflow is claimed.

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
