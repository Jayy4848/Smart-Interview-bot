# Smart AI Interview Bot (MVP)

An AI-powered interview practice app that:

- Generates interview questions based on your resume
- Accepts answers via **text** or **voice** (speech-to-text)
- Evaluates answers and provides **feedback + scoring**

## Quickstart (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Configuration

Set values in `.env` (see `.env.example`):

- `LLM_PROVIDER`: `openai` or `stub`
- `OPENAI_API_KEY`: required if `LLM_PROVIDER=openai`

Optional speech-to-text:

- `STT_PROVIDER`: `openai` or `stub`

## What’s implemented

- Resume upload (`.pdf`, `.docx`, `.txt`)
- Session-based interview flow
- Question generation from resume + target role
- Answer evaluation with a **scoring system** (0–100) + per-dimension rubric
- Voice answer upload (`.wav/.mp3/.m4a`) → STT (OpenAI if configured)

## API (high level)

- `POST /api/resume` upload resume, returns `resume_id`
- `POST /api/sessions` start interview, returns `session_id`
- `POST /api/sessions/{session_id}/next` get next question
- `POST /api/sessions/{session_id}/answer` submit text answer, returns evaluation + score
- `POST /api/sessions/{session_id}/answer-audio` submit audio answer, returns transcript + evaluation + score

## Next upgrades (recommended)

- Persist sessions in SQLite (instead of in-memory)
- Add question difficulty calibration over time
- Add “red flags” detection (fabrication / contradictions vs resume)
- Add per-skill analytics dashboard

