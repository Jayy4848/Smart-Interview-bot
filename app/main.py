from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .llm import LLMClient
from .models import (
    AnswerIn,
    EvaluationOut,
    QuestionOut,
    ResumeOut,
    SessionCreateIn,
    SessionOut,
    ScoreBreakdown,
)
from .resume_parser import extract_resume_text_from_bytes
from .store import AnswerEval, MemoryStore, Question
from .stt import STTClient

app = FastAPI(title="Smart AI Interview Bot", version="0.1.0")

settings = get_settings()
store = MemoryStore()
llm = LLMClient(settings=settings)
stt = STTClient(settings=settings)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/meta")
async def meta() -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "stt_provider": settings.stt_provider,
        "stub_mode": settings.llm_provider != "openai",
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (static_dir / "index.html").read_text(encoding="utf-8")


@app.post("/api/resume", response_model=ResumeOut)
async def upload_resume(file: UploadFile = File(...)) -> ResumeOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    content = await file.read()
    try:
        text = extract_resume_text_from_bytes(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not text or len(text) < 50:
        raise HTTPException(status_code=400, detail="Could not extract enough text from resume.")
    resume = store.create_resume(filename=file.filename, text=text)
    return ResumeOut(resume_id=resume.resume_id, filename=resume.filename, extracted_chars=len(resume.text))


@app.post("/api/sessions", response_model=SessionOut)
async def create_session(payload: SessionCreateIn) -> SessionOut:
    if payload.resume_id not in store.resumes:
        raise HTTPException(status_code=404, detail="Resume not found.")
    s = store.create_session(
        resume_id=payload.resume_id,
        target_role=payload.target_role,
        seniority=payload.seniority,
        focus_areas=payload.focus_areas,
        max_questions=payload.max_questions,
    )
    return SessionOut(
        session_id=s.session_id,
        resume_id=s.resume_id,
        target_role=s.target_role,
        seniority=s.seniority,
        max_questions=s.max_questions,
        asked=s.asked,
        total_score=s.total_score,
        average_score=s.average_score,
    )


@app.post("/api/sessions/{session_id}/next", response_model=QuestionOut)
async def next_question(session_id: str) -> QuestionOut:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = store.get_session(session_id)
    # Generate questions once per session, lazily.
    if not s.questions:
        resume = store.get_resume(s.resume_id)
        generated = await llm.generate_questions(
            resume_text=resume.text,
            target_role=s.target_role,
            seniority=s.seniority,
            focus_areas=s.focus_areas,
            max_questions=s.max_questions,
        )
        for idx, q in enumerate(generated):
            s.questions.append(
                Question(
                    question_id=f"q_{idx+1}",
                    index=idx,
                    question=q.question,
                    category=q.category,
                    difficulty=q.difficulty,
                )
            )

    # Stop only when answered questions already consumed all available questions.
    if len(s.evaluations) >= len(s.questions):
        raise HTTPException(status_code=400, detail="No more questions in this session.")

    q = s.questions[len(s.evaluations)]
    return QuestionOut(
        question_id=q.question_id,
        index=q.index,
        question=q.question,
        category=q.category,
        difficulty=q.difficulty,  # type: ignore[arg-type]
    )


def _find_question(s, question_id: str) -> Question:
    for q in s.questions:
        if q.question_id == question_id:
            return q
    raise KeyError(question_id)


@app.post("/api/sessions/{session_id}/answer", response_model=EvaluationOut)
async def submit_answer(session_id: str, payload: AnswerIn) -> EvaluationOut:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = store.get_session(session_id)
    resume = store.get_resume(s.resume_id)
    try:
        q = _find_question(s, payload.question_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Question not found.")
    if any(ev.question_id == q.question_id for ev in s.evaluations):
        raise HTTPException(status_code=409, detail="This question was already answered.")

    ev = await llm.evaluate_answer(
        resume_text=resume.text,
        target_role=s.target_role,
        question=q.question,
        answer=payload.answer,
    )
    ae = AnswerEval(
        question_id=q.question_id,
        answer=payload.answer,
        transcript=None,
        score=ev.score,
        breakdown=ev.breakdown,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )
    s.evaluations.append(ae)

    bd = ScoreBreakdown(**ev.breakdown)
    return EvaluationOut(
        question_id=q.question_id,
        transcript=None,
        score=ev.score,
        breakdown=bd,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )


@app.post("/api/sessions/{session_id}/answer-audio", response_model=EvaluationOut)
async def submit_audio_answer(session_id: str, question_id: str, file: UploadFile = File(...)) -> EvaluationOut:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = store.get_session(session_id)
    resume = store.get_resume(s.resume_id)
    try:
        q = _find_question(s, question_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Question not found.")
    if any(ev.question_id == q.question_id for ev in s.evaluations):
        raise HTTPException(status_code=409, detail="This question was already answered.")

    audio_bytes = await file.read()
    transcript = await stt.transcribe_bytes(audio_bytes, file.filename or "audio")

    ev = await llm.evaluate_answer(
        resume_text=resume.text,
        target_role=s.target_role,
        question=q.question,
        answer=transcript,
    )
    ae = AnswerEval(
        question_id=q.question_id,
        answer=transcript,
        transcript=transcript,
        score=ev.score,
        breakdown=ev.breakdown,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )
    s.evaluations.append(ae)

    bd = ScoreBreakdown(**ev.breakdown)
    return EvaluationOut(
        question_id=q.question_id,
        transcript=transcript,
        score=ev.score,
        breakdown=bd,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )


@app.post("/api/sessions/{session_id}/answer-video", response_model=EvaluationOut)
async def submit_video_answer(session_id: str, question_id: str, file: UploadFile = File(...)) -> EvaluationOut:
    """Accept a video recording (webm/mp4) and transcribe the audio track via STT."""
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = store.get_session(session_id)
    resume = store.get_resume(s.resume_id)
    try:
        q = _find_question(s, question_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Question not found.")
    if any(ev.question_id == q.question_id for ev in s.evaluations):
        raise HTTPException(status_code=409, detail="This question was already answered.")

    video_bytes = await file.read()
    # Reuse STT — OpenAI Whisper accepts webm/mp4 directly
    transcript = await stt.transcribe_bytes(video_bytes, file.filename or "video.webm")

    ev = await llm.evaluate_answer(
        resume_text=resume.text,
        target_role=s.target_role,
        question=q.question,
        answer=transcript,
    )
    ae = AnswerEval(
        question_id=q.question_id,
        answer=transcript,
        transcript=transcript,
        score=ev.score,
        breakdown=ev.breakdown,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )
    s.evaluations.append(ae)

    bd = ScoreBreakdown(**ev.breakdown)
    return EvaluationOut(
        question_id=q.question_id,
        transcript=transcript,
        score=ev.score,
        breakdown=bd,
        strengths=ev.strengths,
        improvements=ev.improvements,
        suggested_answer=ev.suggested_answer,
    )


@app.get("/api/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str) -> SessionOut:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = store.get_session(session_id)
    return SessionOut(
        session_id=s.session_id,
        resume_id=s.resume_id,
        target_role=s.target_role,
        seniority=s.seniority,
        max_questions=s.max_questions,
        asked=s.asked,
        total_score=s.total_score,
        average_score=s.average_score,
    )

