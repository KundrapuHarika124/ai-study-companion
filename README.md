# AI Study Companion

A learning workspace where a learner uploads their own PDFs, learns with a Tutor that is grounded in that material (with page citations and context-aware visuals), takes adaptive quizzes, and gets an evidence-based picture of mastery, growth and what to do next.

- **Backend:** FastAPI · MongoDB (Motor) · Qdrant · local sentence-transformers embeddings · Google Gemini · Celery + Redis (or inline jobs)
- **Frontend:** React 18 · Vite · TypeScript · Tailwind · TanStack Query · Firebase Auth
- **Docs:** [architecture](docs/architecture.md) · [AI design](docs/ai.md) · [evaluation](docs/evaluation.md) · [decisions](docs/decisions.md) · [development prompts](docs/development-prompts.md)

## What it does

| Area | Behaviour |
|---|---|
| Spaces → Projects | Each project is an isolated learning journey: its own materials, knowledge index, Tutor conversations, quizzes, mastery, recommendations and activity. |
| Materials | PDF upload → background job: text extraction (PyMuPDF), OCR fallback (Tesseract), tables, figure extraction, page-aware chunking, LLM concept extraction, embedding, Qdrant indexing. Status, progress, errors and retry are visible in the UI. |
| Tutor | Retrieval limited to the current user + project. Cheap sufficiency check, then structured LLM output. Citations are built server-side from the retrieved chunks (the model cannot invent them). "Not covered by your material" when evidence is insufficient. Visuals: figure from the cited page → semantically similar project figure → deterministic AI-specified SVG (labelled) → none. |
| Quiz | Adaptive concept selection (weakness + recent mistakes + staleness + no-evidence − repetition), difficulty band that only moves after two consistent results, MCQ + open-ended. Open answers graded on understanding with what was right / missing / incorrect. |
| Mastery | Evidence-weighted estimate per concept with full history; harder/open evidence moves it more; never guessed for unassessed concepts. |
| Growth | improving / stable / attention / insufficient evidence, computed from mastery history within a window. |
| Recommendations | Generated after each quiz (background workflow) from mastery, mistakes, repeated-mistake patterns and materials; references real concepts, materials and pages; deterministic fallback if the LLM is unavailable. |
| Analytics · Activity | Everything is computed from stored events, answers, mastery rows and AI runs. |
| Admin | Users, per-user journey, filterable activity, AI runs (latency/tokens/cost/failures), background jobs (retry), evaluation results, system health. Enforced by the API. |

## Run it locally

Prerequisites: Python 3.11+, Node 18+, Docker (for Mongo/Qdrant/Redis), a Gemini API key. Tesseract is optional (only for scanned PDFs): `apt install tesseract-ocr` / `brew install tesseract` / Windows installer.

```bash
# 1. Infrastructure
docker compose up -d            # MongoDB :27017, Qdrant :6333, Redis :6379

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt                   # first run downloads the embedding model (~90 MB)
cp ../.env.example .env
#   edit .env: GEMINI_API_KEY=...   AUTH_MODE=dev   ADMIN_EMAILS=you@example.com
uvicorn app.main:app --reload --port 8000

# 3. (optional) Celery worker. Without it, JOB_BACKEND=auto with REDIS_URL set will try Celery,
#    so either run the worker or set JOB_BACKEND=inline / REDIS_URL= to run jobs inside the API process.
celery -A app.workers.celery_app worker --loglevel=info --pool=solo   # --pool=solo on Windows

# 4. Frontend
cd ../frontend
npm install
cp .env.example .env            # VITE_AUTH_MODE=dev matches backend AUTH_MODE=dev
npm run dev                     # http://localhost:5173  (proxies /api → :8000)
```

Sign in with any email in dev mode (use the one in `ADMIN_EMAILS` to see the admin dashboard). Create a space → project → upload a PDF → wait for **ready** → ask the Tutor → take a quiz.

### Real authentication (Firebase)

1. Create a Firebase project, enable Email/Password and Google sign-in.
2. Backend `.env`: `AUTH_MODE=firebase`, `FIREBASE_CREDENTIALS_JSON=./firebase-service-account.json` (download from Project settings → Service accounts).
3. Frontend `.env`: `VITE_AUTH_MODE=firebase` + the `VITE_FIREBASE_*` values from the web app config.

### Tests

```bash
cd backend && pytest -q
```

Tests cover mastery maths, adaptive selection policy, growth classification, visual rendering, chunking, Tutor grounding/citation validation/unsupported handling (LLM mocked), job idempotency/retry/failure hooks, and API auth + project isolation (in-memory Mongo, no external services needed).

### AI evaluation

```bash
cd backend && cp evals/cases.example.json evals/cases.json   # fill in a project id that has a processed PDF
python -m evals.run_evals evals/cases.json
```

Results are stored in `ai_evaluations` and shown in Admin → Evaluations. See [docs/evaluation.md](docs/evaluation.md).

## Configuration

All configuration is via environment variables (see `.env.example`). The API refuses to start without MongoDB and logs explicit warnings for missing `GEMINI_API_KEY` (AI endpoints return 503 with a clear message), unreachable Qdrant, dev auth mode and empty `ADMIN_EMAILS`. `GET /api/health` reports startup warnings.

## Deployment

- **API:** `backend/Dockerfile` (includes Tesseract). Run `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `STORAGE_DIR` to a persistent disk (uploaded PDFs and extracted figures live there).
- **Worker:** same image, command `celery -A app.workers.celery_app worker`. Or omit and set `JOB_BACKEND=inline` for a single-process deployment.
- **Data:** MongoDB Atlas, Qdrant Cloud (`QDRANT_URL` + `QDRANT_API_KEY`), Redis (Upstash/Render).
- **Frontend:** `npm run build` → static `dist/` on Vercel/Netlify with `VITE_API_URL=https://<api-host>`; set `FRONTEND_ORIGIN` on the API to that origin.

## Known limitations

- Tutor responses are not streamed (single structured JSON response, so citations and visuals can be validated before display).
- Concept extraction runs once per material; concepts are not merged across materials by meaning, only by exact name.
- Image captions come from nearby page text, not from a vision model, so figure matching is heuristic.
- Cost figures are estimates from published per-token prices.
- Built and reviewed as source code without executing the full stack end-to-end in the authoring environment; expect small integration fixes on first run.
