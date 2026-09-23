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

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)
sessions: dict[str, dict] = {}
CRITICAL_STREAK = 3
PROHIBITED_OBJECT_STREAK = 1
# India Standard Time is fixed at UTC+05:30; India has no daylight-saving time.
INDIA_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_india() -> str:
    return datetime.now(INDIA_TZ).isoformat()


def error(message: str, code: int = 400):
    return jsonify({"error": message}), code


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


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
    assessment_id = str(payload.get("assessment_id") or uuid4())
    sessions[assessment_id] = {"detector": detector, "events": [], "started_at": now_india(), "critical_streak": 0, "object_streak": 0, "terminated": False, "completed": False, "termination_reason": None}
    return jsonify({"assessment_id": assessment_id, "status": "baseline_established", "sample_count": baseline.sample_count, "timezone": "Asia/Kolkata", "baseline_thresholds": {"review": baseline.review_threshold, "termination": baseline.termination_threshold}})


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
    prohibited_object = bool((payload.get("context") or {}).get("prohibited_object"))
    is_critical = session["detector"].is_critical(result["anomaly_score"])
    session["critical_streak"] = session["critical_streak"] + 1 if is_critical else 0
    session["object_streak"] = session["object_streak"] + 1 if prohibited_object else 0
    if session["object_streak"] >= PROHIBITED_OBJECT_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Mobile phone detected: prohibited-device policy violation."
    elif session["critical_streak"] >= CRITICAL_STREAK:
        session["terminated"] = True
        session["termination_reason"] = "Sustained very-high deviation from the session baseline."
    event = {"timestamp": now_india(), "critical": is_critical, "prohibited_object": prohibited_object, **result}
    session["events"].append(event)
    return jsonify({**event, "session_ended": session["terminated"], "termination_reason": session["termination_reason"], "session_action": "END_SESSION" if session["terminated"] else "CONTINUE"})


@app.post("/api/assessment/finish")
def finish_assessment():
    payload = request.get_json(silent=True) or {}
    session = sessions.get(str(payload.get("assessment_id", "")))
    if not session:
        return error("Assessment not found.", 404)
    if not session["terminated"]:
        session["completed"] = True
    return jsonify({"status": "session_terminated" if session["terminated"] else "assessment_completed", "ended_at": now_india()})


@app.get("/api/assessment/report")
def report():
    session = sessions.get(request.args.get("assessment_id", ""))
    if not session:
        return error("Assessment not found.", 404)
    events = session["events"]
    average = sum(item["anomaly_score"] for item in events) / len(events) if events else 0
    incidents = []
    active = None
    for item in events:
        incident_status = "PROHIBITED_OBJECT" if item.get("prohibited_object") else item["status"]
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
        phone_termination = "mobile phone" in (session["termination_reason"] or "").lower()
        warning = {
            "code": "MOBILE_PHONE_DETECTED" if phone_termination else "SUSTAINED_BASELINE_DEVIATION",
            "severity": "critical",
            "title": "Mobile phone detected — session terminated" if phone_termination else "Sustained unusual behavior — session terminated",
            "message": session["termination_reason"],
        }
        report_status = "SESSION_TERMINATED"
    elif session["completed"]:
        warning = None
        report_status = "ASSESSMENT_COMPLETED"
    else:
        warning = None
        report_status = "ASSESSMENT_IN_PROGRESS"
    return jsonify({
        "report_status": report_status,
        "summary_score": round(average, 3),
        "status": session["detector"].status(average),
        "session_ended": session["terminated"],
        "termination_reason": session["termination_reason"],
        "flagged_incidents": incidents,
        "warnings": [warning] if warning else [],
        "recommendation": "A qualified human must review before any consequential decision.",
        "privacy_note": "This MVP retains derived features in memory only for the active process.",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
