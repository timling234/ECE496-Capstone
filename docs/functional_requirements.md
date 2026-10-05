# ASAP functional requirements — living design

## Quick status

This table tracks progress. The detailed requirements and traceability below remain the authoritative rationale. Update this living document when implementation evidence or stakeholder decisions change; preserve FR IDs.

| FR | Function | Status | Short note |
| --- | --- | --- | --- |
| FR-1 | Source ingestion | 🟡 In Progress | X/Bluesky POC works; LinkedIn, scheduling and full verification remain. |
| FR-2 | Common post representation | 🟡 In Progress | X/Bluesky mapping fixtures pass; final model and all-provider coverage remain. |
| FR-3 | Persistent provenance and state | 🟡 In Progress | Persistence/upsert/readback tests pass; replay and source/decision history remain. |
| FR-4 | Relevance curation | 🟡 In Progress | Empty rules allow all; candidate state tested separately from approval. Admin controls remain. |
| FR-5 | Duplicate control | ❓ Decision Needed | Core scope accepted; similarity/grouping policy is unresolved. |
| FR-6 | Selection and ordering | ❓ Decision Needed | Representative selection and order policy need confirmation. |
| FR-7 | Management and approval | ❓ Decision Needed | Core scope accepted; administrator workflow/authentication unresolved. |
| FR-8 | Administrator notification | ❓ Decision Needed | Core scope accepted; channel and recipients unresolved. |
| FR-9 | Public feed delivery | ❓ Decision Needed | Core scope accepted; website integration method unresolved. |
| FR-10 | Extensibility and deployment | ⚪ Planned | Modular contract and Docker deployment not implemented. |
| FR-11 | Manual announcements | ❓ Decision Needed | Confirm MVP commitment against original specification. |
| FR-12 | Multiple sites | ❓ Decision Needed | Confirm scope and implementation timing. |

Status legend: 🟢 Done = implemented and reasonably verified; 🟡 In Progress = partial implementation/POC; ⚪ Planned = current scope/design, implementation not started; 🔴 Rejected = explicitly removed from scope; ❓ Decision Needed = scope/design needs confirmation. No full FR is currently Done or Rejected. Decision Needed can apply to an accepted feature whose policy is unresolved.

## Detailed requirements

Status: proposed, 2026-10-05. These are design targets, not claims of completed features. Source keys: S1 = `docs/references/Detailed_requirements_doc_MSRG _ ASFA – A Simple Feed Aggregator.pdf`; S2 = `docs/meeting_minutes/2026-09-22_proposal_ppt_feedback.md`; S3 = `docs/meeting_minutes/2026-09-24-proposal-meeting-and-feedback.md`; S4 = `docs/meeting_minutes/2026-09-24_proposal_admin_meeting.md`. Resolve scope questions below before treating this as the final proposal baseline.

| ID / name | Description and stakeholder rationale | Acceptance criteria (proposed) | Scope | Components |
| --- | --- | --- | --- | --- |
| FR-1 Source ingestion | Retrieve posts from configured organization accounts on X, Bluesky, and LinkedIn. MSRG needs one feed across its platforms (S1, S3). | For each enabled, authorized source, ingest new text, link, and image posts; record source identity and fetch outcome; an unavailable provider does not corrupt previously stored posts. LinkedIn acceptance depends on platform approval. | MVP; LinkedIn is a gated dependency | Scheduler, provider adapters |
| FR-2 Common post representation | Convert provider-specific posts into a stable internal representation so downstream rules and rendering work across sources (S2, S3). | Fixtures from X and Bluesky produce platform, account, native ID, source time, text, canonical URL, links, media, and provider metadata; missing optional fields do not break ingestion. Add LinkedIn fixture when access is granted. | MVP | Normalizers, post model |
| FR-3 Persistent provenance and state | Retain original provider data and normalized fields, plus processing/publication state, so staff can audit and rerun changed rules without calling an API again (S2). | Restart preserves records; repeated fetch of one platform/native ID makes one record; original payload remains retrievable; publication decisions survive re-fetch; processing results can be regenerated from stored records. | MVP | SQLite repository, processing state |
| FR-4 Relevance curation | Identify relevant candidate content and allow an administrator to include, exclude, or remove it from the public feed. MSRG needs selective publication and later removal (S1, S3). | A rule or administrator decision can mark a post for review, reject it, and withdraw a published item; excluded/withdrawn posts do not appear publicly; the original record remains available for audit. | MVP | Rule evaluation, review queue, publication state |
| FR-5 Duplicate control | Detect repeated content within and across platforms so one announcement is not shown twice (S1–S3). | Exact native reposts are idempotent; test fixtures representing the same announcement on two platforms are grouped or flagged for review; only the administrator-selected representative is displayed; both source records remain stored. | MVP | Candidate grouping, review queue |
| FR-6 Selection and ordering | Provide a defensible choice among equivalent posts and stable feed order; alternative platforms may be available sooner than LinkedIn (S2, S4). | Administrator can select the representative of a duplicate group and order approved items; feed ordering is deterministic. Any automatic platform priority is configurable and requires stakeholder approval. | MVP manual selection/order; automatic ranking is optional | Review controls, feed query |
| FR-7 Management and approval | Let an authorized administrator configure sources and refresh intervals, inspect candidates, and approve, reject, or withdraw publication (S1–S3). | An administrator can perform those actions through a maintainable backend; unauthenticated users cannot change publication state; changes are recorded. Credentials are not displayed or stored in post content. | MVP | Admin backend, configuration, access control |
| FR-8 Administrator notification | Alert an administrator when new relevant items need review, as agreed in proposal feedback (S3). | A new reviewable item triggers one notification through the selected channel; repeat polls do not send duplicate alerts; failed delivery is visible/retryable. Channel and recipients are TBD. | MVP | Notification service, event/outbox |
| FR-9 Public feed delivery | Expose only approved content for the MSRG website, with usable text, links, and images (S1, S3). | Approved posts appear in a responsive feed; rejected/withdrawn posts do not; links lead to original posts. Final integration method (iframe versus static-site interface) must be agreed with the website maintainer. | MVP | Feed read model, renderer/integration |
| FR-10 Extensibility and deployment | Keep provider integrations modular and make the service maintainable in Docker (S1). | A new provider can map into the common model without changing existing provider code; documented configuration and a test harness run in a container. | MVP architecture/deployment | Adapter interface, config, deployment |
| FR-11 Manual announcements | Allow administrators to add non-social announcements, requested in the original specification (S1). | An authorized user can create, edit, approve, and withdraw a manual item in the same public feed. | Scope decision: original spec requests it; later proposal feedback does not explicitly recommit it | Admin backend, post model |
| FR-12 Multiple sites | Support independently curated feeds for MSRG and another site such as QSCC (S1). | Different site configurations yield separate approved outputs without cross-site leakage. | Extension pending proposal scope | Site configuration, publication state |

## Project objective and measurement

**O-1: reduce the approximately 48-hour current delay to approximately one hour.** This is an outcome measure, not a standalone software function. Proposed measurable boundary: time from a post becoming available through an authorized provider API to its appearance in the administrator review queue with a notification, under normal provider operation. Measure p95 over a representative test set; target ≤60 minutes. Report provider publication-to-API availability separately. Time waiting for a human approval and final publication is recorded separately because it is outside the automated pipeline. Stakeholders must confirm this boundary and measurement method (S3, S4).

## Scope decisions for review

1. LinkedIn was part of the original success definition, yet API approval remains pending. Retain FR-1 as a target and define a transparent fallback demonstration if access is denied; do not claim LinkedIn complete.
2. The original specification names iframe output, manual announcements, and multi-site support. The September 24 feedback says website integration is undecided and broader deployment is an extension. Confirm the final commitments with Michalis/Thomas.
3. Define the notification channel, candidate relevance rules, duplicate adjudication policy, administrator identity, and acceptable publication ordering before implementation.
4. Security, responsiveness, latency, licensing, and maintainability also need non-functional requirements; this document only lists functions and one project outcome.

## Requirements traceability matrix

| Stakeholder need / evidence | FR | Architecture component | Current implementation | Verification / test |
| --- | --- | --- | --- | --- |
| Multi-platform retrieval (S1, S3) | FR-1 | Adapters, scheduler | `tests/x_api/x_api_test.py`, `tests/bluesky_api/bluesky_api.py`, `src/store_poc.py` are proof of concept only; LinkedIn TBD | Live X/Bluesky Store run observed 3+3; automated test TBD; LinkedIn TBD |
| Shared fields (S2, S3) | FR-2 | Normalizer/model | `src/store_poc.py:normalize_x/normalize_bluesky` proof of concept | `tests/test_store_poc.py:NormalizationTests`: X/Bluesky synthetic mappings and missing optional fields verified; LinkedIn TBD |
| Original/normalized/state storage (S2) | FR-3 | SQLite repository | `src/store_poc.py:store/load_posts`, read-only `--inspect` | `tests/test_store_poc.py:StoreTests`: restart persistence, JSON roundtrip, idempotency, provider identity, editorial-field preservation, rollback, offline readback, read-only inspection verified; replay/history TBD |
| Relevance and removal (S1, S3) | FR-4 | Rules, review state | `src/relevance.py:mark_candidates`; default stage in `store_poc.py` | `tests/test_relevance.py` and mocked ingestion: pass-through, source preservation, candidate/approval separation verified; admin removal TBD |
| One visible copy (S1–S3) | FR-5 | Duplicate candidates, review | TBD; current unique key handles only the same platform/native ID | TBD |
| Representative choice/order (S2, S4) | FR-6 | Review controls, feed query | Priority field placeholder only | TBD |
| Administrator control (S1–S3) | FR-7 | Admin backend/config | TBD | TBD |
| New-content alert (S3) | FR-8 | Notification/outbox | TBD | TBD |
| Website display (S1, S3) | FR-9 | Feed output | TBD | TBD |
| Modular, deployable system (S1) | FR-10 | Adapter contract, Docker | Single-file proof of concept only | TBD |
| Non-social announcement (S1) | FR-11 | Manual item flow | TBD | TBD |
| Independent site feeds (S1) | FR-12 | Site publication state | TBD | TBD |

Traceability convention: put `FR-n: name` once at a meaningful module/class/function boundary; test names or docstrings say `Verifies FR-n`. Reference IDs are kept separately in `design_references.md`. Do not claim an FR is verified solely because a proof of concept runs.

## Verified increments — 2026-10-05

1. Offline normalization/Store regression baseline: 7 tests passed using synthetic posts and temporary databases.
2. Stored common-data readback and read-only inspection: full suite now 10 tests passed. Inspection of the existing database reported X=3 and Bluesky=3 without an API call. FR-2/3 remain In Progress; no full FR became Done.

Current Store retains the latest raw object and normalized representation for each provider/native ID; repeat imports replace source fields. It preserves reserved editorial columns but does not retain prior source versions or decision history. These limitations are not covered by a claim of full provenance implementation.

## FR-4 MVP decision — architecture B

Tim approved an always-present relevance stage with an empty default rule configuration. No rules means allow all ingested posts as review candidates. Configured rules evaluate content before candidacy; no real keyword/tag/source rules are defined yet. Passing relevance never approves publication. Conceptual states remain `ingested → candidate → approved`; the final transition requires a separately designed administrator workflow.

`src/relevance.py` stores derived `candidate`/`filtered` state separately, leaving source rows and publication state untouched. The extension interface accepts boolean predicates and requires all supplied predicates to pass. User-facing rule configuration and combination semantics remain to be confirmed when actual rules are introduced. No Horizon code or filtering policy was copied.

FR-4 milestone verification: 16 offline tests pass, including five relevance tests and a mocked fetch → store → candidate integration test. Full FR-4 remains In Progress because administrator inclusion/exclusion/withdrawal is not implemented.
