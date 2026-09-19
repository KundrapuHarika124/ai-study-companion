# AI design

All model access goes through `app/services/llm.py`. One provider (Google Gemini, `GEMINI_MODEL`, default `gemini-2.0-flash`), local embeddings (`sentence-transformers/all-MiniLM-L6-v2`, 384-d, cosine). No AI call is made without a project context and an authenticated user.

## Principles

1. **Grounded by construction.** The Tutor only sees chunks retrieved for this user + project. Citations are assembled by the server from the retrieved set; the model returns chunk ids and any id it did not receive is dropped. If it claims `sufficient` but cites nothing, the top evidence it was shown is cited.
2. **Structured outputs everywhere.** Every generation asks for JSON (`response_mime_type=application/json`), is parsed, validated with a pydantic schema, and repaired once on failure. Invalid output → 503 with a clear message, never a half-rendered answer.
3. **Data is not instructions.** Every prompt includes `DATA_GUARD` and wraps material text, conversation history and learner answers in `<data>` blocks declared as untrusted. Tests assert the guard is present in all system prompts; the evaluation suite includes injection cases.
4. **Honest under uncertainty.** Retrieval below `RETRIEVAL_MIN_SCORE` (default 0.30) short-circuits to an explicit "not covered by your material" reply without spending a model call; the model can also declare insufficiency on the evidence it saw, which clears citations.
5. **Observable and bounded.** Timeouts (`AI_TIMEOUT_SECONDS`), retries on 429/503/timeout, and an `ai_runs` row for every call with latency, tokens and estimated cost.

## Tutor pipeline (`services/tutor.py`)

1. Persist the user message; title the conversation from the first message.
2. Context: last 6 messages (not the whole history) and a task-relevant slice of learner context (goal, weak concepts, repeated mistakes, recent topics). For follow-up actions the retrieval query combines the previous user question with the action.
3. Retrieve top-8 text chunks (Qdrant, project filter). Sufficiency pre-check.
4. Prompt = task instruction for the action (`ask`, `explain_simpler`, `example`, `hint`, `visual`, `summarize`, `test_me`) + learner context + `<data>` (history, message, evidence chunks with ids and page labels).
5. Model returns `TutorLLMOutput {answer, sufficient, used_chunk_ids, concept, follow_ups, visual}`.
6. Server builds citations (`Title — Page N`, snippet, material id) from valid chunk ids, deduplicated by page.
7. Visual decision (`services/visuals.py`), see below.
8. Persist assistant message; note the concept in learner context; emit `tutor_interaction` with sufficiency, citation count and visual source.

### Visual learning

Priority order, decided per answer:

1. A figure extracted from the learner's PDF on (or adjacent to) a cited page → shown with "From your material (cited page)" and a page link.
2. A semantically similar indexed figure anywhere in the project (figure captions are embedded alongside text chunks) when similarity ≥ 0.45.
3. A generated visual. The model never emits markup; it emits a small typed spec (`AIVisualSpec`: sequence, layers, steps, array, network, curve, table_relation, tree) which a deterministic server-side renderer turns into escaped SVG, labelled "AI-generated educational visual".
4. None. The system prompt instructs the model to request a visual only when it aids understanding of a process, structure, sequence or relationship.

The learner can force option 3/1 with the "Show me a visual" action.

## Concept extraction (`services/documents.py`)

A 9k-character sample across pages plus headings is sent once per material; the model returns 6–14 specific, quizzable concepts with keywords. Chunks and figures are tagged by keyword match so mastery, recommendations and quiz grounding can reference material sections. Without an API key, headings are used as concepts so processing still completes.

## Assessment (`services/assessment.py`, `services/quiz.py`)

**Generation** is grounded in the top-5 chunks for the concept, with difficulty guidance (easy = recall, medium = explain/compare, hard = apply/analyze) and a list of earlier questions to avoid. MCQs are validated (≥2 options, valid correct index).

**Adaptive policy** (unit-tested):
- concept priority = `0.45·(1−mastery) + 0.25·recent mistake rate + 0.15·staleness + 0.15·[no evidence] − 0.35·[asked this session]`, focus concept overrides;
- difficulty band from mastery (<0.4 easy, <0.7 medium, else hard), shifted one level only after two consecutive consistent results — a single wrong answer does not drop the band, and "correct → hard" is not the rule;
- question type: open-ended every third question or when hard and mastery ≥ 0.6.

**Grading**: MCQ deterministically; open answers via a rubric prompt returning `score, understood, correct[], missing[], incorrect[], reasoning_quality, feedback`. The UI shows all of it.

## Mastery (`services/mastery.py`)

`new = old + α·(score − old)` with prior 0.5 and `α = max(weight, 1/(n+1))`, weight by difficulty (easy .15 / medium .25 / hard .35), +.05 for open-ended, +.10 for a wrong easy answer, +.05 for a correct hard answer. So early evidence moves the estimate a lot, later evidence refines it; hard/open evidence is worth more. Every update is written to `mastery_history` and emitted as `mastery_updated`.

## Growth (`services/growth.py`)

Per concept over the window: <2 evidence points → `insufficient_evidence`; Δ ≥ +0.08 → `improving`; Δ ≤ −0.06 or current < 0.5 → `attention`; else `stable`. Session averages are also returned for a performance line.

## Recommendations (`services/recommendations.py`)

Evidence assembled from mastery rows, recent wrong answers, repeated-mistake patterns, materials (with ids/pages and the chunk covering the weakest concept), previous recommendations and the learning goal. The model returns one action (`quiz|tutor|material|review`) with concept, optional material/page and a rationale; material ids not in the project are discarded. A deterministic fallback produces an evidence-based recommendation when the model is unavailable. Generation is idempotent per trigger (e.g. per quiz session) and supersedes the previous active recommendation.

## Learner context (`services/learner_context.py`)

Stored per project (strengths, weaknesses, repeated mistakes, recent topics). `compose(task)` returns only what the task needs: the Tutor gets goal + weak/strong concepts + repeated mistakes + recent topics; quiz generation gets goal + weak concepts; recommendations get the full evidence set. The whole history is never pasted into a prompt.

## Cost & latency

Typical Tutor answer: ~2.5–4k input tokens (8 chunks + context), ~300–600 output; on `gemini-2.0-flash` ≈ $0.0005–0.001 per answer. Question generation ≈ $0.0003, open grading ≈ $0.0002, concept extraction ≈ $0.001 per material. Embeddings are local (no cost). Latency is dominated by the model call (typically 1.5–5 s); retrieval is ~50–150 ms.
