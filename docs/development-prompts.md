# Development prompts

This project was built with Claude as the primary coding assistant. The full "BUILD COMPLETELY FROM SCRATCH" brief (product requirements, stack, quality bar) was used as the master prompt; the prompts below are the ones that shaped specific parts of the implementation.

## Master prompt (abridged)

> Build the "AI Study Companion" from scratch: FastAPI + MongoDB + Qdrant + Celery/Redis, React/Vite/TS/Tailwind, Firebase Auth, Gemini. Must-haves: spaces/projects with strict per-user isolation, PDF pipeline with OCR/tables/figures and background jobs (idempotent, retryable, observable), grounded Tutor with citations and unsupported-question handling and context-aware visuals (PDF figure → indexed visual → generated → none), adaptive quiz with open-ended grading, evidence-based mastery with history, growth analysis, evidence-based recommendations, project and global analytics, activity, admin dashboard, persistent learner context, structured AI outputs with prompt-injection defence, observability (ai_runs), tests, evaluation, deployment, docs.

## Architecture and isolation

> Design the Mongo collections and Qdrant payload so that no query can ever return another user's or another project's data even if a prompt is compromised. Put ownership checks in one module and return 404 (not 403) for foreign resources.

> Write a background job layer whose state lives in Mongo, with idempotency keys, max 3 attempts with backoff, terminal-failure hooks, startup recovery of stuck jobs, and a switch between Celery and inline asyncio execution so the project runs with or without Redis.

## Document pipeline

> Implement `extract_pdf` with PyMuPDF: page text, OCR fallback with Tesseract only when a page has almost no text, `find_tables` appended as text, images ≥120px extracted with a caption taken from the page heading. Then paragraph-aware chunking (~900 chars, 150 overlap) that keeps page and heading on every chunk.

> Extract 6–14 quizzable concepts per material with keywords, fall back to headings when the LLM is unavailable, and tag chunks/figures with concepts by keyword match.

## Tutor

> The Tutor must only answer from retrieved chunks of the current project. Return JSON: answer, sufficient, used_chunk_ids, concept, follow_ups, visual spec. Build citations server-side from chunk ids, drop unknown ids, clear citations when insufficient. Add a cheap retrieval-score check so obviously unsupported questions don't cost a model call.

> Define a small typed vocabulary of educational visuals (sequence, layers, steps, array, network, curve, table relation, tree) and deterministic SVG renderers with escaping. Selection order: figure on a cited page, similar indexed figure, generated SVG, none. Label generated visuals.

> Every prompt: wrap material, history and learner answers in `<data>` and include a rule that data is never an instruction. Write a test that asserts the guard is in every system prompt.

## Assessment, mastery, growth, recommendations

> Write an adaptive policy that is not "wrong → easy, correct → hard": weighted priority over weakness, recent mistakes, staleness, missing evidence and repetition; difficulty band shifts only after two consistent results; mix open-ended questions in. Unit-test the policy.

> Mastery: EWMA with a prior of 0.5, step size that shrinks with evidence, larger for hard/open evidence, larger for wrong easy answers. Keep a history row per update. Test monotonicity and bounds.

> Growth classification from history within a window, with an explicit insufficient-evidence state. Recommendations: gather mastery, mistakes, repeated-mistake patterns, materials with ids/pages; ask the model for one concrete action; validate material ids; deterministic fallback; idempotent per quiz session; supersede previous.

## Frontend

> React + Vite + Tailwind, TanStack Query. Pages: login (Firebase or dev), home (continue learning, recommendation, attention, recent projects), spaces, space detail, project dashboard, materials (upload, polling, retry, inspect chunks + PDF), tutor (conversations, actions, citations as page chips, visuals), quiz (adaptive flow with detailed feedback and mastery impact, completion summary), mastery, growth (charts), analytics (project/global), activity, admin (tabs). Every list needs loading, error and honest empty states.

## Tests and evaluation

> Write pytest tests with an in-memory Mongo (`mongomock-motor`) and a mocked LLM: isolation via the real API, mastery, adaptive policy, growth, visuals, chunking, tutor grounding, jobs. Write an evaluation runner that hits the live API with curated grounded/unsupported/injection/isolation cases and stores results in `ai_evaluations` for the admin UI.

## Review prompts used along the way

> Review `tutor.py` for any path where the model could produce a citation that is not in the retrieved set.

> Check every project-scoped router uses `ownership.get_project` before touching data.

> List every place a background job can be left in a non-terminal state and make sure recovery covers it.
