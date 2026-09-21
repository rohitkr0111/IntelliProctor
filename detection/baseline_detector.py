"""Statistical personalized-baseline scoring with no biometric persistence."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping

FEATURES = ("gaze_x", "gaze_y", "head_yaw", "head_pitch", "head_roll", "face_scale")
EPSILON = 0.03


@dataclass
class Baseline:
    means: Dict[str, float]
    stds: Dict[str, float]
    sample_count: int
    review_threshold: float
    termination_threshold: float


@dataclass
class PersonalizedBaselineDetector:
    """Scores deviation from a candidate's own calibration data.

    The score is a review signal, never a cheating determination. Feature values
    are normalized client-side landmarks, not images or face embeddings.
    """
    baseline: Baseline | None = None
    history: List[float] = field(default_factory=list)

    def build_baseline(self, samples: Iterable[Mapping[str, float]]) -> Baseline:
        cleaned = [self._clean(sample) for sample in samples]
        if len(cleaned) < 10:
            raise ValueError("At least 10 valid calibration samples are required.")
        means = {name: mean(row[name] for row in cleaned) for name in FEATURES}
        stds = {name: max(pstdev(row[name] for row in cleaned), EPSILON) for name in FEATURES}
        calibration_scores = sorted(self._deviation(row, means, stds) for row in cleaned)
        # These thresholds come from this candidate's calibration variation, not
        # global rules such as “look away for N seconds”. The floors avoid an
        # unstable threshold when calibration happens to be unusually still.
        review_threshold = min(0.65, max(0.30, self._percentile(calibration_scores, 0.90) + 0.08))
        termination_threshold = min(0.90, max(0.65, self._percentile(calibration_scores, 0.99) + 0.15))
        self.baseline = Baseline(means, stds, len(cleaned), review_threshold, termination_threshold)
        return self.baseline

    def score(self, sample: Mapping[str, float], context: Mapping[str, object] | None = None) -> dict:
        if not self.baseline:
            raise ValueError("A baseline must be established before scoring.")
        values = self._clean(sample)
        z_scores = {name: abs(values[name] - self.baseline.means[name]) / self.baseline.stds[name] for name in FEATURES}
        deviation = self._deviation(values, self.baseline.means, self.baseline.stds)
        modifier = self._context_modifier(context or {})
        score = max(0.0, min(1.0, deviation + modifier))
        self.history.append(score)
        return {
            "anomaly_score": round(score, 3),
            "status": self.status(score),
            "top_deviations": [name for name, _ in sorted(z_scores.items(), key=lambda item: item[1], reverse=True)[:2]],
            "context_adjustment": round(modifier, 3),
            "baseline_thresholds": {"review": round(self.baseline.review_threshold, 3), "termination": round(self.baseline.termination_threshold, 3)},
        }

    def status(self, score: float) -> str:
        if not self.baseline:
            raise ValueError("A baseline must be established before scoring.")
        return "LOW_RISK" if score < self.baseline.review_threshold else "REVIEW" if score < self.baseline.termination_threshold else "HIGH_RISK"

    def is_critical(self, score: float) -> bool:
        return bool(self.baseline and score >= self.baseline.termination_threshold)

    @staticmethod
    def _deviation(values: Mapping[str, float], means: Mapping[str, float], stds: Mapping[str, float]) -> float:
        z_scores = [abs(values[name] - means[name]) / stds[name] for name in FEATURES]
        # Root-mean-square prevents a single noisy landmark from dominating.
        return sqrt(sum(min(z, 3.0) ** 2 for z in z_scores) / len(FEATURES)) / 3.0

    @staticmethod
    def _percentile(values: List[float], fraction: float) -> float:
        position = (len(values) - 1) * fraction
        lower, upper = int(position), min(int(position) + 1, len(values) - 1)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)

    @staticmethod
    def _clean(sample: Mapping[str, float]) -> Dict[str, float]:
        try:
            return {name: float(sample[name]) for name in FEATURES}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Feature sample must contain numeric values for: {', '.join(FEATURES)}") from exc

    @staticmethod
    def _context_modifier(context: Mapping[str, object]) -> float:
        adjustment = 0.0
        if bool(context.get("typing")):
            adjustment -= 0.12
        if context.get("difficulty") == "hard":
            adjustment -= 0.08
        if context.get("gaze_direction") == "down":
            adjustment -= 0.06
        # Context can reduce review burden but cannot make an event more punitive.
        return adjustment
