# Architecture

```text
Candidate browser (30-minute MCQ assessment)
    ├─ MediaPipe face landmarks ───┐
    ├─ MediaPipe phone detector ───┼─ derived signals only ─→ Flask API
    ├─ window visibility events ───┘                            ├─ personal baseline scorer
    └─ MCQ selections ──────────────────────────────────────────├─ fixed-rule enforcement
                                                                  ├─ server-side MCQ grading
                                                                  └─ SQLite: candidate, answers, grouped report
```

The browser never sends raw camera frames. The baseline learns the candidate’s own variation during calibration; it is separate from transparent policy rules for a phone, repeated multiple faces, and repeatedly leaving the assessment window. Session termination prevents further scoring for that assessment ID, but does not prove misconduct or control the candidate’s browser outside this app.
