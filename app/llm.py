from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Any, Literal

from .config import Settings


QuestionDifficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class GeneratedQuestion:
    question: str
    category: str
    difficulty: QuestionDifficulty


@dataclass(frozen=True)
class Evaluation:
    score: int
    breakdown: dict[str, int]
    strengths: list[str]
    improvements: list[str]
    suggested_answer: str | None


def _clamp_int(x: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return default
    return max(lo, min(hi, v))


def _top_keywords(text: str, k: int = 10) -> list[str]:
    text = re.sub(r"[^a-zA-Z0-9+#.\s]", " ", text)
    toks = [t.lower() for t in text.split() if 2 <= len(t) <= 24]
    stop = {
        "and",
        "the",
        "a",
        "to",
        "of",
        "in",
        "for",
        "with",
        "on",
        "at",
        "is",
        "are",
        "as",
        "from",
        "an",
        "by",
        "or",
        "be",
        "this",
        "that",
        "it",
        "i",
        "we",
        "you",
        "they",
        "my",
        "our",
        "your",
        "their",
    }
    freq: dict[str, int] = {}
    for t in toks:
        if t in stop:
            continue
        freq[t] = freq.get(t, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_questions(
        self,
        *,
        resume_text: str,
        target_role: str,
        seniority: str,
        focus_areas: list[str],
        max_questions: int,
    ) -> list[GeneratedQuestion]:
        if self.settings.llm_provider == "openai":
            return await self._generate_questions_openai(
                resume_text=resume_text,
                target_role=target_role,
                seniority=seniority,
                focus_areas=focus_areas,
                max_questions=max_questions,
            )
        return self._generate_questions_stub(
            resume_text=resume_text,
            target_role=target_role,
            seniority=seniority,
            focus_areas=focus_areas,
            max_questions=max_questions,
        )

    async def evaluate_answer(
        self,
        *,
        resume_text: str,
        target_role: str,
        question: str,
        answer: str,
    ) -> Evaluation:
        if self.settings.llm_provider == "openai":
            return await self._evaluate_answer_openai(
                resume_text=resume_text,
                target_role=target_role,
                question=question,
                answer=answer,
            )
        return self._evaluate_answer_stub(
            resume_text=resume_text,
            target_role=target_role,
            question=question,
            answer=answer,
        )

    def _generate_questions_stub(
        self,
        *,
        resume_text: str,
        target_role: str,
        seniority: str,
        focus_areas: list[str],
        max_questions: int,
    ) -> list[GeneratedQuestion]:
        kws = _top_keywords(resume_text, k=12)
        focus = ", ".join(focus_areas) if focus_areas else "core engineering"
        base = [
            GeneratedQuestion(
                question=f"Walk me through a project on your resume where you used {k}. What was the impact and what trade-offs did you make?",
                category="resume-deep-dive",
                difficulty="medium",
            )
            for k in kws[: max(3, min(6, len(kws)))]
        ]
        extras = [
            GeneratedQuestion(
                question=f"For a {seniority} {target_role} focused on {focus}, describe how you would design a production-ready feature end-to-end (requirements → rollout).",
                category="system-design",
                difficulty="hard" if seniority in {"senior", "staff"} else "medium",
            ),
            GeneratedQuestion(
                question="Tell me about a time you had a bug in production. How did you detect it, debug it, and prevent recurrence?",
                category="behavioral",
                difficulty="easy",
            ),
            GeneratedQuestion(
                question="Pick one achievement from your resume. What metric improved, and what did you do personally to move it?",
                category="impact",
                difficulty="easy",
            ),
        ]
        qs = base + extras
        random.shuffle(qs)
        return qs[:max_questions]

    def _evaluate_answer_stub(
        self,
        *,
        resume_text: str,
        target_role: str,
        question: str,
        answer: str,
    ) -> Evaluation:
        a = answer.strip()
        length = len(a)
        has_numbers = bool(re.search(r"\b\d+(\.\d+)?%?\b", a))
        has_structure = any(x in a.lower() for x in ["first", "second", "then", "because", "trade-off", "tradeoff"])
        resume_kws = set(_top_keywords(resume_text, k=20))
        overlap = sum(1 for t in _top_keywords(a, k=20) if t in resume_kws)

        relevance = _clamp_int(8 + overlap, 0, 25, 10)
        depth = _clamp_int(6 + (10 if length > 600 else 3 if length > 250 else 0), 0, 25, 10)
        clarity = _clamp_int(10 + (6 if has_structure else 0) - (4 if length > 3500 else 0), 0, 25, 12)
        evidence = _clamp_int(6 + (10 if has_numbers else 0), 0, 25, 10)

        total = relevance + depth + clarity + evidence
        strengths: list[str] = []
        improvements: list[str] = []

        if relevance >= 16:
            strengths.append("Good alignment with your resume and the question.")
        else:
            improvements.append("Tie your answer more explicitly to the question and your resume experience.")

        if evidence >= 16:
            strengths.append("You used concrete evidence/metrics, which increases credibility.")
        else:
            improvements.append("Add measurable outcomes (latency, cost, conversion, incidents, time saved).")

        if clarity >= 16:
            strengths.append("Clear structure and easy to follow.")
        else:
            improvements.append("Use a clearer structure (Situation → Task → Action → Result) and call out trade-offs.")

        if depth >= 16:
            strengths.append("Good technical depth and specificity.")
        else:
            improvements.append("Add deeper technical details: constraints, alternatives considered, and why you chose the final approach.")

        suggested = (
            "A strong answer usually includes: context, your specific role, key decisions + trade-offs, execution details, and measurable impact."
        )

        return Evaluation(
            score=int(max(0, min(100, total * 1.0))),
            breakdown={"relevance": relevance, "depth": depth, "clarity": clarity, "evidence": evidence},
            strengths=strengths[:4],
            improvements=improvements[:4],
            suggested_answer=suggested,
        )

    async def _generate_questions_openai(
        self,
        *,
        resume_text: str,
        target_role: str,
        seniority: str,
        focus_areas: list[str],
        max_questions: int,
    ) -> list[GeneratedQuestion]:
        if not self.settings.openai_api_key:
            return self._generate_questions_stub(
                resume_text=resume_text,
                target_role=target_role,
                seniority=seniority,
                focus_areas=focus_areas,
                max_questions=max_questions,
            )

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        focus = ", ".join(focus_areas) if focus_areas else "core engineering"

        system = (
            "You are an expert technical interviewer. Generate targeted interview questions based on the candidate resume."
        )
        user = f"""
Target role: {target_role}
Seniority: {seniority}
Focus areas: {focus}
Max questions: {max_questions}

Resume:
{resume_text[:12000]}

Return STRICT JSON array with objects:
{{"question": str, "category": str, "difficulty": "easy"|"medium"|"hard"}}
Questions must reference resume details when possible and avoid duplicates.
"""

        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
        )
        content = (resp.choices[0].message.content or "").strip()

        try:
            raw = json.loads(content)
        except Exception:
            return self._generate_questions_stub(
                resume_text=resume_text,
                target_role=target_role,
                seniority=seniority,
                focus_areas=focus_areas,
                max_questions=max_questions,
            )

        out: list[GeneratedQuestion] = []
        for item in raw[:max_questions]:
            if not isinstance(item, dict):
                continue
            q = str(item.get("question", "")).strip()
            if not q:
                continue
            out.append(
                GeneratedQuestion(
                    question=q,
                    category=str(item.get("category", "general")).strip() or "general",
                    difficulty=item.get("difficulty", "medium"),
                )
            )
        return out[:max_questions] or self._generate_questions_stub(
            resume_text=resume_text,
            target_role=target_role,
            seniority=seniority,
            focus_areas=focus_areas,
            max_questions=max_questions,
        )

    async def _evaluate_answer_openai(
        self,
        *,
        resume_text: str,
        target_role: str,
        question: str,
        answer: str,
    ) -> Evaluation:
        if not self.settings.openai_api_key:
            return self._evaluate_answer_stub(
                resume_text=resume_text, target_role=target_role, question=question, answer=answer
            )

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        system = "You are an expert interviewer and coach. Evaluate answers with an explicit rubric."
        user = f"""
Role: {target_role}

Resume (context):
{resume_text[:8000]}

Question:
{question}

Answer:
{answer}

Return STRICT JSON object:
{{
  "breakdown": {{"relevance":0-25,"depth":0-25,"clarity":0-25,"evidence":0-25}},
  "strengths": [..max 4..],
  "improvements": [..max 4..],
  "suggested_answer": "short improved answer (optional)"
}}
Also ensure total score is sum of the four categories (0-100).
"""

        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()

        try:
            raw = json.loads(content)
        except Exception:
            return self._evaluate_answer_stub(
                resume_text=resume_text, target_role=target_role, question=question, answer=answer
            )

        bd = raw.get("breakdown", {}) if isinstance(raw, dict) else {}
        relevance = _clamp_int(bd.get("relevance"), 0, 25, 10)
        depth = _clamp_int(bd.get("depth"), 0, 25, 10)
        clarity = _clamp_int(bd.get("clarity"), 0, 25, 10)
        evidence = _clamp_int(bd.get("evidence"), 0, 25, 10)

        return Evaluation(
            score=int(max(0, min(100, relevance + depth + clarity + evidence))),
            breakdown={"relevance": relevance, "depth": depth, "clarity": clarity, "evidence": evidence},
            strengths=[str(x) for x in (raw.get("strengths") or [])][:4],
            improvements=[str(x) for x in (raw.get("improvements") or [])][:4],
            suggested_answer=(str(raw.get("suggested_answer")).strip() if raw.get("suggested_answer") else None),
        )

