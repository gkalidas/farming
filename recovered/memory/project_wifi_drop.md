---
name: project-wifi-drop
description: Overview of the wifi-drop project — a local Wi-Fi file transfer tool built with FastAPI and vanilla JS
metadata: 
  node_type: memory
  type: project
  originSessionId: 75bed5bb-63a6-496f-96c2-2dbe237390ff
---

A Python/FastAPI server that lets a phone upload files to a laptop over local Wi-Fi — no internet, no app needed.

**Why:** Quick offline file transfer using phone browser as client, laptop as server.

**How to apply:** When suggesting changes, keep the no-dependency-on-phone mindset; phone just needs a browser.

## Architecture

- [server.py](server.py) — FastAPI entry point, mounts routes + middleware
- [config.py](config.py) — `UPLOAD_DIR`, `STATS_FILE`, `CHUNK_THRESHOLD_MB` (500 MB)
- [upload_handler.py](upload_handler.py) — `check_existing_files()`, `handle_file_upload()` (chunked for >5 MB, overrides config's 500 MB threshold)
- [middleware.py](middleware.py) — `TimerMiddleware`: attaches UUID request_id via contextvars, times `/upload`, calls `update_stats()`
- [context.py](context.py) — `ContextVar` for per-request UUID
- [stats.py](stats.py) — load/save/update/print stats in `upload_stats.json`
- [utils.py](utils.py) — `get_local_ip()` via UDP socket trick
- [static/index.html](static/index.html) — vanilla JS, XHR with progress events, multi-file upload

## Key issues / tech debt
- `CHUNK_THRESHOLD_MB` redefined in `upload_handler.py` (5 MB) overrides `config.py` value (500 MB)
- `import rich` in upload_handler.py but `rich` not in requirements.txt and not used
- Frontend never calls `/check-existing` — duplicate detection endpoint is unused in UI
- `server__.py` and `static/index_.html` are old backup files (can be deleted)
- No file size limit enforced
- QR code mentioned in README but not implemented

## Future ideas (from README)
- Password/PIN protection
- Choose upload destination folder from UI
- PWA / offline mode
- Upload cancellation/retry
- Zip before upload
- Parallel uploads
