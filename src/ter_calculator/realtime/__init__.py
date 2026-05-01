"""Real-time TER monitoring system.

This package provides real-time waste pattern detection for Claude Code sessions
using lightweight, embedding-free algorithms.
"""

from .alerts.models import Alert, Severity
from .client.monitor import TERMonitor, TERSession
from .engine import RealtimeEngine
from .state import SessionState

__all__ = [
    "Alert",
    "Severity",
    "RealtimeEngine",
    "SessionState",
    "TERMonitor",
    "TERSession",
]
