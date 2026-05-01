"""Alert data models for real-time waste detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Severity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Real-time waste pattern alert."""

    pattern: str
    severity: Severity | str
    details: dict
    suggestion: str
    timestamp: datetime
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        """Convert string severity to enum if needed."""
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "pattern": self.pattern,
            "severity": self.severity.value if isinstance(self.severity, Severity) else self.severity,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "suggestion": self.suggestion,
        }

    def short_description(self) -> str:
        """One-line summary for notifications."""
        pattern_name = self.pattern.replace("_", " ").title()
        suggestion_short = self.suggestion[:80] + "..." if len(self.suggestion) > 80 else self.suggestion
        return f"{pattern_name}: {suggestion_short}"
