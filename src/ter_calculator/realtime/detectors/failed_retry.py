"""Failed tool retries detector.

Detects tool calls that fail and are retried.
Ported from waste.py lines 494-558.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .base import PatternDetector

if TYPE_CHECKING:
    from ...models import ContentBlock, Message
    from ..alerts.models import Alert
    from ..state import SessionState


class FailedToolRetryDetector(PatternDetector):
    """Detects tool calls that fail and are retried."""

    pattern_name = "failed_tool_retry"

    # From waste.py lines 551-558
    ERROR_MARKERS = [
        "<tool_use_error>",
        "Error:",
        "Exit code 1",
        "File does not exist",
        "command not found",
        "No such file or directory",
        "Permission denied",
        "File has not been read yet",
    ]

    def __init__(self, config: dict):
        super().__init__(config)

    def process_message(
        self, message: "Message", state: "SessionState"
    ) -> list["Alert"]:
        """Check for failed tool calls."""
        from ..alerts.models import Alert

        alerts = []

        # Only process user messages (tool_result blocks)
        if message.role != "user":
            return alerts

        # Scan for error tool_result blocks
        for block in message.content_blocks:
            if block.block_type == "tool_result" and block.tool_use_id:
                content = block.text or ""

                # Check for error markers
                is_error = self._is_error_result(block)

                if is_error:
                    state.failed_tool_ids.add(block.tool_use_id)
                    state.error_tool_results.append(
                        {
                            "tool_use_id": block.tool_use_id,
                            "content_snippet": content[:100],
                        }
                    )

                    # Estimate waste: failed tool call + error result context
                    waste_tokens = len(content) // 4 + 30
                    state.total_waste_tokens += waste_tokens
                    state.pattern_counts[self.pattern_name] = len(state.failed_tool_ids)

                    alerts.append(
                        Alert(
                            pattern=self.pattern_name,
                            severity="critical",
                            details={
                                "tool_use_id": block.tool_use_id,
                                "error_snippet": content[:100],
                                "failed_tool_count": len(state.failed_tool_ids),
                                "estimated_waste_tokens": waste_tokens,
                            },
                            suggestion=(
                                f"Tool call failed. Check paths/permissions. "
                                f"{len(state.failed_tool_ids)} total failures this session."
                            ),
                            timestamp=datetime.now(),
                        )
                    )

        return alerts

    def _is_error_result(self, block: "ContentBlock") -> bool:
        """Check if a tool_result block indicates an error.

        From waste.py lines 543-558.
        """
        text = block.text or ""

        # Check for explicit error markers
        for marker in self.ERROR_MARKERS:
            if marker in text:
                return True

        return False

    def get_default_config(self) -> dict:
        return {}
