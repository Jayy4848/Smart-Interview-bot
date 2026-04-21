from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10)}"


@dataclass
class Resume:
    resume_id: str
    filename: str
    text: str
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class Question:
    question_id: str
    index: int
    question: str
    category: str
    difficulty: str


@dataclass
class AnswerEval:
    question_id: str
    answer: str
    transcript: str | None
    score: int
    breakdown: dict[str, int]
    strengths: list[str]
    improvements: list[str]
    suggested_answer: str | None
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class Session:
    session_id: str
    resume_id: str
    target_role: str
    seniority: str
    focus_areas: list[str]
    max_questions: int
    questions: list[Question] = field(default_factory=list)
    evaluations: list[AnswerEval] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())

    @property
    def asked(self) -> int:
        # "Asked" in UI should reflect how many questions were answered so far.
        return len(self.evaluations)

    @property
    def total_score(self) -> int:
        return sum(e.score for e in self.evaluations)

    @property
    def average_score(self) -> float:
        if not self.evaluations:
            return 0.0
        return self.total_score / len(self.evaluations)


class MemoryStore:
    def __init__(self) -> None:
        self.resumes: dict[str, Resume] = {}
        self.sessions: dict[str, Session] = {}

    def create_resume(self, *, filename: str, text: str) -> Resume:
        resume = Resume(resume_id=_id("resume"), filename=filename, text=text)
        self.resumes[resume.resume_id] = resume
        return resume

    def get_resume(self, resume_id: str) -> Resume:
        return self.resumes[resume_id]

    def create_session(
        self,
        *,
        resume_id: str,
        target_role: str,
        seniority: str,
        focus_areas: list[str],
        max_questions: int,
    ) -> Session:
        s = Session(
            session_id=_id("sess"),
            resume_id=resume_id,
            target_role=target_role,
            seniority=seniority,
            focus_areas=focus_areas,
            max_questions=max_questions,
        )
        self.sessions[s.session_id] = s
        return s

    def get_session(self, session_id: str) -> Session:
        return self.sessions[session_id]

