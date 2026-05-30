---
name: project-personal-assistant
description: "GK — personal AI assistant, multi-module router, not started yet"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1b45e6d1-97dd-4040-8221-36d727c41274
---

# GK — Personal AI Assistant

Not started yet. Farming is module #1. Build this umbrella after farming is stable.

## Identity
- Name: **GK**
- Boot greeting: "Welcome to the future, GK"
- Primary filter on every response: does this move toward **health** or **wealth**?

## Memory system (Option C — confirmed)
- `user_profile.json` — fast access: goals, health context, financial situation, preferences. Updated as user shares things.
- `events.db` — event log, ground truth. Every query + answer stored. Profile is corrected from this.

## Intelligence augmentation
After each answer, one sentence: a follow-up question, a connection to something asked before, or "next time you see X, look for Y." Not a lecture — one hook.
Weekly "here's what you learned this week" summary.

## Privacy proxy (hard rule)
Personal context NEVER leaves the machine. All web queries go through an anonymizer — strips name, age, location, medical specifics. "32yo male in Pune with knee injury" → "treatment options for knee injury". User's identity is never inferred from outbound queries.

## Modules (planned order)
1. **Farming** — already being built (llama3.2-vision + ONNX + weather/soil tools)
2. **Finance** — text only, wealth goal, best early test for module blending
3. **Health/Body** — injury, medicine, routines — high privacy sensitivity
4. **Fashion** — deferred, needs live fashion data sources

## Router behavior
- Small fast local model (qwen2.5:3b or llama3.2:3b) classifies intent
- Can dispatch to multiple modules for blended answers
- Example blend: "adjust farming budget because monsoon hit yield" → finance + farming

## Architecture shape
```
gk/
├── boot.py              # greeting + startup checks
├── router/
│   ├── dispatcher.py    # intent → module(s)
│   ├── blender.py       # multi-module response assembly
│   └── privacy.py       # anonymize before any web call
├── memory/
│   ├── profile.py       # user_profile.json
│   ├── event_log.py     # events.db
│   └── learnings.py     # weekly summary
├── modules/
│   ├── base.py          # BaseModule contract (reuse from farming)
│   ├── farming/         # plug in existing farming project
│   ├── finance/
│   └── health/
├── tools/
│   ├── web_search.py    # anonymized search
│   └── web_fetch.py
└── ui/
    └── chat.py          # single chat, no visible module switching
```

## Input layer
All formats accepted: text, document (PDF/Word/Excel), photo, audio, video.
All processing local — no cloud transcription. Audio/video via Whisper (local, MPS).

Every input goes through metadata extraction before routing:
- Photo: EXIF DateTimeOriginal, GPS, device model
- Document: file creation date, modified date, author
- Audio/Video: creation timestamp, duration, GPS if embedded
- All inputs: ingestion timestamp always stored as fallback

Two timestamps always stored: **event time** (when it happened) + **ingestion time** (when GK received it). Enables true timeline reconstruction — e.g. batch of old farm photos ordered by capture date not upload date.

## Diary layer
- GK auto-drafts diary entry after every session (nothing lost)
- User reviews/approves at day end ("wrap up today")
- Stored as both structured JSON (queryable) + markdown (readable)
- Entries tagged by module: farming, health, finance, general
- Diary reconstruction uses event timestamps, not ingestion timestamps

## Analysis layer
- Weekly: decisions made + outcomes
- Pattern detection across diary entries
- Goal alignment: are actions moving toward health/wealth?
- Causal links across modules (yield drop → traced to skipped spray schedule)

## Knowledge graph (mind map)
Every entity = node. Every connection = edge.
Node types: People, Places, Events, Media, Topics (health, finance, farming seasons).
Person node: personal info, all shared events, all photos together, co-appearance graph, full timeline.
Visualization: vis-network (offline JS, interactive, clickable nodes) in web UI.
GK **suggests** relationship links, user confirms with one tap — never auto-commits.
Storage: SQLite with graph schema.

## People identification (background worker)
InsightFace (local, MPS) clusters unknown faces across photos.
When idle, surfaces unknowns one at a time:
> "I found this face in 5 photos. Who is this?"
User gives name + story → GK maps all occurrences, backdates diary entries to EXIF timestamps.

## Threat model / personal OPSEC layer
GK builds personal security analysis from stored data:
1. **Information inventory** — what GK holds, who else knows it, how/when shared
2. **Who knows what map** — each person has a `knows[]` list: what they've seen, been told, can infer
3. **Vulnerability scoring** — flags info that could be misused, rated low/medium/high:
   - Leverage: sensitive moments, financial pressure, health issues
   - Pattern exposure: routines, locations, regular contacts
   - Association risk: linked to certain people in certain contexts
   - Metadata exposure: GPS/timestamps in photos/docs revealing more than intended
4. **What-if scenarios** — "If this person became adversarial, what do they already know?"

Goal: intentional awareness, not paranoia. User decides what to share knowing the full picture.

## Confirmed decisions
- **Web search**: SearXNG self-hosted on Linux machine — queries never touch third-party servers
- **Router model**: test qwen2.5:3b vs llama3.2:3b on 20 routing examples, pick the winner
- **UI**: terminal chat first, web UI after logic is solid
