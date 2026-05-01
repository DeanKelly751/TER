"""Post-hoc analysis integration.

Runs full TER analysis (with embeddings) on completed sessions.
"""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import TERResult

logger = logging.getLogger(__name__)


class PostHocAnalyzer:
    """Runs full TER analysis (with embeddings) on completed session.

    Integrates with existing analyze_pipeline.py to reuse all the
    embedding-based detectors (reasoning loops, context restatement, etc.)
    """

    def __init__(self, thresholds_config: dict | None = None):
        """Initialize post-hoc analyzer.

        Args:
            thresholds_config: Optional threshold overrides for analysis
        """
        self.thresholds = thresholds_config or {}

    def analyze_session(self, snapshot_path: Path | str) -> "TERResult":
        """Execute full TER pipeline on JSONL snapshot.

        Args:
            snapshot_path: Path to session JSONL snapshot

        Returns:
            TERResult with complete analysis including embeddings

        Raises:
            FileNotFoundError: If snapshot doesn't exist
        """
        from ...analyze_pipeline import analyze_session

        snapshot_path = Path(snapshot_path)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Session snapshot not found: {snapshot_path}")

        # Build args compatible with analyze_pipeline
        args = self._build_analyze_args(snapshot_path)

        # Run full TER analysis (this will use embeddings)
        logger.info(f"Running post-hoc analysis on {snapshot_path.name}")
        result = analyze_session(args)

        logger.info(
            f"Post-hoc TER: {result.aggregate_ter:.2f} "
            f"(waste: {len([p for p in result.waste_patterns])} patterns)"
        )

        return result

    def _build_analyze_args(self, snapshot_path: Path) -> Namespace:
        """Build argparse.Namespace for analyze_pipeline.

        Uses defaults from existing pipeline with optional overrides.
        """
        return Namespace(
            session_path=str(snapshot_path),
            similarity_threshold=self.thresholds.get("similarity_threshold", 0.40),
            confidence_threshold=self.thresholds.get("confidence_threshold", 0.75),
            restatement_threshold=self.thresholds.get("restatement_threshold", 0.85),
            phase_weights=self.thresholds.get("phase_weights", "0.3,0.4,0.3"),
            no_waste_patterns=False,
            cost_model="sonnet",
            no_input_analysis=False,
            prompt_similarity_threshold=self.thresholds.get(
                "prompt_similarity_threshold", 0.75
            ),
        )
