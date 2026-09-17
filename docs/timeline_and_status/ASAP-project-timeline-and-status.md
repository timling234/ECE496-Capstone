# ASAP Project Timeline & Current Status

**Course:** University of Toronto ECE496 Capstone  
**Project:** ASAP - Automated Social-media Aggregation Platform  
**Supervisor:** Prof. Hans-Arno Jacobsen  
**Team:** Tianyu Ling, Shengya Huang, Molin Zhang, Zhengfei Yu

## Project Objective

Develop an open-source, maintainable, and extensible social-media feed aggregator for MSRG. The system will initially integrate LinkedIn, X, and Bluesky, curate and normalize provider content, and expose the resulting feed for website integration.

## Timeline

### Initial Project Discussion / Snapshot Preparation

The team established its initial interpretation of ASAP, prepared the Project Snapshot, and documented questions about project motivation, technical depth, APIs, content handling, hosting, and scope.

**Outcome:** Project Snapshot submitted and initial questions subsequently clarified.

### September 11, 2026 - Project Kickoff

The team received the detailed project requirements and clarified the motivation for replacing the existing Elfsight-based MSRG feed.

Two central needs were identified:

1. Greater control over ingestion, curation, filtering, display, and deployment.
2. A maintainable and extensible open-source system rather than dependence on a third-party widget.

The project requirements include preliminary competitor/open-source analysis, modular provider architecture, content curation, multi-site support, responsive iframe rendering, Docker deployment, testing, and documentation.

**Immediate next step:** establish API feasibility for LinkedIn, X, and Bluesky.

### September 16, 2026 - Feasibility Review with Michalis

The team presented its initial API feasibility study.

- **X:** Official API POC passed for text, links, images, and incremental polling.
- **Bluesky:** Public-read POC passed; simplest tested integration.
- **LinkedIn:** Technically feasible, but further testing requires institutional/organization authorization.

Michalis indicated that this initial feasibility phase was essentially complete.

**New priorities for the following two weeks:**

1. Complete the ECE496 Proposal and Proposal Meeting preparation.
2. Conduct preliminary market/open-source analysis of existing feed aggregators and compare them against ASAP requirements.

## Current Technical Direction

LinkedIn / X / Bluesky  
-> Provider Adapters  
-> Unified Post Model  
-> ASAP API  
-> MSRG Website

## Current Project Status

- Project Snapshot: **Completed / submitted**
- Detailed requirements: **Received**
- Initial API feasibility: **Substantially completed**
- X POC: **Passed**
- Bluesky public-read POC: **Passed**
- LinkedIn POC: **Pending institutional authorization**
- Proposal preparation: **Current priority**
- Existing-solution / open-source analysis: **Current priority**
- Full implementation: **Next phase**

## Documentation

Shared Google Drive: https://drive.google.com/drive/folders/18Og0OanPjyRoiOnd3dT5Sb8wzWtRQ5Kw?usp=sharing

GitHub repository structure is intended to maintain formal project documents, meeting minutes, tests/POCs, prototypes, source code, and supporting engineering documentation.

## Immediate Action Items

- Prepare Proposal Meeting material.
- Complete formal Project Proposal.
- Review proposal with the supervisor/team.
- Analyze Elfsight and at least three other leading commercial feed aggregators.
- Identify and evaluate open-source alternatives.
- Create a comparison matrix against ASAP requirements.
- Continue LinkedIn access/authorization follow-up.
- Begin unified provider architecture after proposal/preliminary-analysis priorities are addressed.
