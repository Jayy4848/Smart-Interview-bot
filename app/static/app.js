let resumeId = null;
let sessionId = null;
let currentQuestionId = null;
let askedIndex = null;

const $ = (id) => document.getElementById(id);

function setStatus(el, msg) {
  el.textContent = msg;
}

function listToUl(ul, items) {
  ul.innerHTML = "";
  (items || []).forEach((x) => {
    const li = document.createElement("li");
    li.textContent = x;
    ul.appendChild(li);
  });
}

function setQuestion(q) {
  currentQuestionId = q.question_id;
  askedIndex = q.index;
  $("questionText").textContent = q.question;
  $("qCategory").textContent = q.category;
  $("qDifficulty").textContent = q.difficulty;
  $("qIndex").textContent = `Q ${q.index + 1}`;
  $("submitTextBtn").disabled = false;
  $("submitAudioBtn").disabled = false;
  $("nextBtn").disabled = true;
}

function resetEvaluation() {
  $("latestScore").textContent = "—";
  $("breakdown").textContent = "relevance — • depth — • clarity — • evidence —";
  listToUl($("strengths"), []);
  listToUl($("improvements"), []);
  $("transcriptBox").hidden = true;
  $("transcript").textContent = "";
}

async function refreshSession() {
  if (!sessionId) return;
  const r = await fetch(`/api/sessions/${sessionId}`);
  const s = await r.json();
  $("avgScore").textContent = s.average_score ? s.average_score.toFixed(1) : "0.0";
  $("askedCount").textContent = `asked ${s.asked} • total score ${s.total_score}`;
}

async function uploadResume() {
  const file = $("resumeFile").files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("file", file);
  setStatus($("resumeStatus"), "Uploading and extracting text...");
  const r = await fetch("/api/resume", { method: "POST", body: fd });
  const data = await r.json();
  if (!r.ok) {
    setStatus($("resumeStatus"), `Error: ${data.detail || "upload failed"}`);
    return;
  }
  resumeId = data.resume_id;
  setStatus($("resumeStatus"), `Uploaded: ${data.filename} • extracted ${data.extracted_chars} chars • resume_id=${resumeId}`);
  $("startBtn").disabled = false;
  setStatus($("sessionStatus"), "Ready to start.");
}

async function startSession() {
  if (!resumeId) return;
  const focus = $("focusAreas").value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const payload = {
    resume_id: resumeId,
    target_role: $("targetRole").value || "Software Engineer",
    seniority: $("seniority").value,
    focus_areas: focus,
    max_questions: Number($("maxQuestions").value || 8),
  };

  setStatus($("sessionStatus"), "Creating session...");
  const r = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await r.json();
  if (!r.ok) {
    setStatus($("sessionStatus"), `Error: ${data.detail || "could not create session"}`);
    return;
  }
  sessionId = data.session_id;
  setStatus($("sessionStatus"), `Session started: ${sessionId}`);
  $("submitTextBtn").disabled = true;
  $("submitAudioBtn").disabled = true;
  $("nextBtn").disabled = true;
  resetEvaluation();
  await nextQuestion();
  await refreshSession();
}

async function nextQuestion() {
  if (!sessionId) return;
  resetEvaluation();
  const r = await fetch(`/api/sessions/${sessionId}/next`, { method: "POST" });
  const data = await r.json();
  if (!r.ok) {
    $("questionText").textContent = data.detail || "No more questions.";
    $("submitTextBtn").disabled = true;
    $("submitAudioBtn").disabled = true;
    $("nextBtn").disabled = true;
    return;
  }
  setQuestion(data);
}

function renderEvaluation(ev) {
  $("latestScore").textContent = String(ev.score);
  $("breakdown").textContent = `relevance ${ev.breakdown.relevance} • depth ${ev.breakdown.depth} • clarity ${ev.breakdown.clarity} • evidence ${ev.breakdown.evidence}`;
  listToUl($("strengths"), ev.strengths);
  listToUl($("improvements"), ev.improvements);
  if (ev.transcript) {
    $("transcriptBox").hidden = false;
    $("transcript").textContent = ev.transcript;
  }
  $("nextBtn").disabled = false;
  $("submitTextBtn").disabled = true;
  $("submitAudioBtn").disabled = true;
}

async function submitText() {
  if (!sessionId || !currentQuestionId) return;
  const ans = $("answerText").value.trim();
  if (!ans) return;

  const payload = { question_id: currentQuestionId, answer: ans };
  const r = await fetch(`/api/sessions/${sessionId}/answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await r.json();
  if (!r.ok) {
    alert(data.detail || "submit failed");
    return;
  }
  renderEvaluation(data);
  await refreshSession();
}

async function submitAudio() {
  if (!sessionId || !currentQuestionId) return;
  const file = $("audioFile").files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/api/sessions/${sessionId}/answer-audio?question_id=${encodeURIComponent(currentQuestionId)}`, { method: "POST", body: fd });
  const data = await r.json();
  if (!r.ok) {
    alert(data.detail || "audio submit failed");
    return;
  }
  renderEvaluation(data);
  await refreshSession();
}

$("uploadBtn").addEventListener("click", uploadResume);
$("startBtn").addEventListener("click", startSession);
$("submitTextBtn").addEventListener("click", submitText);
$("submitAudioBtn").addEventListener("click", submitAudio);
$("nextBtn").addEventListener("click", nextQuestion);

// Show providers from server-rendered env isn't available; keep it minimal here.
// If you want, we can add a `/api/meta` endpoint to display provider config.

