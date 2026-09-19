# Architecture

## Overview

```
Browser (React/Vite)  ──HTTPS──▶  FastAPI (app/main.py)
                                   │  auth: Firebase ID token → user (app/core/security.py)
                                   │  every project route: ownership check (services/ownership.py)
                                   ├──▶ MongoDB      (all application state, events, jobs, ai_runs)
                                   ├──▶ Qdrant       (chunk + figure vectors; payload filtered by user_id + project_id)
                                   ├──▶ Gemini       (via services/llm.py only)
                                   └──▶ Job queue    (Celery/Redis, or inline asyncio) ──▶ worker runs the same handlers
```

The backend is a modular monolith: thin routers in `app/api/*`, all logic in `app/services/*`. Background handlers (`documents.process_material_job`, `workflows.post_quiz_workflow`) are ordinary async functions registered with `@handler`, so the API process and the Celery worker run identical code.

## Data model (MongoDB)

| Collection | Purpose |
|---|---|
| `users` | Upserted on every authenticated request: uid, email, is_admin, last_seen. |
| `spaces`, `projects` | Hierarchy. `projects.last_activity_at/_type` drive "continue learning". |
| `materials` | Upload metadata, processing status (`queued/processing/ready/failed`), error, counts, sha256 for dedupe. |
| `material_chunks` | Page-aware text chunks with heading + tagged concepts (source of truth for citations). |
| `visual_assets` | Extracted figures (file, page, caption, concepts). |
| `concepts` | Per-project concept list extracted from materials (unique on project_id + name). |
| `conversations`, `messages` | Tutor. Assistant messages store citations, visual, concept, sufficiency, retrieval count. |
| `quiz_sessions`, `quiz_questions`, `quiz_answers` | Assessment. Questions store the selection reason, sources, correct answer/reference/key points; answers store the grade breakdown. |
| `mastery`, `mastery_history` | Current estimate per concept + every change with score/difficulty/kind/source. |
| `learner_context` | Persistent per-project context: strengths, weaknesses, repeated mistakes, recent topics. |
| `recommendations` | One active recommendation per project; previous ones superseded; idempotent per trigger. |
| `activity_events` | Append-only event log (optional `dedupe_key`). Feeds activity, analytics, admin, workflows. |
| `ai_runs` | One row per model call: feature, latency, tokens, estimated cost, retrieval counts, success/error, attempts. |
| `background_jobs` | Job state machine with idempotency key, attempts, errors, timestamps. |
| `ai_evaluations` | Stored evaluation runs. |

Ids are UUID hex strings. Indexes are created at startup (`db/mongo.py`).

## Request flows

**Upload** `POST /api/projects/{id}/materials` → validate PDF/size → sha256 dedupe → write to `STORAGE_DIR` → `material_uploaded` event → enqueue `process_material` (idempotency key `process_material:<material_id>`) → 202 with the material doc. The client polls `GET /api/projects/{id}/materials` while any item is queued/processing.

**Processing job** → status `processing` → PyMuPDF extraction per page (OCR only when a page has <40 chars of text and Tesseract is present; tables via `find_tables`; images ≥120px) → concept extraction (LLM over a sampled 9k-char slice, heading fallback) → chunking (paragraph-aware, ~900 chars, 150 overlap, min 60) → concept tagging by keyword → embeddings (local MiniLM) → Qdrant upsert (text chunks and figure captions, payload includes `user_id`, `project_id`, `material_id`, `page`, `type`) → Mongo chunks/visuals/concepts → status `ready` + `material_processed`. On final failure the `on_final_failure` hook sets `failed` + error and emits `material_failed`. Re-processing deletes previous chunks/vectors first, so the job is safe to re-run.

**Tutor** see [ai.md](ai.md).

**Quiz** `POST .../quiz/start` → session → `next_question` (adaptive selection + grounded generation) → `POST .../answer` grades, stores the answer, updates mastery + history, emits `question_answered`/`mastery_updated`; on the last answer: `assessment_completed` + enqueue `post_quiz_workflow` (key `post_quiz:<session_id>`). Re-submitting an answered question returns the stored result (idempotent).

**Post-quiz workflow** → weak/strong detection → repeated-mistake patterns (≥2 wrong of the last 4 answers on a concept) → `learner_context` update → `repeated_mistake_detected` events → recommendation generation (idempotent per session).

## Isolation

- Identity only from the verified token (or `X-Dev-User` in `AUTH_MODE=dev`), never from request bodies.
- `services/ownership.py` is the only way to load a space/project/material; it filters by `user_id` and returns 404 otherwise (no existence leak).
- Every Qdrant query uses `project_filter(user_id, project_id)`; `retrieval.retrieve` re-checks payload ownership as defense in depth. Tests assert the filter keys.
- Deleting a project cascades through all collections and vectors; deleting a material removes its chunks, vectors, files and orphaned concepts.
- Admin routes use `require_admin` (email allow-list from `ADMIN_EMAILS`), checked on the server.

## Background jobs

`services/jobs.py` persists every job in Mongo and dispatches to Celery (`JOB_BACKEND=celery`) or an asyncio task in the API process (`inline`). `auto` picks Celery when `REDIS_URL` is set. Features: idempotent enqueue (active job with the same key is returned, terminal jobs are re-created on explicit retry), up to 3 attempts with backoff, state `queued → processing → retrying → completed | failed`, failure hooks, startup recovery of jobs stuck for >15 min, admin retry. The browser never needs to stay open.

## Observability

Every model call goes through `LLM.generate` → `ai_runs` (feature, model, latency, tokens, estimated cost, retrieval counts, success, error, attempts). Analytics and admin aggregate these. Application logs use standard `logging`; unhandled exceptions are logged and return a generic 500.

## Frontend

`src/lib/api.ts` attaches the Firebase bearer token (or dev header). `AuthProvider` exposes the current user from `/api/me`. Routes are protected client-side (and, more importantly, server-side). Each project page reads a focused endpoint; TanStack Query handles caching, polling (materials) and invalidation after mutations. Visual output from the Tutor is either an authenticated image blob (material figure) or sanitized-by-construction SVG produced by the server's deterministic renderer (the model only supplies a structured spec, never markup).
