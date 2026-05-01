"""Integration tests for real-time TER monitoring (embedding-free detectors)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from ter_calculator.models import ContentBlock, Message, TokenUsage
from ter_calculator.realtime import Severity, TERMonitor
from ter_calculator.realtime.detectors import get_enabled_detectors
from ter_calculator.realtime.engine import RealtimeEngine


def _engine_all_detectors() -> RealtimeEngine:
    patterns = {
        "duplicate_tool_calls": {"enabled": True},
        "repetitive_reads": {"enabled": True},
        "edit_fragmentation": {"enabled": True},
        "bash_antipatterns": {"enabled": True},
        "failed_tool_retries": {"enabled": True},
    }
    return RealtimeEngine(detectors=get_enabled_detectors(patterns))


def _assistant_tool_msg(
    blocks: list[ContentBlock],
    *,
    msg_uuid: str = "m-assist",
    output_tokens: int = 500,
) -> Message:
    return Message(
        uuid=msg_uuid,
        role="assistant",
        content_blocks=blocks,
        usage=TokenUsage(output_tokens=output_tokens),
    )


def _user_tool_results(blocks: list[ContentBlock], *, msg_uuid: str = "m-user") -> Message:
    return Message(uuid=msg_uuid, role="user", content_blocks=blocks)


@pytest.fixture
def tmp_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_duplicate_tool_call_detector():
    engine = _engine_all_detectors()
    sid = engine.start_session("dup-session").session_id
    dup_input = {"file_path": "/project/readme.md"}
    # First occurrence primes the window; alerts emit when the same signature is seen
    # twice as a duplicate (internal count reaches 2), which requires a third identical call.
    blocks = [
        ContentBlock(
            block_type="tool_use",
            tool_name="Read",
            tool_input=dup_input,
            tool_use_id=f"tu-{i}",
        )
        for i in range(3)
    ]
    msg = _assistant_tool_msg(blocks)
    alerts = engine.process_message(sid, msg)
    patterns = {a.pattern for a in alerts}
    assert "duplicate_tool_call" in patterns
    assert any(a.severity == Severity.WARNING for a in alerts)


def test_repetitive_reads_detector():
    engine = _engine_all_detectors()
    sid = engine.start_session("read-session").session_id
    assist = _assistant_tool_msg(
        [
            ContentBlock(
                block_type="tool_use",
                tool_name="Read",
                tool_input={"file_path": "/tmp/repeat.txt"},
                tool_use_id=f"r{i}",
            )
            for i in range(3)
        ]
    )
    engine.process_message(sid, assist)
    user = _user_tool_results(
        [
            ContentBlock(
                block_type="tool_result",
                text="line " * 40,
                tool_use_id=f"r{i}",
            )
            for i in range(3)
        ]
    )
    alerts = engine.process_message(sid, user)
    assert any(a.pattern == "repetitive_read" for a in alerts)
    rep = next(a for a in alerts if a.pattern == "repetitive_read")
    assert rep.details.get("read_count") == 3
    assert rep.severity in (Severity.WARNING, Severity.CRITICAL)


def test_edit_fragmentation_detector():
    engine = _engine_all_detectors()
    sid = engine.start_session("edit-session").session_id
    fp = "/src/module.py"
    msg = _assistant_tool_msg(
        [
            ContentBlock(
                block_type="tool_use",
                tool_name="Edit",
                tool_input={"file_path": fp},
                tool_use_id=f"e{i}",
            )
            for i in range(3)
        ]
    )
    alerts = engine.process_message(sid, msg)
    assert any(a.pattern == "edit_fragmentation" for a in alerts)


def test_bash_antipattern_detector():
    engine = _engine_all_detectors()
    sid = engine.start_session("bash-session").session_id
    msg = _assistant_tool_msg(
        [
            ContentBlock(
                block_type="tool_use",
                tool_name="Bash",
                tool_input={"command": "cat README.md"},
                tool_use_id="b1",
            )
        ]
    )
    alerts = engine.process_message(sid, msg)
    assert any(a.pattern == "bash_antipattern" for a in alerts)
    bash_alert = next(a for a in alerts if a.pattern == "bash_antipattern")
    assert bash_alert.severity == Severity.INFO


def test_failed_tool_retry_detector():
    engine = _engine_all_detectors()
    sid = engine.start_session("fail-session").session_id
    user = _user_tool_results(
        [
            ContentBlock(
                block_type="tool_result",
                text="Error: no such file",
                tool_use_id="failed-1",
            )
        ]
    )
    alerts = engine.process_message(sid, user)
    assert any(a.pattern == "failed_tool_retry" for a in alerts)
    assert all(a.severity == Severity.CRITICAL for a in alerts if a.pattern == "failed_tool_retry")


def test_session_lifecycle_status_and_counts():
    engine = _engine_all_detectors()
    sid = engine.start_session("life-session").session_id
    engine.process_message(
        sid,
        _assistant_tool_msg(
            [
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "grep foo bar.txt"},
                    tool_use_id="g1",
                )
            ]
        ),
    )
    st = engine.get_status(sid)
    assert st["session_id"] == sid
    assert "elapsed_seconds" in st
    assert "alert_counts_by_severity" in st
    assert st["alert_counts_by_severity"]["info"] >= 1
    assert isinstance(st["recent_alerts"], list)


def test_jsonl_snapshot_roundtrip(tmp_path: Path):
    engine = _engine_all_detectors()
    sid = engine.start_session("snap-session").session_id
    msg = _assistant_tool_msg(
        [
            ContentBlock(
                block_type="text",
                text="hello",
            )
        ],
        msg_uuid="uuid-123",
    )
    engine.process_message(sid, msg)
    out = engine.end_session(sid, output_dir=tmp_path)
    assert out.exists()
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["type"] == "assistant"
    assert row["uuid"] == "uuid-123"
    assert row["message"]["role"] == "assistant"


def test_ter_monitor_client(tmp_home: Path):
    seen: list = []

    def on_alert(a):
        seen.append(a)

    monitor = TERMonitor(on_alert=on_alert)
    session = monitor.start_session("client-sess")
    session.add_assistant_message(
        {
            "id": "api-1",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": "bash-x",
                    "input": {"command": "find . -name '*.py'"},
                }
            ],
            "usage": {"output_tokens": 50},
        }
    )
    assert seen and seen[0].pattern == "bash_antipattern"
    assert session.has_critical_alerts() is False
    status = session.get_status()
    assert status["total_output_tokens"] == 50

    result = session.end()
    assert "snapshot_path" in result
    snap = Path(result["snapshot_path"])
    assert snap.is_relative_to(tmp_home)
    assert snap.read_text()


def test_process_message_latency_budget():
    """All detectors stay embedding-free; single-message processing should be well under 100ms."""
    engine = _engine_all_detectors()
    # One message that exercises duplicate + edit frag + bash in the same turn
    blocks = [
        ContentBlock(
            block_type="tool_use",
            tool_name="Read",
            tool_input={"file_path": "/x"},
            tool_use_id="p1",
        ),
        ContentBlock(
            block_type="tool_use",
            tool_name="Read",
            tool_input={"file_path": "/x"},
            tool_use_id="p2",
        ),
        ContentBlock(
            block_type="tool_use",
            tool_name="Edit",
            tool_input={"file_path": "/y.py"},
            tool_use_id="e1",
        ),
        ContentBlock(
            block_type="tool_use",
            tool_name="Edit",
            tool_input={"file_path": "/y.py"},
            tool_use_id="e2",
        ),
        ContentBlock(
            block_type="tool_use",
            tool_name="Edit",
            tool_input={"file_path": "/y.py"},
            tool_use_id="e3",
        ),
        ContentBlock(
            block_type="tool_use",
            tool_name="Bash",
            tool_input={"command": "rg pattern"},
            tool_use_id="b1",
        ),
    ]
    msg = _assistant_tool_msg(blocks, output_tokens=1000)

    durations: list[float] = []
    for i in range(30):
        sid = engine.start_session(f"perf-{i}").session_id
        t0 = time.perf_counter()
        engine.process_message(sid, msg)
        durations.append(time.perf_counter() - t0)

    median = sorted(durations)[len(durations) // 2]
    assert median < 0.1, f"median process_message latency {median:.4f}s exceeds 100ms budget"


def test_alert_to_dict_schema():
    engine = _engine_all_detectors()
    sid = engine.start_session("dict-session").session_id
    alerts = engine.process_message(
        sid,
        _assistant_tool_msg(
            [
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": "cat x"},
                    tool_use_id="c1",
                )
            ]
        ),
    )
    assert alerts
    d = alerts[0].to_dict()
    for key in ("alert_id", "pattern", "severity", "timestamp", "details", "suggestion"):
        assert key in d
    assert d["severity"] in ("info", "warning", "critical")
