# Design references — living design

## Reference status

These states describe design influence, independently of FR implementation progress. Adopted means the concept is selected; Partially adopted/adapted means selected portions are adapted; Under evaluation means a decision is pending; Rejected/not applicable means explicitly excluded for this project. None of these implies copied code.

| Reference | Status | Short note |
| --- | --- | --- |
| REF-HORIZON-01 | Partially adopted/adapted | Provider-independent fetch contract implemented independently; concept adopted, no reference code copied. |
| REF-HORIZON-02 | Partially adopted/adapted | Shared provider-independent POC representation; independent code, no Horizon fields/classes copied. |
| REF-HORIZON-03 | Partially adopted/adapted | Replaceable processing stage aligns with design; pass-through is Tim's decision, independently implemented. |
| REF-HORIZON-04 | Partially adopted/adapted | Separate duplicate stage implemented independently; no digest merge/scoring copied. |
| REF-HORIZON-05 | Partially adopted/adapted | Data/output boundary informs design; SQLite itself is stakeholder-grounded and independent. |
| REF-HORIZON-06 | Under evaluation | Replaceable configuration/delivery idea; channels unresolved. |

Implementation trace: `src/store_poc.py:normalize_x/normalize_bluesky` carries FR-2 and REF-HORIZON-02 concept tags. `store/load_posts` implements portions of FR-3 independently; SQLite and readback are not copied from Horizon. `tests/test_store_poc.py` identifies verified FRs in test docstrings. Reference adoption status does not change merely because tests pass.

Reference exclusions in the detailed table describe recommendations for this architecture, not new stakeholder requirements. Update statuses as concepts are selected or rejected.

This file records external inspiration separately from ASAP requirements. ASAP requirements are grounded in [functional_requirements.md](functional_requirements.md) and stakeholder documents. Horizon was inspected at <https://github.com/Thysrael/Horizon> on 2026-10-05; paths below refer to its `main` branch as viewed then. Its README describes a daily AI news briefing, not a human-approved organizational website feed. Its repository states an MIT license: <https://github.com/Thysrael/Horizon/blob/main/LICENSE>. **No Horizon code was copied into ASAP.** Proposed ideas are adaptations or independent design decisions, not imported implementation.

| REF ID | Horizon actually implements (traceable path) | Potential ASAP adaptation | Do not adopt |
| --- | --- | --- | --- |
| REF-HORIZON-01 | Source-specific scrapers implement `BaseScraper.fetch(since)` and return `ContentItem`: [base.py](https://github.com/Thysrael/Horizon/blob/main/src/scrapers/base.py), [scrapers](https://github.com/Thysrael/Horizon/tree/main/src/scrapers), [orchestrator.py](https://github.com/Thysrael/Horizon/blob/main/src/orchestrator.py). | A small provider contract for X, Bluesky, and LinkedIn, with independent normalization and diagnostics. | Its specific X/Apify/browser retrieval path; ASAP already tests official X API and should follow authorized provider access. |
| REF-HORIZON-02 | Shared `ContentItem` carries source type, stable ID, text/content, URL, timestamps, metadata, and processing data: [models.py](https://github.com/Thysrael/Horizon/blob/main/src/models.py). | Keep a provider-independent post model and stable source identity. | Reuse its news-oriented title/profile/AI fields as mandatory social-post fields. ASAP also needs original payload, account identity, approval, and media. |
| REF-HORIZON-03 | Profile configuration and processing route content into scoring, threshold filtering, optional topic deduplication, and balanced digest selection: [profiles.py](https://github.com/Thysrael/Horizon/blob/main/src/processing/profiles.py), [orchestrator.py](https://github.com/Thysrael/Horizon/blob/main/src/orchestrator.py), [config guide](https://github.com/Thysrael/Horizon/blob/main/docs/configuration.md). | Separate configurable source rules and derived selection results from fetched content. | AI scoring, per-profile prompts, digest quotas, or automated rank thresholds as default ASAP requirements; stakeholders asked for administrator review and controlled publication. |
| REF-HORIZON-04 | The orchestrator has source fetch, duplicate merging, filtering, and digest selection stages: [orchestrator.py](https://github.com/Thysrael/Horizon/blob/main/src/orchestrator.py). It can merge content from duplicate news items. | Keep stages testable and explainable; produce duplicate candidates before publishing. | Destructively merging social posts or letting an AI choice replace administrator selection. Preserve both originals and decisions. |
| REF-HORIZON-05 | `StorageManager` manages file-based configuration/state and generated summaries: [manager.py](https://github.com/Thysrael/Horizon/blob/main/src/storage/manager.py). The README lists Markdown/Pages, email, and webhook outputs. | Separate durable data access from rendering/delivery. | Treat Horizon's file-based summary storage as an ASAP post database or assume it has an approval workflow. ASAP's SQLite/provenance decision comes from S2 and the current proof of concept. |
| REF-HORIZON-06 | Source and processing settings can be configured, and briefings can be delivered through multiple channels: [README](https://github.com/Thysrael/Horizon), [configuration.md](https://github.com/Thysrael/Horizon/blob/main/docs/configuration.md), [orchestrator.py](https://github.com/Thysrael/Horizon/blob/main/src/orchestrator.py). | Keep source/refresh settings and notification output replaceable. | Implement daily briefing generation, bilingual summaries, email subscriptions, MCP, or broad source catalog for the MSRG MVP. |

Horizon has no evident Bluesky or LinkedIn scraper in the inspected source list. Its documented Twitter/X source uses Apify and optional browser tooling; this is materially different from ASAP's current API proof of concept. Its public README and inspected modules show automated briefing generation, rather than a demonstrated administrator approve/reject/withdraw workflow. Absence here means **not found in the inspected files**, not a claim about every historical branch or feature.

If code is ever copied later, record the exact Horizon commit/path, copy extent, MIT attribution, and license compatibility in the change. A conceptual `REF-HORIZON-n` tag alone does not mean code was copied.

FR-5 implementation trace: `src/duplicates.py` uses REF-HORIZON-04 solely for stage separation. Conservative exact-text matching was authorized by Tim as a reversible engineering default; stable hashing, separate SQLite memberships and offline replay are independent implementation details. No Horizon code or digest behavior was copied. Similarity thresholds, automatic representative selection and source priority remain unresolved.

Root verification entry points and readable FR demos are independent implementation; no new Horizon reference is adopted. FR-9 iframe customization is stakeholder feedback relayed by Tim from Thomas, not an external design reference or copied implementation. It is recorded in requirements/architecture while the integration contract remains open.

Option A selection comes from Tim's explicit FR-6/FR-7 decision. `src/editorial.py` and its demo/tests are independent implementation. No Horizon ranking, automatic representative choice, or digest merge behavior is adopted. Existing REF-HORIZON-04 remains limited to duplicate-stage separation; it does not define editorial policy.

## Provider implementation sources

The X adapter uses the official [user-post endpoint documentation](https://docs.x.com/x-api/users/get-posts). The Bluesky adapter follows the official [getAuthorFeed lexicon](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/getAuthorFeed.json). These are protocol references, not requirements or copied implementation code. REF-HORIZON-01 is conceptual inspiration for the independently implemented provider contract; scheduler/transaction behavior is project implementation work.

The [LinkedIn restricted-use documentation](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-09) is recorded as policy context for separate review. It does not change the pending API integration architecture or authorize downstream use.

## Browser vertical slice

FR-6/7/9/11 web/editorial components are independent project implementation using Python's standard library. No new external design reference was used and no external reference code was copied. Existing REF-HORIZON tags remain conceptual references for earlier provider/model/detection stages.
