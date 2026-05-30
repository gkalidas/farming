---
name: feedback-working-style
description: Confirmed working preferences and collaboration patterns
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b45e6d1-97dd-4040-8221-36d727c41274
---

**Keep responses short and direct.** The user reads diffs and code — don't re-explain what was just done.
**Why:** Confirmed across multiple sessions; user never asks for summaries.
**How to apply:** End-of-turn summary = 1-2 sentences max. No narration of process.

**Same stack always.** Flask + SQLite + vanilla JS + aiohttp is the chosen stack for all projects in this workspace. Don't suggest alternatives.
**Why:** Explicitly confirmed when planning `india_security_timeline` — user said "same stack."
**How to apply:** When starting any new project here, copy config/background_scraper patterns from gov_schemes_tracker.

**Neutrality is a hard constraint for data journalism tools.** UI must show patterns, not assert conclusions.
**Why:** User explicitly stated this for both gov_schemes_tracker and india_security_timeline.
**How to apply:** Never write UI copy that implies causation. Always add normalisation (per-year, per-capita) before comparing across parties or governments.

**Plan before building.** For new projects the user wants a detailed plan/outline saved as a file before any code is written.
**Why:** User asked to "make outline/detailed note so AI tool can continue onwards" before starting india_security_timeline.
**How to apply:** Write PLAN.md first for any new project. Include data model, scrapers, API, UI, and a "how to start" section for future AI sessions.

**resume + level-aware skipping matters.** Scrapers must track progress at each level (state → district → sub-district) so they can skip already-completed levels without iterating.
**Why:** PM-KISAN scraper was printing thousands of "skipped" lines and re-checking completed work.
**How to apply:** Always build `_is_done()` / `_mark_done()` with level granularity in any new scraper.

**Any rename or replacement must be treated as a verification problem, not an edit.** When told to rename something, immediately grep the entire repo for all occurrences, fix every one, then verify with a second grep before committing. Never make partial fixes and move on.
**Why:** User explicitly called this out — said "I told you not to use it anywhere" after khetai was missed in README.md and index.html. User said the small mistake made them feel they couldn't trust me with their work.
**How to apply:** grep first, fix all, grep again to confirm zero hits. This applies to any rename, not just directory names — strings in code, comments, UI copy, HTML, config keys.
