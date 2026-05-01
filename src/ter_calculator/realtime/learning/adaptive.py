"""Adaptive threshold learning system.

Automatically adjusts detection thresholds based on feedback metrics
to improve precision and recall over multiple sessions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import TERResult
    from ..alerts.models import Alert
    from .feedback import FeedbackMetrics

logger = logging.getLogger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not available. Config updates will be disabled.")


class AdaptiveThresholdLearner:
    """Adjust detection thresholds based on feedback.

    Learns from comparing real-time alerts to post-hoc analysis,
    and automatically tunes configuration to improve accuracy.
    """

    def __init__(self, config_path: Path | str | None = None):
        """Initialize adaptive learner.

        Args:
            config_path: Path to config.yaml file. Defaults to ~/.ter/config.yaml
        """
        if config_path is None:
            config_path = Path.home() / ".ter" / "config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.feedback_history: list["FeedbackMetrics"] = []
        self.session_count = 0

        # Load learning history if exists
        self._load_history()

    def learn_from_session(
        self,
        realtime_alerts: list["Alert"],
        posthoc_result: "TERResult",
        learning_config: dict,
    ) -> dict[str, int]:
        """Compare real-time vs post-hoc and adjust thresholds.

        Args:
            realtime_alerts: Alerts from real-time detection
            posthoc_result: Full TER analysis result
            learning_config: Learning configuration dict with:
                - auto_adjust_thresholds: bool
                - min_sessions_before_adjust: int
                - target_precision: float
                - target_recall: float
                - max_adjustment_per_session: int

        Returns:
            Dictionary of threshold adjustments made (empty if none)
        """
        from .feedback import FeedbackMetrics

        # Compute feedback metrics
        metrics = FeedbackMetrics.compute(realtime_alerts, posthoc_result)
        self.feedback_history.append(metrics)
        self.session_count += 1

        logger.info(f"Session {self.session_count} feedback: {metrics.summary()}")

        # Save history
        self._save_history(metrics)

        # Check if we should adjust thresholds
        if not learning_config.get("auto_adjust_thresholds", True):
            logger.info("Auto-adjust disabled, skipping threshold updates")
            return {}

        min_sessions = learning_config.get("min_sessions_before_adjust", 5)
        if self.session_count < min_sessions:
            logger.info(
                f"Need {min_sessions - self.session_count} more sessions before adjusting"
            )
            return {}

        # Compute adjustments
        adjustments = self._compute_adjustments(metrics, learning_config)

        if adjustments:
            logger.info(f"Applying threshold adjustments: {adjustments}")
            self._apply_adjustments(adjustments)
        else:
            logger.info("No threshold adjustments needed")

        return adjustments

    def _compute_adjustments(
        self, metrics: "FeedbackMetrics", learning_config: dict
    ) -> dict[str, int]:
        """Determine which thresholds to adjust based on metrics.

        Strategy:
        - Low precision (< target) → too many false positives → raise thresholds
        - Low recall (< target) → too many false negatives → lower thresholds
        - Use per-pattern metrics to adjust specific patterns

        Args:
            metrics: Current feedback metrics
            learning_config: Learning configuration

        Returns:
            Dictionary mapping config keys to adjustment deltas
        """
        target_precision = learning_config.get("target_precision", 0.80)
        target_recall = learning_config.get("target_recall", 0.70)
        max_adjustment = learning_config.get("max_adjustment_per_session", 1)

        adjustments: dict[str, int] = {}

        # Global precision/recall
        precision_gap = target_precision - metrics.precision
        recall_gap = target_recall - metrics.recall

        # Allow small tolerance before adjusting (5% gap)
        tolerance = 0.05

        if precision_gap > tolerance:
            # Too many false positives → raise thresholds
            logger.info(
                f"Precision {metrics.precision:.2%} < target {target_precision:.2%}, "
                f"raising thresholds"
            )
            adjustments["patterns.repetitive_reads.min_reads"] = +1
            adjustments["patterns.edit_fragmentation.min_consecutive"] = +1

        elif recall_gap > tolerance:
            # Too many false negatives → lower thresholds
            logger.info(
                f"Recall {metrics.recall:.2%} < target {target_recall:.2%}, "
                f"lowering thresholds"
            )
            adjustments["patterns.repetitive_reads.min_reads"] = -1
            adjustments["patterns.edit_fragmentation.min_consecutive"] = -1

        # Clamp adjustments to max magnitude
        for key in adjustments:
            adjustments[key] = max(
                -max_adjustment, min(max_adjustment, adjustments[key])
            )

        return adjustments

    def _apply_adjustments(self, adjustments: dict[str, int]):
        """Update config.yaml with learned thresholds.

        Args:
            adjustments: Dictionary mapping config keys to delta values
        """
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, cannot update config")
            return

        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return

        # Load current config
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        # Apply adjustments
        for key, delta in adjustments.items():
            # Navigate nested dict: "patterns.repetitive_reads.min_reads"
            parts = key.split(".")
            node = config

            # Navigate to parent node
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                node = node[part]

            # Get current value
            param_name = parts[-1]
            current = node.get(param_name, 3)  # Default 3 for most thresholds

            # Apply adjustment (never go below 1)
            new_value = max(1, current + delta)
            node[param_name] = new_value

            logger.info(f"Adjusted {key}: {current} → {new_value} (Δ{delta:+d})")

        # Write updated config
        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated config saved to {self.config_path}")

    def _load_history(self):
        """Load learning history from disk."""
        history_path = self.config_path.parent / "learning_history.jsonl"
        if not history_path.exists():
            return

        try:
            with open(history_path, "r") as f:
                for line in f:
                    data = json.loads(line)
                    self.session_count = max(
                        self.session_count, data.get("session_count", 0)
                    )
        except Exception as e:
            logger.warning(f"Failed to load learning history: {e}")

    def _save_history(self, metrics: "FeedbackMetrics"):
        """Append feedback metrics to history file.

        Args:
            metrics: Feedback metrics to save
        """
        history_path = self.config_path.parent / "learning_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(history_path, "a") as f:
                entry = {
                    "session_count": self.session_count,
                    "timestamp": str(Path.cwd()),  # Placeholder, should be datetime
                    **metrics.to_dict(),
                }
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to save learning history: {e}", exc_info=True)

    def get_learning_summary(self) -> dict:
        """Get summary of learning progress.

        Returns:
            Dictionary with learning statistics
        """
        if not self.feedback_history:
            return {
                "sessions_analyzed": 0,
                "average_precision": 0.0,
                "average_recall": 0.0,
                "average_f1": 0.0,
            }

        recent = self.feedback_history[-5:]  # Last 5 sessions

        return {
            "sessions_analyzed": self.session_count,
            "average_precision": sum(m.precision for m in recent) / len(recent),
            "average_recall": sum(m.recall for m in recent) / len(recent),
            "average_f1": sum(m.f1_score for m in recent) / len(recent),
            "latest_metrics": recent[-1].to_dict() if recent else None,
        }
