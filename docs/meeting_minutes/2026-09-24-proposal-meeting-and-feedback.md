# Meeting Minutes — Proposal Meeting Feedback

**Date:** September 24, 2026  
**Project:** ECE496 Capstone — ASAP / MSRG News Aggregation  
**Meeting Type:** Proposal Meeting / Feedback

## 1. Meeting Summary

The team presented the proposed system and initial platform feasibility results. The key feedback was to define a realistic project scope and explicitly state which features the team commits to delivering in the actual Project Proposal. The discussion also covered administrator notifications, content approval, API access, and integration with the upcoming MSRG website.

## 2. Actual Project Proposal — In-Scope Features

The actual proposal should clearly identify committed functionality rather than describing only the overall concept or technical feasibility. The team identified the following features for inclusion:

| Feature | Intended functionality |
|---|---|
| Manageable backend | Allow administrators to manage retrieved content and publishing operations. |
| Data normalization | Convert posts from supported social platforms into a consistent format. |
| Content filtering | Select relevant posts based on the project's defined requirements. |
| Duplicate detection | Identify duplicate content to avoid repeated publication. |
| Faster updates | Reduce the current approximately 48-hour update delay to a target of 1 hour. |
| Administrator notifications | Notify administrators when new relevant content is available for review. |
| Manual review and approval | Let administrators decide which retrieved posts to publish. |
| Website integration | Make approved content available on the new MSRG website. |

**Important performance objective:** The 48-hour-to-1-hour improvement should be emphasized and defined with a measurable acceptance criterion. The proposal needs to specify whether the target measures detection, availability for administrator review, or final publication; manual approval time may affect the last of these.

The team should describe concrete use cases, derive functional requirements from them, prioritize core features, and distinguish committed deliverables from optional future enhancements.

## 3. Platform API Feasibility

- **LinkedIn:** Access remains blocked pending authentication and appropriate permissions for the official MSRG LinkedIn account. Michalis is working on the issue, with a follow-up expected next week.
- **X / Twitter:** The team successfully tested API retrieval using a mock account, including posts with text, links, and images. The API uses pay-per-use pricing, so usage costs should be assessed.
- **Bluesky:** The team successfully retrieved mock-account posts, including text, links, and images, using its publicly accessible API.

These initial tests support the technical feasibility of the approach, while LinkedIn access remains an unresolved dependency.

## 4. Administrator Notifications and Publishing Workflow

Thomas suggested sending a notification when new content is detected so an administrator can review it before publication. The team agreed to include administrator notifications in the project scope.

**Proposed workflow:**

1. Retrieve new content from supported platforms.
2. Normalize, filter, and check content for duplicates.
3. Notify administrators when relevant new posts are available.
4. Let administrators review and approve posts in the backend.
5. Publish approved content to the website.

The exact notification mechanism and workflow details should be finalized in the proposal and subsequent design work.

## 5. New MSRG Website and Integration

Thomas is creating a new static MSRG website, currently hosted at <https://msrg.github.io/>. It is expected to replace the existing `msrg.org` and `msrg.utoronto.ca` websites.

The team will email Thomas to discuss access to the website's source code or GitHub repository, its architecture and deployment workflow, and appropriate integration options. An iframe was mentioned as a possibility, but no integration approach has been finalized.

**Contact:** thomas.trenty@mail.utoronto.ca

## 6. Action Items

| Action item | Status |
|---|---|
| Clearly document committed in-scope features and supported use cases in the actual Project Proposal. | To do |
| Define the measurement and acceptance criterion for the 1-hour update target. | To do |
| Incorporate administrator notifications and manual review into the proposed workflow. | To do |
| Email Thomas about the new website, source repository, and integration approach. | To do |
| Follow up with Michalis about LinkedIn authentication. | Pending |
| Continue evaluating platform API limitations and usage costs. | Ongoing |

## 7. Next Steps

Prioritize a clearly scoped, measurable actual Project Proposal. In parallel, coordinate website integration with Thomas and resolve LinkedIn access with Michalis. Additional features can be considered after the committed core functionality is defined.
