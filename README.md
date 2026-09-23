# IntelliProctor — technical assessment MVP

IntelliProctor is a local 30-minute technical multiple-choice assessment with two distinct integrity layers:

- **Personalized behavior baseline:** a 12-second on-device calibration creates an individual range for face/gaze/head landmark ratios. A session ends only after three sustained, very-high deviations from that candidate’s own baseline.
- **Transparent fixed rules:** a confirmed mobile phone ends the session immediately; repeated multiple-face and browser-leave signals also end the session.

It is intentionally an assessment-session prototype, not a validated cheating detector. It cannot “ban” a person from their browser or prove intent. It terminates the server-side assessment session and produces evidence for a qualified human to review.

## What the assessment includes

- 30-minute timer in India Standard Time (`Asia/Kolkata`)
- 10 server-owned MCQs across Python, algorithms, SQL, web, JavaScript, Git, testing, DevOps, databases, and concurrency
- Server-side answer grading; answer keys are never sent to the browser
- Candidate name, email, explicit storage consent, answers, technical score, grouped integrity incidents, and final report saved locally in SQLite
- Client-side MediaPipe face-landmark and mobile-phone checks; raw video and face embeddings are not stored or uploaded

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests
python backend/app.py
```

Open `http://localhost:5000`. On first camera use, the browser downloads MediaPipe models, so it needs internet access and camera permission.

## Data stored locally

The database is `data/intelliproctor.db` (ignored by Git). It holds:

- candidate name, email, consent record, and session timestamps
- submitted answer selections and computed technical score
- calibration thresholds, grouped integrity incidents, and final report

It does **not** store raw camera footage or facial identity embeddings. Before real-world use, add user authentication, encryption at rest, retention/deletion controls, audit logging, access control, accessibility testing, bias/accuracy evaluation, an appeal process, and legal/privacy review.

## Integrity policy

| Signal | Action |
| --- | --- |
| Confirmed mobile phone | Terminate the assessment session immediately |
| Two consecutive multiple-face checks | Terminate the assessment session |
| Three repeated browser-hidden/window-leave checks | Terminate the assessment session |
| Three consecutive very-high deviations from personal baseline | Terminate the assessment session |

Automatic termination is an integrity-policy action, not proof of misconduct. The final report is a decision-support artifact for human review.
