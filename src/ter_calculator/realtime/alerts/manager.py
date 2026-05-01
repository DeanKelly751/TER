"""Alert management and routing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .notifier import DesktopNotifier

if TYPE_CHECKING:
    from .models import Alert
    from ..state import SessionState

logger = logging.getLogger(__name__)


class AlertManager:
    """Routes alerts to appropriate handlers (desktop, UI, callbacks, logs)."""

    def __init__(self, notifications_config: dict):
        """Initialize alert manager.

        Args:
            notifications_config: Configuration for notifications
        """
        # Initialize desktop notifier
        self.desktop_notifier = DesktopNotifier(notifications_config)

        # User callbacks
        self.callbacks: list[Callable[[Alert], None]] = []

        # Alert deduplication
        self.recent_alerts: set[str] = set()

    def register_callback(self, callback: Callable[["Alert"], None]):
        """Register custom alert handler.

        Args:
            callback: Function that takes an Alert and processes it
        """
        self.callbacks.append(callback)

    def handle_alert(self, alert: "Alert", state: "SessionState"):
        """Dispatch alert to all handlers.

        Args:
            alert: The alert to handle
            state: Current session state
        """
        # Desktop notification
        self.desktop_notifier.send_alert(alert)

        # User callbacks
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}", exc_info=True)

        # Log to file
        self._log_alert(alert, state.session_id)

    def _log_alert(self, alert: "Alert", session_id: str):
        """Append alert to session log file.

        Args:
            alert: Alert to log
            session_id: Session identifier
        """
        try:
            log_dir = Path.home() / ".ter" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{session_id}_alerts.jsonl"

            with open(log_file, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")

        except Exception as e:
            logger.error(f"Failed to log alert to file: {e}", exc_info=True)
