"""Pydantic request/response schemas."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    color: str = Field(default="#2F5D62", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str = Field(default="book", max_length=32)


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=32)


class ProjectCreate(BaseModel):
    space_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    learning_goal: str = Field(default="", max_length=1000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    learning_goal: str | None = Field(default=None, max_length=1000)


TutorAction = Literal["ask", "explain_simpler", "example", "hint", "visual", "summarize", "test_me"]


class TutorAsk(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    action: TutorAction = "ask"


class QuizStart(BaseModel):
    length: int = Field(default=5, ge=1, le=15)
    focus_concept: str | None = None


class QuizAnswer(BaseModel):
    question_id: str
    answer: str = Field(max_length=4000)


class ConceptOut(BaseModel):
    name: str
    description: str = ""


class AIVisualSpec(BaseModel):
    """Structured visual request produced by the model. Validated before rendering."""
    kind: Literal["none", "sequence", "layers", "steps", "array", "network", "curve", "table_relation", "tree"] = "none"
    title: str = ""
    actors: list[str] = []
    messages: list[dict[str, Any]] = []
    items: list[str] = []
    values: list[str] = []
    highlights: list[int] = []
    layer_sizes: list[int] = []
    left: list[str] = []
    right: list[str] = []
    children: dict[str, list[str]] = {}
    root: str = ""


class TutorLLMOutput(BaseModel):
    answer: str
    sufficient: bool = True
    used_chunk_ids: list[str] = []
    concept: str = ""
    follow_ups: list[str] = []
    visual: AIVisualSpec = AIVisualSpec()


class GeneratedQuestion(BaseModel):
    type: Literal["mcq", "open"]
    question: str
    options: list[str] = []
    correct_index: int | None = None
    reference_answer: str = ""
    explanation: str = ""
    key_points: list[str] = []


class OpenGrade(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    understood: str = ""
    correct: list[str] = []
    missing: list[str] = []
    incorrect: list[str] = []
    reasoning_quality: str = ""
    feedback: str = ""


class RecommendationOut(BaseModel):
    title: str
    body: str
    action_type: Literal["quiz", "tutor", "material", "review"] = "review"
    concept: str = ""
    material_id: str | None = None
    page: int | None = None
    rationale: str = ""
