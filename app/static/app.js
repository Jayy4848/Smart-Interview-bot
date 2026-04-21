// ─── State ────────────────────────────────────────────────────────────────────
let resumeId = null;
let sessionId = null;
let currentQuestionId = null;
let currentCategory = null;

// Video recording state
let mediaStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;

// ─── Helpers ──────────────────────────────────────────────────────────────────
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

/**
 * Coding / programming categories that should default to text mode.
 * Everything else defaults to video.
 */
const CODING_CATEGORIES = new Set([
  "coding",
  "programming",
  "algorithm",
  "algorithms",
  "data-structures",
  "data structures",
  "code",
  "technical-coding",
  "problem-solving",
  "leetcode",
  "implementation",
]);

function isCodingQuestion(category) {
  if (!category) return false;
  return CODING_CATEGORIES.has(category.toLowerCase().trim());
}

// ─── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  ["video", "text", "audio"].forEach((t) => {
    $(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.toggle("active", t === tab);
    $(`panel${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.toggle("hidden", t !== tab);
  });

  // Stop camera if leaving video tab
  if (tab !== "video") {
    stopCamera();
  }
}

function autoSelectTab(category) {
  if (isCodingQuestion(category)) {
    switchTab("text");
    const badge = $("answerModeBadge");
    badge.textContent = "⌨️ Text mode (coding)";
    badge.hidden = false;
  } else {
    switchTab("video");
    const badge = $("answerModeBadge");
    badge.textContent = "🎥 Video mode";
    badge.hidden = false;
    // Auto-start camera for video questions
    startCamera();
  }
}

$("tabVideo").addEventListener("click", () => {
  switchTab("video");
  startCamera();
});
$("tabText").addEventListener("click", () => switchTab("text"));
$("tabAudio").addEventListener("click", () => switchTab("audio"));

// ─── Camera / Recording ────────────────────────────────────────────────────────
async function startCamera() {
  if (mediaStream) return; // already running
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    _attachStreamToPreview();
    $("startVideoBtn").disabled = false;
    $("videoHint").textContent = "Camera ready. Click 'Start recording' when ready.";
  } catch (err) {
    $("videoHint").textContent = `Camera error: ${err.message}. Use audio upload or text instead.`;
    $("videoOverlay").hidden = false;
  }
}

function _attachStreamToPreview() {
  const preview = $("videoPreview");
  preview.srcObject = mediaStream;
  preview.play().catch(() => {});
  $("panelVideo").classList.add("has-live-camera");
  $("videoOverlay").hidden = true;
}

function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  const preview = $("videoPreview");
  preview.srcObject = null;
  $("panelVideo").classList.remove("has-live-camera");
  $("startVideoBtn").disabled = true;
  $("videoOverlay").hidden = false;
}

async function startRecording() {
  if (!mediaStream) await startCamera();
  if (!mediaStream) return;

  // Disable the start button so user can't double-click
  $("startVideoBtn").disabled = true;

  // Run countdown — stream stays live in background
  await countdown(3);

  // Re-attach stream to preview in case it got detached
  _attachStreamToPreview();

  // Reset state
  recordedChunks = [];
  recordedBlob = null;
  $("recordedPreview").hidden = true;
  $("submitVideoBtn").disabled = true;

  const mimeType = getSupportedMimeType();
  try {
    mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : {});
  } catch (e) {
    mediaRecorder = new MediaRecorder(mediaStream);
  }

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordedChunks.push(e.data);
  };
  mediaRecorder.onstop = onRecordingStop;
  mediaRecorder.start(250);

  $("startVideoBtn").hidden = true;
  $("stopVideoBtn").hidden = false;
  $("stopVideoBtn").disabled = false;
  $("recordingIndicator").hidden = false;
  $("videoHint").textContent = "Recording… click Stop when done.";
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  $("stopVideoBtn").hidden = true;
  $("startVideoBtn").hidden = false;
  $("startVideoBtn").disabled = false;
  $("recordingIndicator").hidden = true;
}

function onRecordingStop() {
  const mimeType = (mediaRecorder && mediaRecorder.mimeType) || "video/webm";
  recordedBlob = new Blob(recordedChunks, { type: mimeType });

  const url = URL.createObjectURL(recordedBlob);
  const rv = $("recordedVideo");
  rv.src = url;
  $("recordedPreview").hidden = false;
  $("submitVideoBtn").disabled = false;
  $("videoHint").textContent = "Recording saved. Review it below, then submit or retake.";
}

function retakeRecording() {
  recordedBlob = null;
  recordedChunks = [];
  $("recordedPreview").hidden = true;
  $("submitVideoBtn").disabled = true;
  if (mediaStream) {
    $("startVideoBtn").disabled = false;
    $("videoHint").textContent = "Camera ready. Click 'Start recording' when ready.";
  }
}

function getSupportedMimeType() {
  const types = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ];
  for (const t of types) {
    try {
      if (MediaRecorder.isTypeSupported(t)) return t;
    } catch (_) {}
  }
  return "";
}

// ─── Countdown ─────────────────────────────────────────────────────────────────
function countdown(seconds) {
  return new Promise((resolve) => {
    const overlay = $("countdownOverlay");
    const num = $("countdownNumber");

    const steps = [];
    for (let i = seconds; i >= 1; i--) steps.push(String(i));
    steps.push("GO!");

    // Show overlay
    overlay.classList.add("active");
    let idx = 0;

    function tick() {
      if (idx >= steps.length) {
        // Hide overlay, then resolve so recording starts with clean preview
        overlay.classList.remove("active");
        resolve();
        return;
      }

      const label = steps[idx];
      idx++;

      // Restart CSS animation: kill it, update text, double-rAF to re-enable
      num.style.animation = "none";
      num.textContent = label;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          num.style.animation = "";
          const delay = label === "GO!" ? 600 : 950;
          setTimeout(tick, delay);
        });
      });
    }

    tick();
  });
}

$("startVideoBtn").addEventListener("click", startRecording);
$("stopVideoBtn").addEventListener("click", stopRecording);
$("retakeBtn").addEventListener("click", retakeRecording);

// ─── Question display ──────────────────────────────────────────────────────────
function setQuestion(q) {
  currentQuestionId = q.question_id;
  currentCategory = q.category;

  $("questionText").textContent = q.question;
  $("qCategory").textContent = q.category;
  $("qDifficulty").textContent = q.difficulty;
  $("qIndex").textContent = `Q ${q.index + 1}`;

  // Enable submit buttons
  $("submitTextBtn").disabled = false;
  $("submitAudioBtn").disabled = false;
  $("startVideoBtn").disabled = false;
  $("nextBtn").disabled = true;

  // Reset recorded video
  retakeRecording();

  // Auto-select the right mode
  autoSelectTab(q.category);
}

function resetEvaluation() {
  $("latestScore").textContent = "—";
  $("breakdown").textContent = "relevance — • depth — • clarity — • evidence —";
  listToUl($("strengths"), []);
  listToUl($("improvements"), []);
  $("transcriptBox").hidden = true;
  $("transcript").textContent = "";
}

// ─── API calls ─────────────────────────────────────────────────────────────────
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
  setStatus($("resumeStatus"), "Uploading and extracting text…");
  const r = await fetch("/api/resume", { method: "POST", body: fd });
  const data = await r.json();
  if (!r.ok) {
    setStatus($("resumeStatus"), `Error: ${data.detail || "upload failed"}`);
    return;
  }
  resumeId = data.resume_id;
  setStatus(
    $("resumeStatus"),
    `Uploaded: ${data.filename} • extracted ${data.extracted_chars} chars • resume_id=${resumeId}`
  );
  $("startBtn").disabled = false;
  setStatus($("sessionStatus"), "Ready to start.");
}

async function startSession() {
  if (!resumeId) return;
  const focus = $("focusAreas")
    .value.split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const payload = {
    resume_id: resumeId,
    target_role: $("targetRole").value.trim() || "Software Engineer",
    seniority: $("seniority").value,
    focus_areas: focus,
    max_questions: Math.max(3, Math.min(20, parseInt($("maxQuestions").value, 10) || 8)),
  };

  setStatus($("sessionStatus"), "Creating session…");
  const r = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await r.json();
  if (!r.ok) {
    // Show detailed validation errors if present
    let msg = data.detail || "could not create session";
    if (Array.isArray(data.detail)) {
      msg = data.detail.map((e) => `${e.loc?.join(".")}: ${e.msg}`).join("; ");
    }
    setStatus($("sessionStatus"), `Error: ${msg}`);
    return;
  }
  sessionId = data.session_id;
  setStatus($("sessionStatus"), `Session started: ${sessionId}`);
  $("submitTextBtn").disabled = true;
  $("submitAudioBtn").disabled = true;
  $("startVideoBtn").disabled = true;
  $("nextBtn").disabled = true;
  resetEvaluation();
  await nextQuestion();
  await refreshSession();
}

async function nextQuestion() {
  if (!sessionId) return;
  resetEvaluation();
  stopCamera(); // reset camera state between questions
  const r = await fetch(`/api/sessions/${sessionId}/next`, { method: "POST" });
  const data = await r.json();
  if (!r.ok) {
    $("questionText").textContent = data.detail || "No more questions.";
    if ((data.detail || "").toLowerCase().includes("no more questions")) {
      $("qCategory").textContent = "completed";
      $("qDifficulty").textContent = "done";
      $("qIndex").textContent = "✓";
      $("answerModeBadge").textContent = "Session complete";
      $("answerModeBadge").hidden = false;
      $("sessionStatus").textContent = "Session completed. Start a new session for another round.";
    }
    $("submitTextBtn").disabled = true;
    $("submitAudioBtn").disabled = true;
    $("startVideoBtn").disabled = true;
    $("nextBtn").disabled = true;
    stopCamera();
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
  $("startVideoBtn").disabled = true;
  $("submitVideoBtn").disabled = true;
  stopCamera();
}

async function submitText() {
  if (!sessionId || !currentQuestionId) return;
  const ans = $("answerText").value.trim();
  if (!ans) return;

  $("submitTextBtn").disabled = true;
  $("submitTextBtn").textContent = "Evaluating…";
  const payload = { question_id: currentQuestionId, answer: ans };
  const r = await fetch(`/api/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await r.json();
  $("submitTextBtn").textContent = "Submit text";
  if (!r.ok) {
    alert(data.detail || "submit failed");
    $("submitTextBtn").disabled = false;
    return;
  }
  renderEvaluation(data);
  await refreshSession();
}

async function submitAudio() {
  if (!sessionId || !currentQuestionId) return;
  const file = $("audioFile").files[0];
  if (!file) return;

  $("submitAudioBtn").disabled = true;
  $("submitAudioBtn").textContent = "Transcribing…";
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(
    `/api/sessions/${sessionId}/answer-audio?question_id=${encodeURIComponent(currentQuestionId)}`,
    { method: "POST", body: fd }
  );
  const data = await r.json();
  $("submitAudioBtn").textContent = "Submit audio";
  if (!r.ok) {
    alert(data.detail || "audio submit failed");
    $("submitAudioBtn").disabled = false;
    return;
  }
  renderEvaluation(data);
  await refreshSession();
}

async function submitVideo() {
  if (!sessionId || !currentQuestionId || !recordedBlob) return;

  $("submitVideoBtn").disabled = true;
  $("submitVideoBtn").textContent = "Uploading & transcribing…";

  const ext = recordedBlob.type.includes("mp4") ? "mp4" : "webm";
  const fd = new FormData();
  fd.append("file", recordedBlob, `answer.${ext}`);

  const r = await fetch(
    `/api/sessions/${sessionId}/answer-video?question_id=${encodeURIComponent(currentQuestionId)}`,
    { method: "POST", body: fd }
  );
  const data = await r.json();
  $("submitVideoBtn").textContent = "Submit video answer";
  if (!r.ok) {
    alert(data.detail || "video submit failed");
    $("submitVideoBtn").disabled = false;
    return;
  }
  renderEvaluation(data);
  await refreshSession();
}

// ─── Event listeners ───────────────────────────────────────────────────────────
$("uploadBtn").addEventListener("click", uploadResume);
$("startBtn").addEventListener("click", startSession);
$("submitTextBtn").addEventListener("click", submitText);
$("submitAudioBtn").addEventListener("click", submitAudio);
$("submitVideoBtn").addEventListener("click", submitVideo);
$("nextBtn").addEventListener("click", nextQuestion);

// ─── Init: load provider info ──────────────────────────────────────────────────
(async () => {
  try {
    const r = await fetch("/api/meta");
    const meta = await r.json();
    $("modePill").textContent = `LLM: ${meta.llm_provider} • STT: ${meta.stt_provider}`;
    if (meta.stub_mode) {
      $("stubWarning").hidden = false;
    }
  } catch (_) {
    // ignore
  }
})();
