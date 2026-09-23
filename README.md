# IntelliProctor MVP

An explainable proctoring-review prototype that calibrates to an individual's own behavior before emitting an anomaly signal. A signal is **not** a cheating finding: any consequential action requires trained human review.

## What is included

- Statistical personalized baseline built from normalized landmark features.
- Context adjustments that can reduce review burden when typing, responding to a hard question, or looking down.
- Flask JSON API with in-memory, active-session-only data.
- A browser demo with optional webcam calibration. MediaPipe derives landmarks in the browser; raw camera frames and identity templates are never posted to the API.
- A contextual assessment prompt: only a local boolean for recent typing and selected difficulty are sent with a score; answer text never leaves the browser.
- Unit tests for normal and strong-deviation cases.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests
python backend/app.py
```

Open `http://localhost:5000`.

## API

`POST /api/assessment/start` accepts `{ "samples": [feature, ...] }`; each feature has `gaze_x`, `gaze_y`, `head_yaw`, `head_pitch`, `head_roll`, and `face_scale` numeric values.

`POST /api/assessment/score_frame` accepts an `assessment_id`, `features`, and optional non-sensitive `context` (`typing`, `difficulty`, `gaze_direction`). `GET /api/assessment/report?assessment_id=…` produces a compact review timeline.

## Candidate experience

The browser samples derived landmarks about every two seconds to keep the session check current. It does **not** create a report for every sample: a report is generated only when the user chooses **View report**. Reports contain grouped flagged incidents rather than raw sample-by-sample data. The candidate sees a plain-language all-clear, a temporary camera check, or a warning after three consecutive elevated checks.

The API builds review and termination thresholds from the calibration distribution for that session, rather than fixed behavior rules (for example, “eyes away for N seconds”). It ends the session after three consecutive deviations above that personal termination range and rejects later scores. This guardrail is deliberately strict: ending a session is not a finding of wrongdoing, and any consequence requires qualified human review. Session timestamps use India Standard Time (`Asia/Kolkata`).

## Mobile-phone policy

Behavioral monitoring cannot identify a phone. The browser therefore runs a separate on-device object detector for the `cell phone` class; no camera frame is sent to the server. A confirmed mobile-phone detection sends a policy signal to the API, which immediately ends the session and records one grouped `PROHIBITED_OBJECT` incident. The final summary presents a clear policy-warning message instead of raw JSON. Object detection is probabilistic, so a human must review the outcome.

## Guardrails

This is an MVP demonstration—not a validated cheating detector. Do not use it for automated employment, education, or disciplinary decisions. Before collecting real video, complete consent, retention/deletion, security, accessibility, bias, accuracy, and legal assessments with qualified stakeholders.
