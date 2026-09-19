"""Question generation and grading (MCQ deterministic, open-ended rubric-graded via structured LLM output)."""
from __future__ import annotations
from app.schemas import GeneratedQuestion, OpenGrade
from app.services import retrieval
from app.services.llm import llm, DATA_GUARD

GEN_SYSTEM = ("You write high-quality assessment questions strictly grounded in the provided study material. " + DATA_GUARD +
              " Return ONLY JSON: {type:'mcq'|'open', question, options (4 for mcq, else []), correct_index (mcq only, 0-3), "
              "reference_answer (open only: model answer), explanation (why the answer is right), key_points (3-5 concepts a good answer covers)}.")

GRADE_SYSTEM = ("You are a fair, specific grader of a learner's open-ended answer. Judge understanding, accuracy, relevance, key concepts covered, "
                "missing concepts, incorrect statements and reasoning quality, using the reference answer and evidence as the standard. " + DATA_GUARD +
                " Return ONLY JSON: {score (0-1), understood (what the learner clearly understood), correct[], missing[], incorrect[], "
                "reasoning_quality (one sentence), feedback (2-4 sentences: what was right, what was missing, how to improve)}.")


async def generate_question(db, *, user: dict, project: dict, concept: str, difficulty: str, qtype: str, avoid: list[str]) -> tuple[GeneratedQuestion, list[dict]]:
    evidence = await retrieval.retrieve(user_id=user["id"], project_id=project["_id"], query=concept, limit=5)
    ev_block = "\n\n".join(f"<chunk source=\"{e.label}\">\n{e.text}\n</chunk>" for e in evidence)
    avoid_block = "\n".join(f"- {a}" for a in avoid[-8:]) or "(none)"
    prompt = (f"Write ONE {difficulty} {'multiple-choice' if qtype == 'mcq' else 'open-ended'} question about the concept '{concept}'.\n"
              f"Difficulty guide: easy=recall/definition, medium=explain/compare, hard=apply/analyze a scenario.\n"
              f"Do not repeat these earlier questions:\n{avoid_block}\n\n<data>\nLEARNING GOAL: {project.get('learning_goal','')}\n\nMATERIAL:\n{ev_block or '(no material retrieved: write a general question on the concept)'}\n</data>")
    q = await llm.generate_json(prompt, GeneratedQuestion, system=GEN_SYSTEM, feature="quiz_generation", user_id=user["id"],
                                project_id=project["_id"], db=db, temperature=0.6, retrieval_count=len(evidence))
    if q.type == "mcq":
        if len(q.options) < 2 or q.correct_index is None or not (0 <= q.correct_index < len(q.options)):
            raise ValueError("invalid MCQ from model")
    q.type = qtype if qtype in ("mcq", "open") else q.type
    sources = [{"material_id": e.material_id, "page": e.page, "label": e.label} for e in evidence[:2]]
    return q, sources


async def grade_open(db, *, user: dict, project: dict, question: dict, answer: str) -> OpenGrade:
    if len(answer.strip()) < 3:
        return OpenGrade(score=0.0, understood="", correct=[], missing=question.get("key_points", []), incorrect=[],
                         reasoning_quality="No answer provided.", feedback="You did not provide an answer. Try to write what you know, even partially.")
    prompt = (f"<data>\nQUESTION: {question['question']}\nREFERENCE ANSWER: {question.get('reference_answer','')}\nKEY POINTS: {question.get('key_points', [])}\n\n"
              f"LEARNER ANSWER:\n{answer}\n</data>\nGrade it now.")
    return await llm.generate_json(prompt, OpenGrade, system=GRADE_SYSTEM, feature="assessment_grading", user_id=user["id"],
                                   project_id=project["_id"], db=db, temperature=0.1)
