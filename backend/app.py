"""Flask API for the IntelliProctor MVP.

This prototype accepts derived landmark features only; it deliberately does not
receive, store, or identify video frames. Production use needs consent, a data
retention policy, accessibility validation, security review, and human review.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from detection.baseline_detector import PersonalizedBaselineDetector
from backend.questions import answer_is_correct, grade_answers, public_questions
from backend.storage import initialize, recent_reports, save_answer, save_finished, save_report, save_started, saved_report

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)
sessions: dict[str, dict] = {}
CRITICAL_STREAK = 3
PROHIBITED_OBJECT_STREAK = 1
MULTIPLE_FACE_STREAK = 2
BROWSER_LEAVE_STREAK = 3
# India Standard Time is fixed at UTC+05:30; India has no daylight-saving time.
INDIA_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")
initialize()


def now_india() -> str:
    return datetime.now(INDIA_TZ).isoformat()


def error(message: str, code: int = 400):
    return jsonify({"error": message}), code


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/assessment/questions")
def questions():
    return jsonify({"duration_minutes": 30, "questions": public_questions()})


@app.get("/api/reviewer/reports")
def reviewer_reports():
    """Local MVP reviewer queue. Production requires authentication and access control."""
    return jsonify({"reports": recent_reports()})


@app.post("/api/assessment/start")
def start_assessment():
    payload = request.get_json(silent=True) or {}
    samples = payload.get("samples")
    if not isinstance(samples, list):
        return error("samples must be an array of derived landmark feature objects.")
    detector = PersonalizedBaselineDetector()
    try:
        baseline = detector.build_baseline(samples)
    except ValueError as exc:
        return error(str(exc))
    candidate = payload.get("candidate") or {}
    name, email = str(candidate.get("name", "")).strip(), str(candidate.get("email", "")).strip().lower()
    if not name or not email or "@" not in email or not bool(candidate.get("consent")):
        return error("candidate name, valid email, and data-storage consent are required.")
    assessment_id = str(payload.get("assessment_id") or uuid4())
    started_at = now_india()
    baseline_record = {"sample_count": baseline.sample_count, "review_threshold": baseline.review_threshold, "termination_threshold": baseline.termination_threshold}
    try:
        candidate_id = save_started(assessment_id, {"name": name, "email": email, "consent": True}, started_at, baseline_record)
    except Exception as exc:
        return error(f"Could not save assessment data: {exc}", 500)
    sessions[assessment_id] = {
        "detector": detector, "events": [], "started_at": started_at, "candidate": {"id": candidate_id, "name": name, "email": email},
        "critical_streak": 0, "object_streak": 0, "multiple_face_streak": 0, "browser_leave_streak": 0,
        "terminated": False, "completed": False, "termination_reason": None,
    }
    return jsonify({"assessment_id": assessment_id, "status": "baseline_established", "sample_count": baseline.sample_count, "timezone": "Asia/Kolkata", "duration_minutes": 30, "baseline_thresholds": {"review": baseline.review_threshold, "termination": baseline.termination_threshold}})


@app.post("/api/assessment/score_frame")
def score_frame():
    payload = request.get_json(silent=True) or {}
    session = sessions.get(str(payload.get("assessment_id", "")))
    if not session:
        return error("Assessment not found.", 404)
    if session["terminated"] or session["completed"]:
        return jsonify({"error": "This assessment session has ended.", "session_ended": True}), 409
    try:
        result = session["detector"].score(payload.get("features", {}), payload.get("context", {}))
    except ValueError as exc:
        return error(str(exc))
    context = payload.get("context") or {}
    prohibited_object = bool(context.get("prohibited_object"))
    multiple_faces = bool(context.get("multiple_faces"))
    browser_hidden = bool(context.get("browser_hidden"))
    is_critical = session["detector"].is_critical(result["anomaly_score"])
    session["critical_streak"] = session["critical_streak"] + 1 if is_critical else 0
    session["object_streak"] = session["object_streak"] + 1 if prohibited_object else 0
    session["multiple_face_streak"] = session["multiple_face_streak"] + 1 if multiple_faces else 0
    session["browser_leave_streak"] = session["browser_leave_streak"] + 1 if browser_hidden else 0
    if session["object_streak"] >= PROHIBITED_OBJECT_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Mobile phone detected: prohibited-device policy violation."
    elif session["multiple_face_streak"] >= MULTIPLE_FACE_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Multiple faces detected repeatedly: assessment requires one candidate in view."
    elif session["browser_leave_streak"] >= BROWSER_LEAVE_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Assessment window was repeatedly left or hidden."
    elif session["critical_streak"] >= CRITICAL_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Sustained very-high deviation from the session baseline."
    event = {"timestamp": now_india(), "critical": is_critical, "prohibited_object": prohibited_object, "multiple_faces": multiple_faces, "browser_hidden": browser_hidden, **result}
    session["events"].append(event)
    return jsonify({**event, "session_ended": session["terminated"], "termination_reason": session["termination_reason"], "session_action": "END_SESSION" if session["terminated"] else "CONTINUE"})


@app.post("/api/assessment/answer")
def save_assessment_answer():
    payload = request.get_json(silent=True) or {}
    assessment_id = str(payload.get("assessment_id", ""))
    session = sessions.get(assessment_id)
    if not session:
        return error("Assessment not found.", 404)
    if session["terminated"] or session["completed"]:
        return jsonify({"error": "This assessment session has ended."}), 409
    question_id, selected_option = payload.get("question_id"), payload.get("selected_option")
    if not isinstance(question_id, str) or not isinstance(selected_option, int):
        return error("question_id and integer selected_option are required.")
    is_correct = answer_is_correct(question_id, selected_option)
    if is_correct is None:
        return error("Unknown question id.")
    try:
        save_answer(assessment_id, question_id, selected_option, is_correct)
    except Exception as exc:
        return error(f"Could not save answer: {exc}", 500)
    return jsonify({"status": "answer_saved", "question_id": question_id})


@app.post("/api/assessment/finish")
def finish_assessment():
    payload = request.get_json(silent=True) or {}
    session = sessions.get(str(payload.get("assessment_id", "")))
    if not session:
        return error("Assessment not found.", 404)
    answers = payload.get("answers") or {}
    if not isinstance(answers, dict):
        return error("answers must be an object keyed by question id.")
    correct, total, results = grade_answers(answers)
    session["grading"] = {"correct": correct, "total": total, "results": results}
    if not session["terminated"]:
        session["completed"] = True
    ended_at = now_india()
    try:
        save_finished(assessment_id=str(payload.get("assessment_id")), status="TERMINATED" if session["terminated"] else "COMPLETED", ended_at=ended_at, correct=correct, total=total, results=results)
    except Exception as exc:
        return error(f"Could not save final assessment data: {exc}", 500)
    return jsonify({"status": "session_terminated" if session["terminated"] else "assessment_completed", "ended_at": ended_at, "score": {"correct": correct, "total": total, "percent": round(correct / total * 100, 1)}})


@app.get("/api/assessment/report")
def report():
    assessment_id = request.args.get("assessment_id", "")
    session = sessions.get(assessment_id)
    if not session:
        archived = saved_report(assessment_id)
        return jsonify(archived) if archived else error("Assessment not found.", 404)
    events = session["events"]
    average = sum(item["anomaly_score"] for item in events) / len(events) if events else 0
    incidents = []
    active = None
    for item in events:
        incident_status = (
            "PROHIBITED_OBJECT" if item.get("prohibited_object") else "MULTIPLE_FACES" if item.get("multiple_faces")
            else "BROWSER_LEFT" if item.get("browser_hidden") else item["status"]
        )
        if incident_status == "LOW_RISK":
            if active:
                incidents.append(active)
                active = None
            continue
        if not active or active["status"] != incident_status:
            if active:
                incidents.append(active)
            active = {"status": incident_status, "started_at": item["timestamp"], "ended_at": item["timestamp"], "checks": 1}
        else:
            active["ended_at"] = item["timestamp"]
            active["checks"] += 1
    if active:
        incidents.append(active)
    if session["terminated"]:
        reason = session["termination_reason"] or "Session was terminated."
        phone_termination = "mobile phone" in reason.lower()
        multiple_faces_termination = "multiple faces" in reason.lower()
        browser_termination = "window" in reason.lower()
        warning = {
            "code": "MOBILE_PHONE_DETECTED" if phone_termination else "MULTIPLE_FACES" if multiple_faces_termination else "BROWSER_LEFT" if browser_termination else "SUSTAINED_BASELINE_DEVIATION",
            "severity": "critical",
            "title": "Mobile phone detected — session terminated" if phone_termination else "Multiple people detected — session terminated" if multiple_faces_termination else "Assessment window repeatedly left — session terminated" if browser_termination else "Sustained unusual behavior — session terminated",
            "message": reason,
        }
        report_status = "SESSION_TERMINATED"
    elif session["completed"]:
        warning = None
        report_status = "ASSESSMENT_COMPLETED"
    else:
        warning = None
        report_status = "ASSESSMENT_IN_PROGRESS"
    grading = session.get("grading") or {"correct": 0, "total": len(public_questions()), "results": []}
    report_payload = {
        "report_status": report_status,
        "candidate": {"name": session["candidate"]["name"], "email": session["candidate"]["email"]},
        "assessment": {"started_at": session["started_at"], "timezone": "Asia/Kolkata", "duration_minutes": 30},
        "technical_score": {"correct": grading["correct"], "total": grading["total"], "percent": round(grading["correct"] / grading["total"] * 100, 1)},
        "summary_score": round(average, 3),
        "status": session["detector"].status(average),
        "session_ended": session["terminated"],
        "termination_reason": session["termination_reason"],
        "flagged_incidents": incidents,
        "warnings": [warning] if warning else [],
        "recommendation": "Automated integrity signals support a qualified human review; they are not proof of misconduct.",
        "privacy_note": "Candidate profile, answers, final score, grouped incidents, and report are stored locally in SQLite. Raw video and identity embeddings are not stored.",
    }
    if session["completed"] or session["terminated"]:
        try:
            save_report(assessment_id, report_payload, now_india())
        except Exception:
            pass
    return jsonify(report_payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
