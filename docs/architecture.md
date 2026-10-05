# ASAP high-level architecture — living design

This is a living design, revised as implementation and stakeholder feedback provide evidence. Requirements: [functional_requirements.md](functional_requirements.md). External inspiration: [design_references.md](design_references.md). Component progress does not imply completion of a whole FR.

## Component status

| Component | Status | Evidence / remaining work |
| --- | --- | --- |
| X / Bluesky fetch functions | 🟡 In Progress | Working POCs; final adapter contract and scheduler remain. |
| Common normalization | 🟡 In Progress | X/Bluesky synthetic fixture tests pass; final validation/model remains. |
| SQLite ingest store | 🟡 In Progress | Upsert, reopen, rollback, state preservation and offline readback verified; replay/versioning/history remain. |
| Scheduler / provider contract / Docker | ⚪ Planned | No implementation yet. |
| LinkedIn adapter | ❓ Decision Needed | API access pending; fallback behavior requires confirmation. |
| Relevance stage | 🟡 In Progress | Default pass-through and separate candidate state verified; real rules/admin controls remain. |
| Duplicate candidates | ❓ Decision Needed | Similarity/grouping policy requires confirmation. |
| Admin review / selection / order | ❓ Decision Needed | Workflow and identity require confirmation. |
| Notifications / public feed integration | ❓ Decision Needed | Channel and website interface require confirmation. |
| Manual items / site separation | ❓ Decision Needed | Scope requires confirmation. |

Uses the FR status legend. No complete architecture component is labelled Done, and no idea has yet been explicitly removed from project scope. Horizon AI ranking and briefing generation are reference exclusions/recommendations, not implicitly rejected stakeholder requirements. The diagram below shows intended flow, not implemented coverage.

## Current baseline

`tests/x_api/x_api_test.py` polls X and maintains its own latest-ID cursor; `tests/bluesky_api/bluesky_api.py` reads a public author feed; `src/store_poc.py` fetches both, normalizes into shared fields, and upserts an ignored SQLite file with original response objects, metadata, and pending publication status. This is a working proof of concept, not a scheduler, production adapter system, filtering engine, admin backend, or public feed. LinkedIn access remains gated by platform approval.

`load_posts(conn)` now restores common fields, raw objects, metadata, and stored state offline. `--inspect` opens the existing database in SQLite read-only mode, reports counts, and makes no API calls. Ten offline tests pass; live database inspection reports three records per provider. Repeat imports still replace the latest source snapshot, so immutable source-version history in the proposed architecture is not implemented. Reserved editorial fields are preserved but no administrator workflow exists.

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
         Duplicate candidates + representative suggestions
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

Current FR-4 MVP decision (architecture B): the relevance stage always runs after storage. Empty rules allow every ingested post to become a candidate. `src/relevance.py:mark_candidates` persists derived candidate/filtered status independently of `posts.publication_status`; no approval occurs here. Configured predicate extensions can evaluate posts, but no keyword/tag/provider rule is implemented. Source payloads are preserved. Sixteen offline tests verify the current pipeline and state separation. Administrator transitions and actual rule configuration remain future decisions.

The proposed `Fetch → Normalize → Store → Filter → Deduplicate → Prioritize → Manage → Publish` is a useful sketch but hides two important distinctions:

1. **Persist provenance before curation.** Save original provider payload and a normalized representation before relevance and duplicate decisions. Changed rules can then be rerun without paying for or waiting on another API call. Preserve the original object unchanged; update versioned derived decisions separately. If normalization fails, retain a safe failed-ingest record/diagnostic where feasible so it can be examined or retried.
2. **Separate ingestion from publication.** Filtering and deduplication produce candidates and explanations; administrator review controls approval and representative selection. Priority/order is a property of the published feed and its editorial decisions, not a mandatory ranking stage that must run before management. Notify after an item becomes reviewable, and publish only approved items.

Suggested operational sequence: **fetch → validate/normalize → durable ingest → evaluate relevance → propose duplicate groups → queue/notify → administrator decision → render approved feed**. Re-evaluation starts from durable ingest and updates derived results without overwriting the original or an explicit administrator decision. Same-platform native-ID uniqueness prevents re-ingestion duplicates; cross-platform semantic duplicates require a distinct policy and review.

## Data boundaries (conceptual)

- **Source account/config:** provider, stable account ID, enabled state, refresh policy, auth reference, last fetch status/cursor. Credentials live in secret storage/environment, never in post rows or logs.
- **Ingested post:** provider/native ID, account, source time, fetch time, common text/URL/links/media, original provider payload, normalization version.
- **Derived assessment:** relevance result and rationale, potential duplicate group, suggested representative, rule version, evaluation time.
- **Editorial state:** pending/approved/rejected/withdrawn, selected representative, display order, decision actor/time. Explicit decisions survive repeat imports.
- **Delivery state:** notification id/status and public-feed publication state.

SQLite is reasonable for a single-instance initial deployment and aligns with the September 22 discussion. Keep a small repository interface so storage can change later if multi-site concurrency requires it. Historical data is retained initially, consistent with meeting feedback; retention policy remains a later decision.

## Interfaces and verification

- Each provider adapter returns source identity, raw records, and fetch diagnostics. Normalization maps records into the common model. Provider failures should be visible and should not erase stored content.
- Ingest is idempotent on `(provider, native_id)`; an explicit edit to editorial state is never silently reset by re-fetch.
- Review actions require an authorized administrator. Public output queries approved, non-withdrawn representatives only.
- Test fixtures cover each provider mapping; temporary SQLite tests cover re-import and decision preservation; workflow tests cover notification exactly once, rejection/withdrawal, duplicate representative selection, and public-feed exclusion. End-to-end timing measures O-1 separately from platform availability and human response.

## Open decisions / dependencies

LinkedIn access and account ownership; final website integration with Thomas (iframe was requested originally but the new static site path is unresolved); notification channel; definition of relevant content; duplicate policy; manual-announcement and multi-site MVP scope; administrator authentication; measurement boundary for the one-hour target. Keep these explicit in the proposal rather than treating draft choices as confirmed requirements.

## Traceability convention

Use concise tags at meaningful boundaries, for example `# FR-2: Common post representation`. If design inspiration is relevant, add a separate `# REF-HORIZON-01: provider contract` and explain adaptation in `design_references.md`. Tests use names/docstrings such as `test_normalize_x` — `Verifies FR-2`. Do not annotate every line or use a REF tag as evidence of stakeholder need.
