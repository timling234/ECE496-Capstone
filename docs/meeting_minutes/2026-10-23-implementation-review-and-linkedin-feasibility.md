# Meeting Minutes — Implementation Review and LinkedIn Feasibility

**Date:** October 23, 2026  
**Project:** ECE496 Capstone — ASAP / MSRG News Aggregation  
**Meeting Type:** Progress Demonstration and Technical Feedback  
**Attendees:** Project team and reviewer(s); individual speakers cannot be reliably identified from the supplied transcript.

**Source note:** Prepared from the user-supplied meeting transcript. Automatic transcription is substantially distorted. The meeting date follows the user's description of this as today's meeting. Unclear names, permission identifiers, and scheduling details are not treated as confirmed facts. This record documents discussion and follow-up work; it does not by itself revise implementation acceptance criteria.

## 1. Meeting Summary

The team demonstrated the current implementation, including source configuration, retrieved posts, and the manual approval/rejection workflow. The feedback focused on reducing manual content-curation work through an instruction-driven agent or LLM, and on resolving whether LinkedIn's official API can retrieve the content actually required by the project.

LinkedIn feasibility should be investigated promptly rather than waiting indefinitely for application approval without first confirming that the requested API and permissions support the intended use case.

## 2. Current Implementation Demonstration

- The discussion referred to configured source accounts/providers and the posts retrieved from them.
- Approval and rejection currently involve manual administrator actions.
- The reviewer asked the team to consider how automated filtering could fit into the existing implementation.

The transcript does not establish additional completed acceptance tests, a production deployment, or successful LinkedIn retrieval. These should not be inferred from the demonstration.

## 3. Agent / LLM-Assisted Content Filtering

The reviewer proposed supplying an agent with specific instructions so it can evaluate retrieved content against the intended selection criteria, reducing the need to perform every curation step manually. The reviewer encouraged the team to investigate and try integrating this capability with the current system.

The team raised the possibility of running a local model and the question of how the model would remain available when the application is eventually hosted on a server.

### Follow-up interpretation and boundaries

- Explore an instruction-driven filtering proof of concept and explain how it would connect to the existing pipeline.
- Establish what instructions/content criteria the agent should follow and how its output will be evaluated.
- Consider local-model versus hosted execution and the resources/availability required for eventual deployment.
- The transcript does **not** clearly settle whether automation would only assist relevance filtering, recommend editorial actions, or make final approval/rejection decisions. Confirm that boundary before changing publication behavior.
- No model, hosting provider, concrete keyword rules, or permission to automatically publish content was established.

## 4. LinkedIn API Access and Required Retrieval Scope

### 4.1 Application and documentation review

The team walked through LinkedIn Developers, an existing application, the Community Management API access request, and API documentation including the Posts API and permissions. The team reported that an access application had already been submitted and that a response was still outstanding. The precise submission date is unclear in the transcript.

### 4.2 Main feasibility question

The reviewer questioned whether the API supports the project's required retrieval scope, especially the distinction between:

- An authorized organization/page's posts.
- An authorized member's posts.
- Posts from other or arbitrary accounts, which may require different access or may not be supported for the intended use.

The discussion included statements about retrieving posts by specifying an account, but these were challenged or remained uncertain. **The meeting did not verify that arbitrary-account retrieval is permitted or technically available.**

The team should identify the exact endpoints, permissions, account roles/authorization, and permitted use needed for the actual MSRG use case. API access approval and the API's supported retrieval scope are separate questions.

### 4.3 Follow-up priority

The reviewer urged the team to check this promptly, with discussion suggesting the next few days, so the team does not spend further time waiting for access to an API that may not satisfy the requirement. Bring back documentation-backed findings and remaining uncertainty.

Open-source scraping/crawling approaches were mentioned as possible avenues to investigate if the official route proves unsuitable. **No alternative was selected or validated, and this discussion does not authorize implementing a scraper or bypassing platform restrictions.** Any alternative would require a separate feasibility and compliance review and an explicit integration decision.

## 5. Follow-Up Meetings and Demonstration Preparation

- The participants discussed meeting again in approximately two weeks and coordinating a suitable time.
- References to particular weeks, weekdays, and a possible November date are too unclear to establish a confirmed calendar appointment.
- The timing of the course interim demonstration was discussed. One participant thought it might be after the Christmas break, but this was explicitly uncertain; verify the course's official schedule.
- Prepare a short progress presentation/demo for subsequent meetings. A limit of approximately five minutes was mentioned; confirm the exact expectation if needed.

No firm course deadline or interim-demo date should be derived from this transcript.

## 6. Action Items

| Action item | Responsible party | Status / evidence needed |
|---|---|---|
| Identify the exact LinkedIn endpoints and permissions required for MSRG's organization/member retrieval use cases. | Project team | Priority follow-up; documentation-backed findings needed. |
| Confirm which account roles and authorization are required, and whether the required accounts/content can actually be retrieved. | Project team, with account owner/reviewer clarification as needed | Unresolved; arbitrary-account retrieval is not verified. |
| Continue tracking the submitted Community Management API application. | Project team | External response pending; access approval alone does not establish supported scope. |
| Explore an instruction-driven agent/LLM filtering proof of concept within the current pipeline. | Project team | Requested exploration; concrete rules and evaluation approach needed. |
| Confirm whether automation assists filtering/review or may make final editorial decisions. | Project team and stakeholder/reviewer | Decision needed before changing approval/publication behavior. |
| Assess local versus hosted model execution and deployment availability. | Project team | No hosting or model decision made. |
| Confirm the next meeting date/time and official interim-demo schedule. | Project team and reviewer(s) | Tentative discussion only. |
| Prepare a concise progress presentation/demo for follow-up meetings. | Project team | Approximately five minutes mentioned; exact expectation to confirm. |

## 7. Implications for the Living Design

This meeting introduces a request to investigate agent-assisted filtering and prioritizes verification of LinkedIn's actual retrieval scope. It does not establish successful LinkedIn integration, approve a fallback retrieval mechanism, or replace administrator approval with automatic publication. Record any resulting scope/architecture change separately once the necessary decisions and feasibility evidence are available.
