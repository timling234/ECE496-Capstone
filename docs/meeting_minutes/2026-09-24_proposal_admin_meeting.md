
# Meeting Minutes — Proposal Meeting with Course Administrator

**Date:** September 24, 2026  
**Project:** ECE496 Capstone — ASAP / MSRG News  
**Meeting Type:** Proposal Presentation & Administrative Feedback  
**Attendees:** Capstone Team and Course Administrator

## 1. Meeting Overview

The team presented the proposed MSRG News Aggregation System, including its motivation, system architecture, planned features, and initial technical feasibility research.

The administrator provided positive feedback and discussed opportunities to improve the project's applicability, authentication and security, and technical approach to reducing publication delays.

## 2. Project Presentation

The team presented the following core features:

- Multi-platform integration supporting LinkedIn, X (Twitter), and Bluesky.
- A manageable backend for configuring and managing social media sources.
- Content retrieval, normalization, filtering, deduplication, storage, and publication.
- Integration with the MSRG website.
- A target of reducing publication delays from approximately 48 hours to one hour.

The team also presented its initial API feasibility research.

## 3. Administrator Feedback

### 3.1 Broader Applicability

The administrator suggested considering how the system could support users beyond the initial MSRG deployment.

Potential extensions include:
- Supporting additional platforms, such as Facebook.
- Allowing other researchers or organizations to use the system.
- Designing the backend to accommodate additional integrations.

These suggestions should be evaluated against the project's available time and technical constraints.

### 3.2 Authentication and Security

The administrator asked how users would authenticate their social media accounts and how their credentials would be protected.

The team explained that:
- The professor would be the initial user.
- The initial implementation would use authorized API access to the professor's social media accounts.
- The team plans to obtain the necessary LinkedIn API access through the professor.

The administrator suggested considering a more general authentication mechanism that would allow additional users to connect their own accounts securely.

Multi-user authentication is a potential extension rather than a confirmed requirement.

### 3.3 Main Technical Challenge: Publication Delay

The administrator asked the team to identify its most significant technical challenge.

The team identified the current publication delay of approximately 48 hours.

The source of this delay remains uncertain. Possible causes include:
- The existing third-party provider.
- LinkedIn's own content availability or API limitations.
- Other components of the existing retrieval process.

The team proposed the following approaches:

1. Investigate the source of the existing publication delay.
2. Determine whether direct LinkedIn API access can reduce the delay.
3. Retrieve relevant content from alternative platforms, including X and Bluesky.
4. Prioritize available content from alternative platforms when LinkedIn updates are delayed.

The target is to reduce the publication delay to approximately one hour.

## 4. Initial Technical Feasibility

The team presented its initial API research.

| Platform | Current Status |
|---|---|
| LinkedIn | Awaiting official account access and required business verification |
| X (Twitter) | Initial API access and post retrieval successfully tested; pay-per-use pricing |
| Bluesky | Public API access and post retrieval successfully tested; free public API |

The initial results suggest that the proposed system is technically feasible.

However, LinkedIn integration and the publication delay remain unresolved.

## 5. Communication and Future Meetings

The team asked whether regular meetings with the administrator would be required.

The administrator clarified that:
- Regular meetings are not typically necessary.
- The team can contact the administrator by email for additional feedback.
- The team may share its proposal before formal submission for high-level feedback, subject to availability.

The team explained that Michalis, the professor's PhD student, is its primary technical contact.

The team expects to continue meeting with Michalis regularly to discuss implementation progress and LinkedIn API access.

## 6. Action Items

| Priority | Action Item |
|---|---|
| High | Investigate the source of the existing 48-hour publication delay. |
| High | Follow up with Michalis regarding LinkedIn API access. |
| High | Clearly define the committed project scope in the written proposal. |
| High | Prepare the written proposal and incorporate relevant feedback. |
| Medium | Document API authentication and credential security. |
| Medium | Evaluate broader applicability and potential multi-user support. |

## 7. Overall Feedback

The administrator expressed positive feedback regarding the team's presentation, project organization, and progress.

Three areas were identified for further consideration:

1. Broader applicability beyond MSRG.
2. Secure authentication and account management.
3. Reducing publication latency and identifying the underlying technical challenges.

The team will incorporate relevant feedback into its written proposal while maintaining a manageable project scope.

**Note:** Broader deployment, multi-user authentication, and additional social media platforms were suggested extensions, not mandatory project requirements.
