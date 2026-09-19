# ASAP Project Timeline & Current Status

**Course:** University of Toronto ECE496 Capstone  
**Project:** ASAP - Automated Social-media Aggregation Platform  
**Supervisor:** Prof. Hans-Arno Jacobsen  
**Team:** Tianyu Ling, Shengya Huang, Molin Zhang, Zhengfei Yu

---

## Project Objective

Develop an open-source, maintainable, and extensible social-media feed aggregator for MSRG.

ASAP will initially integrate **LinkedIn, X, and Bluesky**, retrieve posts from selected organization-owned accounts, normalize and curate provider content, and expose a unified feed for website integration.

The initial deployment target is the **MSRG website**, while the architecture should remain extensible to additional providers and websites.

---

# Current Phase

## Phase 1 - Project Proposal & Preliminary Research

**Status:** In Progress  
**Period:** September - October 2026

The project is currently focused on validating the proposed direction before full implementation begins.

Current work includes:

- Project requirements clarification
- Initial API feasibility testing
- Existing-solution and open-source research
- Initial system architecture
- Proposal Meeting preparation
- Formal Project Proposal
- LinkedIn access investigation

### Work Completed So Far

**Project Snapshot**
- Initial project interpretation established
- Project questions documented
- Snapshot submitted

**September 11 - Project Kickoff**
- Detailed project requirements received
- Existing Elfsight-based workflow discussed
- Project motivation and expected technical scope clarified

**Initial API Feasibility**
- X official API POC passed
- Bluesky public-read POC passed
- LinkedIn API path investigated
- LinkedIn testing currently requires Business Account Authentication

**September 16 - Feasibility Review**
- Initial API feasibility presented to Michalis
- Feasibility investigation considered sufficient for the current stage
- Proposal preparation and existing-solution research identified as the next priorities

**Existing-Solution Research**
- Elfsight reviewed as the current MSRG solution
- Walls.io reviewed as a commercial alternative
- Harken reviewed as an open-source architectural reference

---

# Project Roadmap

```text
PAST                              NOW                              FUTURE

───────────────────────────────────────────────────────────────────────────────>

Snapshot        API           Proposal &        Core           Website       Final
& Kickoff    Feasibility       Research      Development     Integration    Delivery

    ✓             ✓               ●               ○               ○            ○

 Sep 2026      Sep 2026        Sep / Oct        Fall           Winter        Winter
```

**Legend:**  
`✓` Completed &nbsp;&nbsp; `●` Current &nbsp;&nbsp; `○` Planned

---

# Current Technical Direction

```text
 LinkedIn ──┐
 X ─────────┼──> Provider Adapters
 Bluesky ───┘
                    │
                    ▼
             Unified Post Model
                    │
                    ▼
           Filtering / Curation
                    │
                    ▼
                  Cache
                    │
                    ▼
                ASAP API
                    │
                    ▼
            Website / iframe
                    │
                    ▼
              MSRG Website
```

The architecture separates provider-specific retrieval from the common ASAP processing pipeline, allowing providers to be added or modified without redesigning the entire system.

---

# Current Status

| Area | Status |
|---|---|
| Project Snapshot | ✓ Completed |
| Detailed Requirements | ✓ Received |
| X API POC | ✓ Passed |
| Bluesky Public-read POC | ✓ Passed |
| LinkedIn API Investigation | ⚠ Business Account Authentication Needed |
| Existing-Solution Research | ● In Progress |
| Proposal Meeting Preparation | ● In Progress |
| Formal Project Proposal | ● In Progress |
| Initial Architecture | ● In Progress |
| Core Implementation | ○ Planned |
| Website Integration | ○ Planned |
| Testing & Deployment | ○ Planned |

---

# ECE496 Timeline

```text
2026

SEP                    OCT                    NOV                    DEC
│                      │                      │                      │
├─ Sep 18              ├─ Oct 10             ├─ Nov 7              ├─ Interim Demo
│  Project Snapshot    │  Project Proposal   │  Implementation     │  Nov 30-Dec 4
│  ✓                   │                     │  Plan               │
│                      │                     │                      │
└─ Sep 21-25           │                     │                      │
   Proposal Meeting    │                     │                      │
   ●                   │                     │                      │


2027

JAN                    FEB                    MAR
│                      │                      │
├─ Jan 10-16           ├─ Feb 2 / 4 / 9      ├─ Mar 20
│  Admin Design        │  Oral Presentation  │  Final Report
│  Review              │  Final Evaluation   │
│                      │                      │
├─ Jan 19 / 21 / 26    │                      ├─ Mar 23-25
│  Presentation        │                      │  Design Fair &
│  Feedback            │                      │  Poster Presentation
│                      │                      │
└─ Jan 24-30           │                      └─ Mar 27
   Technical Design    │                         Best-Team Showcase
   Review              │                         (if selected)
```

---

# Key Upcoming Milestones

| Date | Milestone | Project Focus |
|---|---|---|
| **Sep 21-25, 2026** | Proposal Meeting | Present project direction, feasibility, architecture, and plan |
| **Oct 10, 2026** | Project Proposal | Formalize requirements, design, and implementation approach |
| **Nov 7, 2026** | Implementation Plan | Define implementation and testing strategy |
| **Nov 30-Dec 4, 2026** | Interim Demo | Demonstrate interim technical progress |
| **Jan 24-30, 2027** | Technical Design Review | Review technical implementation with supervisor |
| **Feb 2 / 4 / 9, 2027** | Oral Presentation Final Evaluation | Present project progress and design |
| **Mar 20, 2027** | Final Report | Submit complete engineering report |
| **Mar 23-25, 2027** | Design Fair | Demonstrate final ASAP system |

---

# Immediate Action Items

- Complete Proposal Meeting presentation
- Complete formal Project Proposal
- Complete existing-solution comparison
- Continue LinkedIn Business Account Authentication investigation
- Refine initial ASAP architecture
- Prepare for implementation following proposal feedback

---

# Documentation

Project documentation is maintained through the team's shared Google Drive and GitHub repository.

The repository is intended to contain:

- Requirements
- Meeting minutes
- Existing-solution research
- API feasibility investigations
- Provider POCs
- Architecture documentation
- Source code
- Tests
- Deployment configuration
- Engineering documentation

**Shared Google Drive:**  
https://drive.google.com/drive/folders/18Og0OanPjyRoiOnd3dT5Sb8wzWtRQ5Kw?usp=sharing