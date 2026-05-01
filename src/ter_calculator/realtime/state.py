"""Session state management for real-time pattern detection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from .alerts.models import Alert


@dataclass
class SessionState:
    """In-memory state for real-time pattern detection.

    Tracks all necessary information for the 5 embedding-free pattern detectors:
    1. Duplicate tool calls
    2. Repetitive reads
    3. Edit fragmentation
    4. Bash antipatterns
    5. Failed tool retries
    """

    session_id: str
    start_time: datetime = field(default_factory=datetime.now)

    # Pattern 1: Duplicate tool call tracking
    recent_tool_signatures: deque[str] = field(default_factory=lambda: deque(maxlen=10))
    tool_signature_counts: dict[str, int] = field(default_factory=dict)

    # Pattern 2: Repetitive read tracking
    file_read_counts: dict[str, int] = field(default_factory=dict)
    file_read_tokens: dict[str, list[int]] = field(default_factory=dict)
    tool_use_id_to_file: dict[str, str] = field(default_factory=dict)

    # Pattern 3: Edit fragmentation tracking
    edit_history: deque[tuple[str, str, float]] = field(
        default_factory=lambda: deque(maxlen=20)
    )
    # Structure: (file_path, tool_name, timestamp)

    # Pattern 4: Bash antipattern tracking
    bash_antipattern_instances: list[dict] = field(default_factory=list)

    # Pattern 5: Failed retry tracking
    failed_tool_ids: set[str] = field(default_factory=set)
    error_tool_results: list[dict] = field(default_factory=list)

    # Aggregated metrics
    total_waste_tokens: int = 0
    total_output_tokens: int = 0
    pattern_counts: dict[str, int] = field(default_factory=dict)
    alerts: list[Alert] = field(default_factory=list)

    # JSONL snapshot buffer for post-hoc analysis
    message_buffer: list[dict] = field(default_factory=list)

    def waste_percentage(self) -> float:
        """Calculate current waste percentage."""
        if self.total_output_tokens == 0:
            return 0.0
        return (self.total_waste_tokens / self.total_output_tokens) * 100

    def get_alert_counts_by_severity(self) -> dict[str, int]:
        """Count alerts by severity level."""
        counts = {"info": 0, "warning": 0, "critical": 0}
        for alert in self.alerts:
            severity = alert.severity.value if hasattr(alert.severity, 'value') else alert.severity
            counts[severity] = counts.get(severity, 0) + 1
        return counts
