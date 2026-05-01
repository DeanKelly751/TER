"""Bash antipatterns detector.

Detects Bash commands that should use dedicated tools.
Ported from waste.py lines 410-491.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from .base import PatternDetector

if TYPE_CHECKING:
    from ...models import Message
    from ..alerts.models import Alert
    from ..state import SessionState


class BashAntipatternDetector(PatternDetector):
    """Detects Bash commands that should use dedicated tools."""

    pattern_name = "bash_antipattern"

    # From waste.py lines 411-418
    ANTIPATTERN_RULES: list[tuple[re.Pattern, str, str]] = [
        (re.compile(r"(?:^|\|\s*)cat\s+"), "Read", "cat → Read"),
        (re.compile(r"(?:^|\|\s*)head\s+"), "Read", "head → Read"),
        (re.compile(r"(?:^|\|\s*)tail\s+"), "Read", "tail → Read"),
        (re.compile(r"(?:^|\|\s*)grep\s+"), "Grep", "grep → Grep"),
        (re.compile(r"(?:^|\|\s*)rg\s+"), "Grep", "rg → Grep"),
        (re.compile(r"^find\s+"), "Glob", "find → Glob"),
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.alert_threshold = config.get("alert_threshold", 1)

    def process_message(
        self, message: "Message", state: "SessionState"
    ) -> list["Alert"]:
        """Check for bash antipatterns."""
        from ..alerts.models import Alert

        alerts = []

        # Only process assistant messages (Bash tool_use blocks)
        if message.role != "assistant":
            return alerts

        # Scan for Bash tool_use blocks
        for block in message.content_blocks:
            if (
                block.block_type == "tool_use"
                and block.tool_name == "Bash"
                and block.tool_input
            ):
                command = block.tool_input.get("command", "").strip()
                if not command:
                    continue

                # Check against antipattern rules
                for pattern, recommended_tool, description in self.ANTIPATTERN_RULES:
                    if pattern.search(command):
                        # Record instance
                        state.bash_antipattern_instances.append(
                            {
                                "command": command,
                                "recommended_tool": recommended_tool,
                                "description": description,
                            }
                        )

                        count = len(state.bash_antipattern_instances)

                        # Estimate waste (bash invocation overhead)
                        waste_tokens = 20  # Conservative estimate
                        state.total_waste_tokens += waste_tokens
                        state.pattern_counts[self.pattern_name] = count

                        # Alert on each occurrence
                        alerts.append(
                            Alert(
                                pattern=self.pattern_name,
                                severity="info",
                                details={
                                    "command_snippet": command[:60],
                                    "recommended_tool": recommended_tool,
                                    "instance_count": count,
                                },
                                suggestion=(
                                    f"Use {recommended_tool} instead of Bash for better "
                                    f"performance and structured output."
                                ),
                                timestamp=datetime.now(),
                            )
                        )
                        break  # Only alert once per command

        return alerts

    def get_default_config(self) -> dict:
        return {"alert_threshold": 1}
