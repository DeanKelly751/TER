"""Feedback metrics for comparing real-time vs post-hoc detection.

Computes precision, recall, and F1 score by matching real-time alerts
to post-hoc WastePattern objects.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import TERResult
    from ..alerts.models import Alert

logger = logging.getLogger(__name__)


@dataclass
class FeedbackMetrics:
    """Metrics comparing real-time alerts to post-hoc ground truth.

    Measures how well real-time detection matches the embedding-based
    post-hoc analysis (which is considered ground truth).
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float

    # Per-pattern breakdown
    pattern_metrics: dict[str, dict]

    @classmethod
    def compute(
        cls, realtime_alerts: list["Alert"], posthoc_result: "TERResult"
    ) -> "FeedbackMetrics":
        """Match real-time alerts to post-hoc WastePattern objects.

        Strategy:
        - Group alerts and patterns by type
        - Compare counts (simple matching)
        - Compute TP/FP/FN for each pattern
        - Aggregate to global metrics

        Args:
            realtime_alerts: Alerts generated during real-time detection
            posthoc_result: Full TER analysis result

        Returns:
            FeedbackMetrics with precision/recall/F1
        """
        # Group alerts by pattern type
        rt_by_pattern = defaultdict(list)
        for alert in realtime_alerts:
            rt_by_pattern[alert.pattern].append(alert)

        # Group post-hoc patterns by type
        ph_by_pattern = defaultdict(list)
        for wp in posthoc_result.waste_patterns:
            ph_by_pattern[wp.pattern_type].append(wp)

        # Compute per-pattern metrics
        tp = fp = fn = 0
        pattern_metrics = {}

        all_patterns = set(rt_by_pattern.keys()) | set(ph_by_pattern.keys())

        for pattern in all_patterns:
            rt_count = len(rt_by_pattern[pattern])
            ph_count = len(ph_by_pattern[pattern])

            # Simple count-based matching
            # TP: min of real-time and post-hoc (matched detections)
            # FP: real-time detected but post-hoc didn't (false alarms)
            # FN: post-hoc detected but real-time didn't (missed)
            pattern_tp = min(rt_count, ph_count)
            pattern_fp = max(0, rt_count - ph_count)
            pattern_fn = max(0, ph_count - rt_count)

            tp += pattern_tp
            fp += pattern_fp
            fn += pattern_fn

            pattern_metrics[pattern] = {
                "true_positives": pattern_tp,
                "false_positives": pattern_fp,
                "false_negatives": pattern_fn,
                "realtime_count": rt_count,
                "posthoc_count": ph_count,
            }

        # Global precision/recall/F1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        logger.info(
            f"Feedback metrics: P={precision:.2f}, R={recall:.2f}, F1={f1:.2f} "
            f"(TP={tp}, FP={fp}, FN={fn})"
        )

        return cls(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            pattern_metrics=pattern_metrics,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "pattern_metrics": self.pattern_metrics,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Precision: {self.precision:.2%} ({self.false_positives} false positives)",
            f"Recall: {self.recall:.2%} ({self.false_negatives} missed)",
            f"F1 Score: {self.f1_score:.2%}",
            f"True Positives: {self.true_positives}",
        ]

        if self.pattern_metrics:
            lines.append("\nPer-pattern breakdown:")
            for pattern, metrics in sorted(self.pattern_metrics.items()):
                lines.append(
                    f"  {pattern.replace('_', ' ').title()}: "
                    f"RT={metrics['realtime_count']}, "
                    f"PH={metrics['posthoc_count']}, "
                    f"TP={metrics['true_positives']}"
                )

        return "\n".join(lines)
