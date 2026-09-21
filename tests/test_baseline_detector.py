import unittest
from detection.baseline_detector import PersonalizedBaselineDetector

SAMPLE = {"gaze_x": .5, "gaze_y": .5, "head_yaw": 0, "head_pitch": 0, "head_roll": 0, "face_scale": 1}

class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = PersonalizedBaselineDetector()
        self.detector.build_baseline([SAMPLE] * 12)

    def test_baseline_like_sample_is_low_risk(self):
        self.assertEqual(self.detector.score(SAMPLE)["status"], "LOW_RISK")

    def test_large_deviation_is_high_risk_signal(self):
        changed = {name: 2 for name in SAMPLE}
        self.assertEqual(self.detector.score(changed)["status"], "HIGH_RISK")

if __name__ == "__main__":
    unittest.main()
