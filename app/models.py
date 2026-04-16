from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResumeOut(BaseModel):
    resume_id: str
    filename: str
    extracted_chars: int


class SessionCreateIn(BaseModel):
    resume_id: str
    target_role: str = Field(default="Software Engineer", max_length=120)
    seniority: Literal["intern", "junior", "mid", "senior", "staff"] = "mid"
    focus_areas: list[str] = Field(default_factory=list, description="e.g., ['backend', 'system design']")
    max_questions: int = Field(default=8, ge=3, le=20)


class SessionOut(BaseModel):
    session_id: str
    resume_id: str
    target_role: str
    seniority: str
    max_questions: int
    asked: int
    total_score: int
    average_score: float


class QuestionOut(BaseModel):
    question_id: str
    index: int
    question: str
    category: str
    difficulty: Literal["easy", "medium", "hard"]


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=6000)


class ScoreBreakdown(BaseModel):
    relevance: int = Field(ge=0, le=25)
    depth: int = Field(ge=0, le=25)
    clarity: int = Field(ge=0, le=25)
    evidence: int = Field(ge=0, le=25)

    @property
    def total(self) -> int:
        return int(self.relevance + self.depth + self.clarity + self.evidence)


class EvaluationOut(BaseModel):
    question_id: str
    transcript: str | None = None
    score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    strengths: list[str]
    improvements: list[str]
    suggested_answer: str | None = None

