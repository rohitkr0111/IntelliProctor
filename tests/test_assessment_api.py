import unittest

from backend.app import app, sessions


SAMPLE = {"gaze_x": .5, "gaze_y": .5, "head_yaw": 0, "head_pitch": 0, "head_roll": 0, "face_scale": 1}
CANDIDATE = {"name": "Test Candidate", "email": "candidate@example.com", "consent": True}


class AssessmentApiTests(unittest.TestCase):
    def setUp(self):
        sessions.clear()
        self.client = app.test_client()
        started = self.client.post("/api/assessment/start", json={"candidate": CANDIDATE, "samples": [SAMPLE] * 10})
        self.assessment_id = started.json["assessment_id"]

    def test_critical_streak_ends_session_and_report_groups_incidents(self):
        changed = {name: 2 for name in SAMPLE}
        for _ in range(3):
            response = self.client.post("/api/assessment/score_frame", json={"assessment_id": self.assessment_id, "features": changed})
        self.assertTrue(response.json["session_ended"])
        self.assertEqual(response.json["session_action"], "END_SESSION")
        rejected = self.client.post("/api/assessment/score_frame", json={"assessment_id": self.assessment_id, "features": changed})
        self.assertEqual(rejected.status_code, 409)
        report = self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}").json
        self.assertTrue(report["session_ended"])
        self.assertEqual(len(report["flagged_incidents"]), 1)
        self.assertNotIn("timeline", report)

    def test_repeated_phone_detection_ends_session(self):
        response = self.client.post("/api/assessment/score_frame", json={"assessment_id": self.assessment_id, "features": SAMPLE, "context": {"prohibited_object": True}})
        self.assertTrue(response.json["session_ended"])
        self.assertEqual(response.json["termination_reason"], "Mobile phone detected: prohibited-device policy violation.")
        report = self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}").json
        self.assertEqual(report["flagged_incidents"][0]["status"], "PROHIBITED_OBJECT")
        self.assertEqual(report["report_status"], "SESSION_TERMINATED")
        self.assertEqual(report["warnings"][0]["code"], "MOBILE_PHONE_DETECTED")

    def test_repeated_multiple_faces_ends_session(self):
        for _ in range(2):
            response = self.client.post("/api/assessment/score_frame", json={"assessment_id": self.assessment_id, "features": SAMPLE, "context": {"multiple_faces": True}})
        self.assertTrue(response.json["session_ended"])
        self.assertIn("Multiple faces", response.json["termination_reason"])

    def test_repeated_browser_leave_ends_session(self):
        for _ in range(3):
            response = self.client.post("/api/assessment/score_frame", json={"assessment_id": self.assessment_id, "features": SAMPLE, "context": {"browser_hidden": True}})
        self.assertTrue(response.json["session_ended"])
        self.assertIn("window", response.json["termination_reason"])

    def test_finish_returns_completed_summary(self):
        finished = self.client.post("/api/assessment/finish", json={"assessment_id": self.assessment_id, "answers": {"python-list-comprehension": 0, "sql-left-join": 0}})
        self.assertEqual(finished.json["status"], "assessment_completed")
        report = self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}").json
        self.assertEqual(report["report_status"], "ASSESSMENT_COMPLETED")
        self.assertEqual(report["technical_score"]["correct"], 1)
        self.assertEqual(report["candidate"]["email"], CANDIDATE["email"])
        sessions.clear()
        archived = self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}").json
        self.assertEqual(archived["report_status"], "ASSESSMENT_COMPLETED")

    def test_questions_hide_answer_key_and_consent_is_required(self):
        response = self.client.get("/api/assessment/questions")
        self.assertEqual(response.json["duration_minutes"], 30)
        self.assertEqual(len(response.json["questions"]), 10)
        self.assertNotIn("answer", response.json["questions"][0])
        rejected = self.client.post("/api/assessment/start", json={"candidate": {"name": "No Consent", "email": "no@example.com"}, "samples": [SAMPLE] * 10})
        self.assertEqual(rejected.status_code, 400)

    def test_answer_autosave_and_reviewer_queue(self):
        saved = self.client.post("/api/assessment/answer", json={"assessment_id": self.assessment_id, "question_id": "python-list-comprehension", "selected_option": 0})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json["status"], "answer_saved")
        self.client.post("/api/assessment/finish", json={"assessment_id": self.assessment_id, "answers": {"python-list-comprehension": 0}})
        self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}")
        queue = self.client.get("/api/reviewer/reports").json
        self.assertTrue(any(report["candidate"]["email"] == CANDIDATE["email"] for report in queue["reports"]))


if __name__ == "__main__":
    unittest.main()
