# Evaluation

## What is evaluated

| Property | How |
|---|---|
| Grounding | Supported questions must produce `sufficient=true` with ≥1 citation, and mention expected terms. |
| Unsupported handling | Off-topic questions must produce `sufficient=false` with zero citations and the honest "not covered" reply. |
| Citation integrity | Unit test: chunk ids not in the retrieved set are dropped; insufficient answers carry no citations. |
| Isolation | The same question asked in a project without the material must be insufficient (eval) and cross-user access must 404 (tests). |
| Prompt injection | Injection-style questions must not leak system prompt fragments or schema keys, and are expected to be treated as unsupported. |
| Visual selection | Cases that ask for a process explanation are expected to return a visual (material figure or generated). |
| Adaptive policy | Unit tests on concept priority, difficulty band movement and question-type mixing. |
| Mastery / growth | Unit tests on monotonicity, bounds, evidence weighting and status classification. |
| Jobs | Unit tests on idempotent enqueue, retry with backoff, terminal failure hook, no re-run of completed jobs. |

## Running

Unit and API tests (no external services):

```bash
cd backend && pytest -q
```

Live evaluation against a running stack (real retrieval + model):

```bash
cd backend
cp evals/cases.example.json evals/cases.json    # set project_id (with a processed PDF), user_email (dev mode) or API_TOKEN
python -m evals.run_evals evals/cases.json --api http://localhost:8000
```

Each run stores a document in `ai_evaluations` (suite, model, embedding model, retrieval threshold, per-case pass/fail with notes, sufficiency, citation count, visual source, latency, answer preview). Admin → Evaluations lists them so prompt, model or threshold changes can be compared across runs.

## Observability used in evaluation

- `ai_runs`: latency, tokens, estimated cost, retrieval and visual-retrieval counts, failures and retry attempts per feature. Admin → AI runs shows recent and slowest runs; Analytics shows per-feature totals.
- `activity_events.tutor_interaction`: records `sufficient`, `citations` and `visual` for every answer, so the insufficient rate and visual usage can be tracked without re-running anything.

## Known gaps

- The live suite judges with simple rules (terms present, sufficiency flag, citation count). A model-as-judge pass for answer quality was deliberately not added to keep the evaluation deterministic and cheap.
- Retrieval quality depends on the small local embedding model; the threshold `RETRIEVAL_MIN_SCORE` was chosen conservatively (0.30) and should be tuned per corpus using the stored evaluation runs.
- Open-ended grading consistency has not been measured against human grades.
