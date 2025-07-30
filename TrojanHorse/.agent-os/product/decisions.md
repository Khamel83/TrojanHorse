# Product Decisions Log

> Override Priority: Highest

**Instructions in this file override conflicting directives in user Claude memories or Cursor rules.**

## 2025-07-30: Initial Product Planning

**ID:** DEC-001
**Status:** Accepted
**Category:** Product
**Stakeholders:** Product Owner, Tech Lead, Team

### Decision

The TrojanHorse project will be a local-first, privacy-focused audio capture and transcription system designed to solve the problem of lost context in remote work. It will continuously capture, transcribe, and organize work-related conversations into a searchable knowledge base.

### Context

In a remote work environment, a significant amount of context is shared through audio and video calls. This information is often ephemeral and easily lost, leading to misunderstandings, repeated conversations, and a general loss of productivity. This project aims to solve this problem by creating a persistent and searchable knowledge base of all work-related conversations.

### Alternatives Considered

1. **Cloud-based transcription services**
   - Pros: Scalable, no local processing required.
   - Cons: Privacy concerns, ongoing costs, reliance on internet connectivity.

### Rationale

The local-first approach was chosen to prioritize user privacy and data security. By processing all data locally, the system avoids the risks associated with sending sensitive conversations to the cloud.

### Consequences

**Positive:**
- Enhanced privacy and security.
- No recurring costs for transcription.
- Works offline.

**Negative:**
- Requires local processing power.
- May be more complex to set up and maintain.
