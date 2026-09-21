import { FaceLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";

const API = "";
const $ = (id) => document.getElementById(id);
const video = $("camera");
let assessmentId, landmarker, stream, scoringTimer, countdownTimer, lastTypingAt = 0, elevatedSamples = 0, remainingSeconds = 600, assessmentFinished = false;

function show(message) { $("message").textContent = message; }
function renderTimer() { const minutes = String(Math.floor(remainingSeconds / 60)).padStart(2, "0"), seconds = String(remainingSeconds % 60).padStart(2, "0"); $("assessmentTimer").textContent = `${minutes}:${seconds}`; }
function startCountdown() { renderTimer(); countdownTimer = setInterval(() => { remainingSeconds -= 1; renderTimer(); if (remainingSeconds <= 0) finishAssessment("Time has expired. Your assessment has been submitted."); }, 1000); }
function stopMonitoring() { clearInterval(scoringTimer); scoringTimer = null; }
function stopCamera() { stream?.getTracks().forEach((track) => track.stop()); $("cameraState").textContent = "Camera session ended"; }
function updateIndiaTime() { $("indiaTime").textContent = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).format(new Date()); }
updateIndiaTime(); setInterval(updateIndiaTime, 1000);
function landmarkFeature(points) {
  // Normalized landmark ratios reduce the impact of camera position.
  const p = (index) => points[index];
  const left = p(234), right = p(454), nose = p(1), forehead = p(10), chin = p(152);
  const width = Math.max(right.x - left.x, .001), height = Math.max(chin.y - forehead.y, .001);
  const leftIris = p(468), rightIris = p(473);
  return {
    gaze_x: ((leftIris.x + rightIris.x) / 2 - (p(33).x + p(263).x) / 2) / width,
    gaze_y: ((leftIris.y + rightIris.y) / 2 - forehead.y) / height,
    head_yaw: (nose.x - (left.x + right.x) / 2) / width,
    head_pitch: (nose.y - (forehead.y + chin.y) / 2) / height,
    head_roll: (p(33).y - p(263).y) / width,
    face_scale: width,
  };
}
function currentFeatures() {
  if (!landmarker || video.readyState < 2) return null;
  const result = landmarker.detectForVideo(video, performance.now());
  return result.faceLandmarks?.[0] ? landmarkFeature(result.faceLandmarks[0]) : null;
}
function dot(score) { const item = document.createElement("i"); item.style.height = `${18 + score * 65}px`; item.className = score < .3 ? "low" : score < .6 ? "review" : "high"; $("timeline").append(item); }
function updateSessionCheck(data) {
  const isNormal = data.status === "LOW_RISK";
  const isElevated = data.status === "HIGH_RISK";
  elevatedSamples = isElevated ? elevatedSamples + 1 : 0;
  const copy = isNormal
    ? ["✓", "Everything looks normal", "Your movement is within the range established during calibration."]
    : isElevated
      ? ["!", "Please re-centre for the assessment", "We noticed a continued change from your usual camera position. Check your lighting and make sure you are comfortably in frame."]
      : ["…", "Quick camera check", "A temporary change was noticed. Continue naturally; no action is needed unless you see a warning."];
  $("signalIcon").textContent = copy[0]; $("signalTitle").textContent = copy[1]; $("signalText").textContent = copy[2];
  $("status").textContent = isNormal ? "ALL CLEAR" : isElevated ? "PLEASE CHECK" : "MONITORING";
  $("status").className = `badge ${isNormal ? "low" : isElevated ? "high" : "review"}`;
  $("explanation").textContent = isNormal ? "No action needed." : "This is a session-quality prompt, not an accusation or automated decision.";
  $("warning").classList.toggle("hidden", elevatedSamples < 3);
}
function endSession() {
  if (assessmentFinished) return;
  assessmentFinished = true; stopMonitoring(); clearInterval(countdownTimer); $("score").disabled = true; $("score").textContent = "Session ended"; $("finish").disabled = true;
  $("signalIcon").textContent = "■"; $("signalTitle").textContent = "This session has ended";
  $("signalText").textContent = "A sustained, very large change from your personal calibration range was detected. Please contact the assessment supervisor for next steps.";
  $("status").textContent = "SESSION ENDED"; $("status").className = "badge high";
  $("warningTitle").textContent = "Assessment session ended"; $("warningText").textContent = "Please stop the assessment and contact your supervisor. A human review is required."; $("warning").classList.remove("hidden"); stopCamera(); showReport();
}
async function showReport() { const response = await fetch(`${API}/api/assessment/report?assessment_id=${assessmentId}`); const data = await response.json(); $("reportBox").classList.remove("hidden"); $("reportContent").textContent = JSON.stringify(data, null, 2); }
function startMonitoring() { if (scoringTimer || assessmentFinished) return; sendScore(); scoringTimer = setInterval(sendScore, 2000); $("score").textContent = "Pause session check"; }
function finishAssessment(message = "Assessment submitted. Your grouped session summary is ready.") { if (assessmentFinished) return; assessmentFinished = true; stopMonitoring(); clearInterval(countdownTimer); $("score").disabled = true; $("score").textContent = "Assessment complete"; $("finish").disabled = true; $("status").textContent = "SUBMITTED"; $("status").className = "badge low"; $("signalIcon").textContent = "✓"; $("signalTitle").textContent = "Assessment submitted"; $("signalText").textContent = "Your response remains in this browser. The summary shows only grouped session incidents."; stopCamera(); show(message); showReport(); }
async function sendScore() {
  const features = currentFeatures();
  if (!features) return show("No face landmarks detected. Centre your face and improve lighting.");
  const typing = Date.now() - lastTypingAt < 2200;
  $("typingState").textContent = `Typing activity: ${typing ? "active" : "idle"} (local only)`;
  const context = { typing, difficulty: $("difficulty").value, gaze_direction: "center" };
  const response = await fetch(`${API}/api/assessment/score_frame`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assessment_id: assessmentId, features, context }) });
  const data = await response.json(); if (!response.ok) return show(data.error);
  updateSessionCheck(data); dot(data.anomaly_score); $("report").disabled = false; if (data.session_ended) endSession();
}

$("cameraButton").onclick = async () => {
  try {
    show("Loading on-device face landmark model…");
    const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
    landmarker = await FaceLandmarker.createFromOptions(vision, { baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" }, runningMode: "VIDEO", numFaces: 1 });
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 640, height: 480 }, audio: false });
    video.srcObject = stream; await video.play(); $("cameraState").textContent = "On-device landmark processing active";
    $("cameraButton").disabled = true; $("baseline").disabled = false; show("Camera ready. Begin calibration when you are comfortable.");
  } catch (error) { show(`Camera setup failed: ${error.message}. Allow camera permission and use a secure/local origin.`); }
};
$("baseline").onclick = async () => {
  $("baseline").disabled = true; show("Calibrating for 12 seconds. Stay naturally in frame; no footage is uploaded.");
  const samples = [];
  await new Promise((resolve) => { const timer = setInterval(() => { const value = currentFeatures(); if (value) samples.push(value); if (samples.length >= 40) { clearInterval(timer); resolve(); } }, 300); });
  if (samples.length < 10) { $("baseline").disabled = false; return show("Calibration needs a stable face view. Try again."); }
  const response = await fetch(`${API}/api/assessment/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ samples }) }); const data = await response.json();
  if (!response.ok) { $("baseline").disabled = false; return show(data.error); }
  assessmentId = data.assessment_id; $("score").disabled = false; $("finish").disabled = false; startCountdown(); startMonitoring(); show(`Personal baseline established from ${data.sample_count} samples. The 10-minute assessment and background session check have started.`);
};
$("score").onclick = () => { if (scoringTimer) { stopMonitoring(); $("score").textContent = "3. Resume session check"; show("Background session check paused."); return; } startMonitoring(); show("Background session check resumed."); };
$("finish").onclick = () => finishAssessment();
$("response").addEventListener("input", () => { lastTypingAt = Date.now(); $("typingState").textContent = "Typing activity: active (local only)"; });
window.addEventListener("beforeunload", stopCamera);
