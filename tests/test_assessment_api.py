import unittest

from backend.app import app, sessions


SAMPLE = {"gaze_x": .5, "gaze_y": .5, "head_yaw": 0, "head_pitch": 0, "head_roll": 0, "face_scale": 1}


class AssessmentApiTests(unittest.TestCase):
    def setUp(self):
        sessions.clear()
        self.client = app.test_client()
        started = self.client.post("/api/assessment/start", json={"samples": [SAMPLE] * 10})
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

    def test_finish_returns_completed_summary(self):
        finished = self.client.post("/api/assessment/finish", json={"assessment_id": self.assessment_id})
        self.assertEqual(finished.json["status"], "assessment_completed")
        report = self.client.get(f"/api/assessment/report?assessment_id={self.assessment_id}").json
        self.assertEqual(report["report_status"], "ASSESSMENT_COMPLETED")


if __name__ == "__main__":
    unittest.main()
