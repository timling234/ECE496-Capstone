# API Feasibility Review with Michalis

**Date:** September 16, 2026  
**Project:** ASAP - Automated Social-media Aggregation Platform  
**Course:** ECE496 Capstone

## Purpose

Review the team's initial social-media API feasibility investigation and determine the priorities for the following two weeks.

## Work Completed Before the Meeting

The team conducted an initial feasibility study for LinkedIn, X, and Bluesky.

### LinkedIn

- Community Management API investigated.
- Mock application and Page association established.
- Technical approach appears feasible.
- Production testing is currently blocked by organization verification.
- Authorized MSRG/UofT identity and Page access are required for further validation.

### X

- Official X API v2 proof of concept completed.
- Text retrieval tested.
- URL/link metadata retrieval tested.
- Image/media retrieval tested.
- Incremental polling using `since_id` and empty polls tested.
- A five-minute polling interval appears practical for the prototype.
- The API uses pay-per-returned-resource billing; a conservative project estimate was approximately US$8/month.

### Bluesky

- AT Protocol/Public API proof of concept completed.
- Public post text retrieval tested.
- External URI/title retrieval tested.
- Image/CDN metadata retrieval tested.
- Tested public reads require no developer application, API key, or organization verification.
- Incremental polling remains to be experimentally validated.

## Feedback

Michalis indicated that the initial feasibility work was strong and that the first feasibility-check phase was essentially complete.

The team should therefore shift its main effort away from deeper API experimentation for the next two weeks.

## Priorities for the Next Two Weeks

### 1. Proposal and Proposal Meeting

Prepare the formal ECE496 Project Proposal and the Proposal Meeting material.

- Proposal review: Tuesday, September 22, 5-6 PM.
- Proposal submission: Thursday, September 24.

### 2. Preliminary / Market Analysis

Investigate existing solutions and determine how they compare with ASAP requirements.

The analysis should include:

- Elfsight;
- at least three other leading commercial feed aggregators;
- available open-source feed aggregation projects;
- which ASAP requirements existing solutions satisfy;
- which requirements they do not satisfy; and
- the gaps that justify building ASAP.

## Current Technical Direction

The feasibility study supports the following initial architecture:

LinkedIn / X / Bluesky  
-> Provider Adapters  
-> Unified Post Model  
-> ASAP API  
-> MSRG Website

Current scope is focused on MSRG-owned account posts rather than global search or scraping.

## Decisions / Outcomes

- Initial API feasibility phase considered substantially complete.
- X official API POC passed.
- Bluesky public-read POC passed.
- LinkedIn is technically promising but requires institutional authorization.
- Near-term focus shifts to the Proposal and comparative market/open-source analysis.

## Action Items

- Prepare Proposal Meeting material.
- Draft and review the formal Project Proposal.
- Analyze Elfsight and at least three commercial alternatives.
- Search for relevant open-source alternatives.
- Build a requirements-comparison matrix.
- Document where existing solutions meet or fail ASAP requirements.
- Continue LinkedIn institutional-access follow-up as needed.
