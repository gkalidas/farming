---
name: project-security-timeline
description: New project idea — India security attack timeline correlated with elections. Planned but not started.
metadata: 
  node_type: memory
  type: project
  originSessionId: 1b45e6d1-97dd-4040-8221-36d727c41274
---

User wants to build a separate data journalism project: `india_security_timeline`.

**Goal:** Plot major terrorist/militant attacks in India on a timeline alongside election dates, showing ruling party, casualties, official response, and days before the nearest election. Tool shows patterns neutrally — user draws conclusions.

**Status:** Fully planned, no code written. Full plan at:
`/Users/glondhe/Library/CloudStorage/OneDrive-TriNetUSA,Inc/workspace/india_security_timeline/PLAN.md`

**Key decisions already made:**
- Separate project from gov_schemes_tracker (different domain, same stack)
- Same Flask + SQLite + vanilla JS + aiohttp pattern as [[gov-schemes-tracker]]
- Primary data source: SATP (South Asia Terrorism Portal) — incident-level HTML tables
- Elections data: Wikipedia (easier) cross-verified with ECI PDFs
- Government periods: static table, pre-populated (see PLAN.md for the data)
- UI must normalise by years in power — don't compare raw counts across parties
- Every data point must link to a source URL

**Why:** User hypothesises attacks cluster before elections. Project should let data answer that without asserting causation in the UI.

**How to apply:** When user asks to start building this, read PLAN.md first — it has full data model, scraper targets, API design, and a "how to start" section.
