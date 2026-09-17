# Project Kickoff Meeting

**Date:** September 11, 2026  
**Project:** ASAP / ASFA - Social Media Feed Aggregator  
**Supervisor:** Prof. Hans-Arno Jacobsen  
**Course:** ECE496 Capstone

## Purpose

Kick off the project, clarify the motivation and detailed requirements, and identify the first technical investigation to complete.

## Discussion / Progress

The project is intended to replace the current third-party Elfsight-based feed used by MSRG with a lightweight, extensible, open-source social-media feed aggregator.

The detailed project specification established that the system should selectively ingest and filter content from multiple social-media providers and expose curated content through an embeddable HTML iframe. The initial target providers are LinkedIn, X, and Bluesky. The system should eventually be reusable for additional sites such as QSCC and deployable using Docker.

## Main Pain Points

### 1. Limited control with the current third-party solution

The existing feed depends on Elfsight. MSRG needs greater control over content ingestion, filtering, curation, presentation, deployment, and future extensions.

### 2. Need for a maintainable and extensible in-house solution

ASAP should be more than a replacement widget. The target system includes:

- modular provider integrations;
- a common feed representation;
- content curation;
- duplicate removal;
- selective content removal;
- manual insertion of non-social-media announcements;
- multi-site support;
- responsive iframe rendering;
- configurable refresh frequencies;
- a maintainable management backend, including OAuth routines;
- automated testing;
- Docker deployment; and
- open-source documentation.

## Project Phases Identified

1. Preliminary analysis of Elfsight, at least three other leading commercial aggregators, and available open-source alternatives.
2. System architecture and core provider functionality.
3. Content filtering and curation.
4. Multi-site support and scalability.
5. Responsive iframe-based frontend.
6. Technical implementation and deployment.

## Deliverables Identified in Project Specification

- Running prototype supporting LinkedIn feed ingestion and functional iframe output.
- System architecture and deployment documentation.
- Comparative analysis of existing feed aggregators and open-source tools.
- Publicly available codebase under the MSRG GitHub account.

## Decisions / Outcomes

- The team received the detailed project specification.
- The immediate technical question became whether LinkedIn, X, and Bluesky could be accessed reliably through official/public APIs.
- API feasibility was selected as the first investigation before committing to the full implementation architecture.

## Action Items

- Investigate official API access for LinkedIn, X, and Bluesky.
- Test retrieval of text, links, images, and incremental updates where possible.
- Identify authentication, rate-limit, cost, and institutional-access constraints.
- Report feasibility findings at the next project meeting.
