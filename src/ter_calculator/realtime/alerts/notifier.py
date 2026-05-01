"""Desktop notification system using plyer."""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Alert

logger = logging.getLogger(__name__)

# Try to import plyer, but make it optional
try:
    from plyer import notification

    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    logger.warning(
        "plyer not installed. Desktop notifications disabled. "
        "Install with: pip install plyer"
    )


class DesktopNotifier:
    """Send desktop notifications via plyer (cross-platform)."""

    def __init__(self, config: dict):
        """Initialize desktop notifier.

        Args:
            config: Notification configuration dict with:
                - enabled: bool
                - severity_filter: list of severity levels to notify
                - sound_enabled: bool
        """
        self.enabled = config.get("enabled", True) and PLYER_AVAILABLE
        self.severity_filter = set(config.get("severity_filter", ["warning", "critical"]))
        self.sound_enabled = config.get("sound_enabled", False)

        # Platform detection for fallback
        self.platform = platform.system()

        if self.enabled:
            logger.info(f"Desktop notifier initialized for {self.platform}")
        else:
            logger.info("Desktop notifications disabled")

    def send_alert(self, alert: "Alert"):
        """Send desktop notification for alert.

        Args:
            alert: Alert to send notification for
        """
        if not self.enabled:
            return

        # Check severity filter
        severity = alert.severity.value if hasattr(alert.severity, "value") else alert.severity
        if severity not in self.severity_filter:
            return

        try:
            # Format notification
            title = self._format_title(alert)
            message = alert.suggestion[:200]  # Limit message length

            # Send notification
            notification.notify(
                title=title,
                message=message,
                app_name="TER Monitor",
                timeout=10,  # seconds
            )

            logger.debug(f"Sent desktop notification: {alert.pattern}")

        except Exception as e:
            # Fallback to terminal bell if notification fails
            logger.warning(f"Desktop notification failed: {e}")
            if self.sound_enabled:
                self._terminal_bell()

    def _format_title(self, alert: "Alert") -> str:
        """Format notification title based on severity."""
        severity = alert.severity.value if hasattr(alert.severity, "value") else alert.severity
        pattern_name = alert.pattern.replace("_", " ").title()

        emoji_map = {
            "info": "ℹ️ ",
            "warning": "⚠️ ",
            "critical": "🚨",
        }

        emoji = emoji_map.get(severity, "")
        return f"{emoji} TER Alert: {pattern_name}"

    @staticmethod
    def _terminal_bell():
        """Emit terminal bell sound as fallback."""
        print("\a", end="", flush=True)
