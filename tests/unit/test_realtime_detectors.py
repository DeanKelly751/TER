"""Unit tests for real-time pattern detectors."""

from __future__ import annotations

import pytest

from ter_calculator.models import ContentBlock, Message, TokenUsage
from ter_calculator.realtime import Severity
from ter_calculator.realtime.detectors import (
    BashAntipatternDetector,
    DuplicateToolCallsDetector,
    EditFragmentationDetector,
    FailedToolRetryDetector,
    RepetitiveReadsDetector,
)
from ter_calculator.realtime.state import SessionState


@pytest.fixture
def state():
    """Fresh session state for each test."""
    return SessionState(session_id="test-session")


class TestDuplicateToolCallsDetector:
    """Tests for duplicate tool call detection."""

    def test_no_alert_on_first_call(self, state):
        detector = DuplicateToolCallsDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/test.py"},
                    tool_use_id="t1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_alert_on_duplicate(self, state):
        detector = DuplicateToolCallsDetector({"enabled": True})
        dup_input = {"file_path": "/test.py"}

        # First call
        msg1 = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input=dup_input,
                    tool_use_id="t1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        detector.process_message(msg1, state)

        # Duplicate call (triggers on 3rd total occurrence)
        msg2 = Message(
            uuid="m2",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input=dup_input,
                    tool_use_id="t2",
                ),
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input=dup_input,
                    tool_use_id="t3",
                ),
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg2, state)
        assert len(alerts) >= 1
        alert = alerts[0]
        assert alert.pattern == "duplicate_tool_call"
        assert alert.severity == Severity.WARNING

    def test_different_inputs_no_alert(self, state):
        detector = DuplicateToolCallsDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/a.py"},
                    tool_use_id="t1",
                ),
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/b.py"},
                    tool_use_id="t2",
                ),
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_window_size_limit(self, state):
        detector = DuplicateToolCallsDetector({"enabled": True, "window_size": 3})
        # Fill window with different calls
        for i in range(4):
            msg = Message(
                uuid=f"m{i}",
                role="assistant",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_use",
                        tool_name="Read",
                        tool_input={"file_path": f"/file{i}.py"},
                        tool_use_id=f"t{i}",
                    )
                ],
                usage=TokenUsage(output_tokens=50),
            )
            detector.process_message(msg, state)

        # First call should have been evicted from window
        msg_old = Message(
            uuid="m_old",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/file0.py"},
                    tool_use_id="t_old",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg_old, state)
        # Should not alert since original call was evicted
        assert len(alerts) == 0


class TestRepetitiveReadsDetector:
    """Tests for repetitive file read detection."""

    def test_no_alert_on_first_read(self, state):
        detector = RepetitiveReadsDetector({"enabled": True, "min_reads": 3})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/config.json"},
                    tool_use_id="t1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        detector.process_message(msg, state)

        result_msg = Message(
            uuid="m2",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id="t1",
                    text='{"key": "value"}',
                )
            ],
        )
        alerts = detector.process_message(result_msg, state)
        assert len(alerts) == 0

    def test_alert_on_third_read(self, state):
        detector = RepetitiveReadsDetector({"enabled": True, "min_reads": 3})
        file_path = "/config.json"

        # Read same file 3 times
        for i in range(3):
            msg = Message(
                uuid=f"m{i}",
                role="assistant",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_use",
                        tool_name="Read",
                        tool_input={"file_path": file_path},
                        tool_use_id=f"t{i}",
                    )
                ],
                usage=TokenUsage(output_tokens=50),
            )
            detector.process_message(msg, state)

            result_msg = Message(
                uuid=f"r{i}",
                role="user",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_result",
                        tool_use_id=f"t{i}",
                        text='{"data": "x" * 100}',
                    )
                ],
            )
            alerts = detector.process_message(result_msg, state)

            if i == 2:  # Third read
                assert len(alerts) >= 1
                alert = alerts[0]
                assert alert.pattern == "repetitive_read"
                assert alert.details["file_path"] == file_path
                assert alert.details["read_count"] == 3
            else:
                assert len(alerts) == 0

    def test_different_files_no_alert(self, state):
        detector = RepetitiveReadsDetector({"enabled": True, "min_reads": 3})

        for i in range(3):
            msg = Message(
                uuid=f"m{i}",
                role="assistant",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_use",
                        tool_name="Read",
                        tool_input={"file_path": f"/file{i}.py"},
                        tool_use_id=f"t{i}",
                    )
                ],
                usage=TokenUsage(output_tokens=50),
            )
            detector.process_message(msg, state)

            result_msg = Message(
                uuid=f"r{i}",
                role="user",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_result",
                        tool_use_id=f"t{i}",
                        text="content",
                    )
                ],
            )
            alerts = detector.process_message(result_msg, state)
            assert len(alerts) == 0


class TestEditFragmentationDetector:
    """Tests for edit fragmentation detection."""

    def test_no_alert_on_single_edit(self, state):
        detector = EditFragmentationDetector({"enabled": True, "min_consecutive": 3})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={"file_path": "/main.py"},
                    tool_use_id="e1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_alert_on_consecutive_edits(self, state):
        detector = EditFragmentationDetector({"enabled": True, "min_consecutive": 3})
        file_path = "/main.py"

        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={"file_path": file_path},
                    tool_use_id=f"e{i}",
                )
                for i in range(3)
            ],
            usage=TokenUsage(output_tokens=150),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) >= 1
        alert = alerts[0]
        assert alert.pattern == "edit_fragmentation"
        assert alert.details["file_path"] == file_path
        assert alert.details["consecutive_edit_count"] >= 3

    def test_different_files_breaks_sequence(self, state):
        detector = EditFragmentationDetector({"enabled": True, "min_consecutive": 3})

        # Edit file1, file2, file1 - no sequence
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={"file_path": "/a.py"},
                    tool_use_id="e1",
                ),
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={"file_path": "/b.py"},
                    tool_use_id="e2",
                ),
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={"file_path": "/a.py"},
                    tool_use_id="e3",
                ),
            ],
            usage=TokenUsage(output_tokens=150),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0


class TestBashAntipatternDetector:
    """Tests for bash antipattern detection."""

    def test_cat_antipattern(self, state):
        detector = BashAntipatternDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "cat README.md"},
                    tool_use_id="b1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 1
        assert alerts[0].pattern == "bash_antipattern"
        assert "Read" in alerts[0].suggestion

    def test_grep_antipattern(self, state):
        detector = BashAntipatternDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "grep pattern file.txt"},
                    tool_use_id="b1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 1
        assert "Grep" in alerts[0].suggestion

    def test_find_antipattern(self, state):
        detector = BashAntipatternDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "find . -name '*.py'"},
                    tool_use_id="b1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 1
        assert "Glob" in alerts[0].suggestion

    def test_no_antipattern_normal_bash(self, state):
        detector = BashAntipatternDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "npm install"},
                    tool_use_id="b1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_severity_is_info(self, state):
        detector = BashAntipatternDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "cat file.txt"},
                    tool_use_id="b1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert alerts[0].severity == Severity.INFO


class TestFailedToolRetryDetector:
    """Tests for failed tool retry detection."""

    def test_error_marker_detection(self, state):
        detector = FailedToolRetryDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id="t1",
                    text="Error: File not found",
                )
            ],
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 1
        assert alerts[0].pattern == "failed_tool_retry"
        assert alerts[0].severity == Severity.CRITICAL

    def test_tool_use_error_marker(self, state):
        detector = FailedToolRetryDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id="t1",
                    text="<tool_use_error>Invalid input</tool_use_error>",
                )
            ],
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 1

    def test_success_no_alert(self, state):
        detector = FailedToolRetryDetector({"enabled": True})
        msg = Message(
            uuid="m1",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id="t1",
                    text="Successfully completed",
                )
            ],
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_multiple_error_markers(self, state):
        detector = FailedToolRetryDetector({"enabled": True})
        error_texts = [
            "Error: Permission denied",
            "File does not exist",
            "Exit code 1",
            "command not found",
        ]

        for i, error_text in enumerate(error_texts):
            msg = Message(
                uuid=f"m{i}",
                role="user",
                content_blocks=[
                    ContentBlock(
                        block_type="tool_result",
                        tool_use_id=f"t{i}",
                        text=error_text,
                    )
                ],
            )
            alerts = detector.process_message(msg, state)
            assert len(alerts) >= 1, f"Failed to detect error in: {error_text}"


class TestDetectorDisabling:
    """Tests for detector enable/disable functionality."""

    def test_disabled_detector_no_alerts(self, state):
        detector = DuplicateToolCallsDetector({"enabled": False})
        msg = Message(
            uuid="m1",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/test.py"},
                    tool_use_id="t1",
                )
            ],
            usage=TokenUsage(output_tokens=50),
        )
        alerts = detector.process_message(msg, state)
        assert len(alerts) == 0

    def test_all_detectors_can_be_disabled(self):
        detectors = [
            DuplicateToolCallsDetector({"enabled": False}),
            RepetitiveReadsDetector({"enabled": False}),
            EditFragmentationDetector({"enabled": False}),
            BashAntipatternDetector({"enabled": False}),
            FailedToolRetryDetector({"enabled": False}),
        ]

        for detector in detectors:
            assert not detector.config.get("enabled", True)
