"""Unit tests for real-time learning system."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ter_calculator.models import WastePattern
from ter_calculator.realtime import Severity
from ter_calculator.realtime.alerts.models import Alert
from ter_calculator.realtime.learning.feedback import FeedbackMetrics


@pytest.fixture
def sample_alerts():
    """Sample real-time alerts."""
    return [
        Alert(
            pattern="repetitive_read",
            severity=Severity.WARNING,
            details={"file_path": "/config.json", "read_count": 3},
            suggestion="Consider caching",
            timestamp=datetime.now(),
        ),
        Alert(
            pattern="edit_fragmentation",
            severity=Severity.WARNING,
            details={"file_path": "/main.py", "consecutive_count": 3},
            suggestion="Batch edits",
            timestamp=datetime.now(),
        ),
        Alert(
            pattern="duplicate_tool_call",
            severity=Severity.WARNING,
            details={"tool_name": "Read"},
            suggestion="Avoid duplicates",
            timestamp=datetime.now(),
        ),
    ]


@pytest.fixture
def sample_posthoc_patterns():
    """Sample post-hoc waste patterns."""
    return [
        WastePattern(
            pattern_type="repetitive_reads",
            description="File /config.json read 3 times",
            start_position=100,
            end_position=550,
            spans_involved=3,
            tokens_wasted=450,
            details={"file_path": "/config.json", "count": 3},
        ),
        WastePattern(
            pattern_type="edit_fragmentation",
            description="3 consecutive edits to /main.py",
            start_position=600,
            end_position=900,
            spans_involved=3,
            tokens_wasted=300,
            details={"file_path": "/main.py", "count": 3},
        ),
        WastePattern(
            pattern_type="duplicate_tool_calls",
            description="Read tool called 2x with same input",
            start_position=1000,
            end_position=1200,
            spans_involved=2,
            tokens_wasted=200,
            details={"tool_name": "Read", "count": 2},
        ),
        # Extra pattern not detected by real-time (false negative)
        WastePattern(
            pattern_type="repetitive_reads",
            description="File /utils.py read 2 times",
            start_position=1300,
            end_position=1450,
            spans_involved=2,
            tokens_wasted=150,
            details={"file_path": "/utils.py", "count": 2},
        ),
    ]


class TestFeedbackMetrics:
    """Tests for FeedbackMetrics computation."""

    def test_perfect_match(self, sample_alerts):
        # All alerts match post-hoc patterns (remove the false negative)
        posthoc = [
            WastePattern(
                pattern_type="repetitive_reads",
                description="Repetitive reads",
                start_position=0,
                end_position=450,
                spans_involved=3,
                tokens_wasted=450,
                details={"count": 3},
            ),
            WastePattern(
                pattern_type="edit_fragmentation",
                description="Edit fragmentation",
                start_position=450,
                end_position=750,
                spans_involved=3,
                tokens_wasted=300,
                details={"count": 3},
            ),
            WastePattern(
                pattern_type="duplicate_tool_calls",
                description="Duplicate tool calls",
                start_position=750,
                end_position=950,
                spans_involved=2,
                tokens_wasted=200,
                details={"count": 2},
            ),
        ]

        metrics = FeedbackMetrics.compute(sample_alerts, posthoc)

        assert metrics.true_positives == 3
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0

    def test_false_positives(self):
        # Real-time alerts that don't match post-hoc
        alerts = [
            Alert(
                pattern="repetitive_read",
                severity=Severity.WARNING,
                details={"file_path": "/fake.json"},
                suggestion="Cache",
                timestamp=datetime.now(),
            ),
            Alert(
                pattern="edit_fragmentation",
                severity=Severity.WARNING,
                details={"file_path": "/fake.py"},
                suggestion="Batch",
                timestamp=datetime.now(),
            ),
        ]
        posthoc = []  # No actual patterns

        metrics = FeedbackMetrics.compute(alerts, posthoc)

        assert metrics.true_positives == 0
        assert metrics.false_positives == 2
        assert metrics.false_negatives == 0
        assert metrics.precision == 0.0
        assert metrics.recall is None  # No ground truth

    def test_false_negatives(self, sample_posthoc_patterns):
        # Real-time missed some patterns
        alerts = [
            Alert(
                pattern="repetitive_read",
                severity=Severity.WARNING,
                details={},
                suggestion="",
                timestamp=datetime.now(),
            )
        ]  # Only caught 1 of 4 patterns

        metrics = FeedbackMetrics.compute(alerts, sample_posthoc_patterns)

        assert metrics.true_positives >= 1
        assert metrics.false_negatives >= 2  # Missed at least 2 patterns
        assert metrics.recall < 1.0

    def test_mixed_results(self, sample_alerts, sample_posthoc_patterns):
        # Some matches, some misses
        metrics = FeedbackMetrics.compute(sample_alerts, sample_posthoc_patterns)

        # 3 alerts match 3 of 4 posthoc patterns
        assert metrics.true_positives == 3
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 1  # Missed /utils.py read
        assert 0.0 < metrics.precision <= 1.0
        assert 0.0 < metrics.recall < 1.0

    def test_per_pattern_breakdown(self, sample_alerts, sample_posthoc_patterns):
        metrics = FeedbackMetrics.compute(sample_alerts, sample_posthoc_patterns)

        # Check per-pattern metrics exist
        assert "repetitive_read" in metrics.per_pattern
        assert "edit_fragmentation" in metrics.per_pattern

        repetitive = metrics.per_pattern["repetitive_read"]
        assert repetitive["true_positives"] >= 1
        assert repetitive["false_negatives"] >= 1  # Missed utils.py

    def test_summary_format(self, sample_alerts, sample_posthoc_patterns):
        metrics = FeedbackMetrics.compute(sample_alerts, sample_posthoc_patterns)
        summary = metrics.summary()

        assert "Precision:" in summary
        assert "Recall:" in summary
        assert "F1 Score:" in summary
        assert "True Positives:" in summary

    def test_pattern_name_normalization(self):
        # Real-time uses "repetitive_read", post-hoc uses "repetitive_reads"
        alert = Alert(
            pattern="repetitive_read",
            severity=Severity.WARNING,
            details={},
            suggestion="",
            timestamp=datetime.now(),
        )
        pattern = WastePattern(
            pattern_type="repetitive_reads",
            description="Pattern",
            start_position=0,
            end_position=100,
            spans_involved=1,
            tokens_wasted=450,
            details={},
        )

        # Should match despite naming difference
        metrics = FeedbackMetrics.compute([alert], [pattern])
        assert metrics.true_positives >= 1

    def test_count_based_matching(self):
        # Match by count of same pattern type
        alerts = [
            Alert(
                pattern="duplicate_tool_call",
                severity=Severity.WARNING,
                details={},
                suggestion="",
                timestamp=datetime.now(),
            ),
            Alert(
                pattern="duplicate_tool_call",
                severity=Severity.WARNING,
                details={},
                suggestion="",
                timestamp=datetime.now(),
            ),
        ]
        posthoc = [
            WastePattern(
                pattern_type="duplicate_tool_calls",
                description="Duplicate 1",
                start_position=0,
                end_position=200,
                spans_involved=2,
                tokens_wasted=400,
                details={},
            ),
            WastePattern(
                pattern_type="duplicate_tool_calls",
                description="Duplicate 2",
                start_position=200,
                end_position=400,
                spans_involved=2,
                tokens_wasted=300,
                details={},
            ),
        ]

        metrics = FeedbackMetrics.compute(alerts, posthoc)
        assert metrics.true_positives == 2
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0


class TestAdaptiveThresholdLearner:
    """Tests for adaptive threshold learning - basic functionality only."""

    def test_learning_history_persistence(self, tmp_path, monkeypatch):
        # Import inside test to avoid issues if module is missing
        pytest.importorskip("yaml")
        from ter_calculator.realtime.learning.adaptive import AdaptiveThresholdLearner

        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = {
            "patterns": {},
            "learning": {
                "enabled": True,
                "auto_adjust_thresholds": True,
                "min_sessions_before_adjust": 1,
                "target_precision": 0.80,
                "target_recall": 0.70,
            },
        }

        learner = AdaptiveThresholdLearner(config_path=None)

        alerts = []
        posthoc = []

        learner.learn_from_session(alerts, posthoc, config)

        # Check history file was created
        history_file = tmp_path / ".ter" / "learning_history.jsonl"
        assert history_file.exists()

        # Check it's valid JSONL
        lines = history_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert "timestamp" in record
        assert "precision" in record
        assert "recall" in record
