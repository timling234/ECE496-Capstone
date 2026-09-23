# Meeting Minutes — Proposal Meeting Feedback

**Date:** September 22, 2026  
**Project:** ECE496 Capstone — ASAP / MSRG News  
**Meeting Type:** Proposal Presentation / Feedback Meeting

## Meeting Summary

The team presented the current proposal slides and system design. The discussion focused on improving the clarity of the presentation and, more importantly, defining the backend workflow, data normalization, storage structure, duplicate handling, and system manageability.

## Presentation Feedback

### Slide 2 — Project Description
- Convert the project description into concise bullet points instead of paragraph-style text.
- Present the main ideas sequentially so the audience can understand the project more easily during the presentation.

### Slide 3 — Problem / Motivation
- Make the slide layout symmetric.
- Place two points on the left and two points on the right.
- Center and align the icons to improve visual balance.

### Slide 4 — System Workflow
- The diagram should clearly show the transitions between different stages of the system.
- Divide the workflow into phases and indicate where each phase starts and ends.
- The workflow should explain not only what components exist, but also how data moves through the system.

A proposed high-level workflow is:

**Social Media APIs → Raw Posts → Normalization → Deduplication / Priority Decision → Data Store → Manageable Backend → MSRG News**

## Technical Discussion

### 1. Data Acquisition
The first stage of the system retrieves posts from supported social media APIs, such as X, Bluesky, and LinkedIn.

The system should be designed so that additional social media platforms can be integrated in the future without major changes to the overall architecture.

### 2. Post Normalization
Posts retrieved from different platforms have different data formats. The system therefore needs a normalization stage that converts platform-specific API responses into a common internal format.

The normalized format may include information such as:
- Source platform
- Account name / ID
- Original post ID
- Timestamp
- Post content
- Media or links
- Other relevant metadata

The purpose of normalization should be clearly explained in the presentation.

### 3. Duplicate Detection and Publication Priority
An important question was raised regarding posts containing the same or similar content across multiple platforms.

For example, if the same announcement is posted on both LinkedIn and Bluesky:
- Should both versions be published to MSRG News?
- If only one should be published, which platform should take priority?
- How should the system determine that two posts represent the same content?

The team needs to define a deduplication and/or priority policy.

This decision is closely related to normalization because the normalized representation allows posts from different platforms to be compared consistently before publication.

### 4. Data Store / Database
The role of the data store needs to be explained more clearly.

The team should determine what information will be stored, potentially including:
- Original/raw posts
- Normalized posts
- Source platform and account information
- Post IDs and timestamps
- Publication status
- Whether a post has already been published to MSRG News
- Duplicate/grouping information
- Priority or selection information

The database should provide a reliable way to track what content has already been processed and published.

**SQLite** was discussed as an initial option for implementing the backend database. The team will further define the database schema and determine which data should be stored.

### 5. Data Retention
Christina raised the question of whether old data should be periodically cleared from storage.

Barry suggested that storage management could potentially be controlled through the manageable backend.

Michalis indicated that there is currently no need to periodically delete the stored data, and that historical data can be retained.

For the initial implementation, the team will therefore assume persistent storage.

### 6. Manageable Backend
The concept of a "manageable backend" needs to be defined more concretely.

The backend should make it easy to:
- Modify system configuration.
- Manage monitored accounts and sources.
- Manage or adjust content before publication where appropriate.
- Configure publication-related behavior.
- Add APIs for new social media platforms in the future.

A question was raised about what exactly can be modified if the system primarily retrieves existing social media posts.

The team should distinguish between the **original source content**, which should remain unchanged, and the **processed/publication representation and system configuration**, which may be managed before content is published to MSRG News.

## Scope and Website Integration

Website integration is **not the current priority**.

The near-term focus should remain on the backend pipeline:

**API Integration → Normalization → Deduplication / Priority Logic → Data Storage → Manageable Backend**

Integration with the MSRG News website will be addressed later, potentially around **November**, after the core backend workflow and data model are established.

## Action Items

- Revise Slide 2 into concise bullet points.
- Make Slide 3 symmetric with two points on each side and centered icons.
- Redesign Slide 4 to clearly show workflow transitions and project phases.
- Clearly define and explain post normalization.
- Determine the policy for duplicate posts across different social media platforms.
- Determine publication priority when equivalent content exists on multiple platforms.
- Design the initial SQLite database schema.
- Define what raw, normalized, source, and publication-status data should be stored.
- Define the functionality and scope of the manageable backend.
- Keep the backend modular so new social media APIs can be added easily.
- Prioritize the backend/data pipeline before website integration.