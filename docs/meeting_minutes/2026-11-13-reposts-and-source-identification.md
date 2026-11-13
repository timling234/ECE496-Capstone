# November 13, 2026 — source identification and native repost verification

Scope: improve R1 ingestion, R2 normalization, R3 deduplication and R6 website integration; no new functional requirement. Keep the original four copied test posts. Replace the pending copy-post batch with a native repost experiment.

Sources should display the actual connected organization's name, resolved from LinkedIn. Numeric account IDs remain internal identifiers. Copy-pasted posts are original posts by ASAP Test Lab, with their actual November 13 publication date; they must not be relabeled as MSRG/Yifang Tian posts.

A native reshare stores A's wrapper ID, source organization and repost date separately from B's original ID, author, content/media and original date. Only API-returned original data is accepted. Successful hydration displays the original author/date inside the repost card. Missing originals require human review and cannot publish as complete news. Different wrappers of the same original remain separate provenance records in one duplicate group, using the existing representative selection.

## Live experiment

Only A (ASAP Test Lab, organization 143906318) authenticated. Four real reshares were created, then fetched in one batch. All four returned A as author and both `reshareContext.parent` and `root`. The wrapper responses contained empty commentary and no original content.

Initial reference positions 1/3 returned 404 for the queried identities. The experiment therefore used the four explicit `ugcPost` links at positions 2, 4, 13 and 16 in the saved MSRG reference list. A second original-content batch after resharing returned 403 for all four. These are current access results, not a claim that all LinkedIn integrations have the same restriction. Authenticating A does not currently grant this app access to those B originals.

Created reshares (retain until instructed otherwise):
- `urn:li:ugcPost:7527080571873714176`
- `urn:li:ugcPost:7527080575254441984`
- `urn:li:ugcPost:7527080578396028928`
- `urn:li:ugcPost:7527080580874752000`

Nine actual LinkedIn HTTP calls: organization name (1), pre-reshare original batch (1), create reshare (4), read A's reshares (1), post-reshare original batch (1), normal A-author finder (1). The normal source finder returned all four new reposts. No original author authenticated, no uploads, deletions or blind retries. Full response evidence stays outside Git in the server-local experiment directory, not in public test fixtures.

Public Feed and Mock Website use the same renderer. Mock defaults to the workspace's published posts; reference snapshots remain an explicitly labeled sample mode and are never evidence of API access.

References: [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-09), [Post schema](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/post-api-schema?view=li-lms-2026-08).

## Native embed verification (same day)

All four existing A reshares above rendered through LinkedIn's public `/embed/feed/update/{urn}` endpoint in fresh anonymous Chrome profiles. Each displayed ASAP Test Lab as the outer account and the expected inner original author (Yifang Tian, Tianyin Xu, Shivesh Prakash, Guoli Li), with original text. No B account authenticated.

An actual iframe on a temporary local HTTP page was also visually verified for the Guoli Li reshare: outer A, inner B, avatar, original relative date, full text and five-photo mosaic loaded successfully. An initial file-URL frame failed; HTTP framing worked. The first HTTP screenshot preceded image loading; a real-time delayed capture confirmed all photos. Evidence remains in ignored `.tmp/native-embed-check/`. Temporary browser/server processes were closed.

This verifies presentation of A wrapping B despite the REST original-content 403 results. It does not grant server-side AI access to B's content, prove every repost type embeds, or establish production integration. Current production CSP allows only self-hosted frames; integrating official LinkedIn frames still needs a narrow frame allowlist and a feed rendering decision. No additional LinkedIn REST API calls, posts or deletions were made during this check; only public embed pages and their assets were loaded.

## Native embeds connected to Public Feed

Public Feed now renders valid LinkedIn reshare wrapper IDs with the official LinkedIn iframe; Mock Website inherits this through the shared feed. Other posts retain the existing renderer. The CSP permits frames only from self and `https://www.linkedin.com`. Frame URLs are constructed from a strict LinkedIn platform/reshare check and numeric share/ugcPost identity, never arbitrary metadata URLs. Frames are lazy-loaded with a 620px scrollable viewport; LinkedIn controls their internal appearance and external-content availability.

Unresolved originals may now enter the human review queue and be manually approved for native embedding. They remain `needs_review` for AI: successful browser embedding does not provide server-readable original content. Existing decisions are preserved; deployment restores previously filtered native reposts to candidate status without approving them or sending migration notifications. No LinkedIn REST calls are required for this integration.
