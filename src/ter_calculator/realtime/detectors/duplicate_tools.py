"""Duplicate tool calls detector.

Detects identical tool invocations within a sliding window.
Ported from waste.py lines 173-213.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from .base import PatternDetector

if TYPE_CHECKING:
    from ...models import ContentBlock, Message
    from ..alerts.models import Alert
    from ..state import SessionState


class DuplicateToolCallsDetector(PatternDetector):
    """Detects identical tool invocations within a sliding window."""

    pattern_name = "duplicate_tool_call"

    def __init__(self, config: dict):
        super().__init__(config)
        self.window_size = config.get("window_size", 5)
        self.alert_on_each = config.get("alert_on_each", False)

    def process_message(
        self, message: "Message", state: "SessionState"
    ) -> list["Alert"]:
        """Check for duplicate tool calls in this message."""
        from ..alerts.models import Alert

        alerts = []

        # Only process assistant messages (tool_use blocks)
        if message.role != "assistant":
            return alerts

        # Extract tool_use blocks
        for block in message.content_blocks:
            if block.block_type != "tool_use":
                continue

            # Create signature: "ToolName{json_params}"
            signature = self._get_tool_signature(block)
            if not signature:
                continue

            # Check against recent window
            if signature in state.recent_tool_signatures:
                # Duplicate detected!
                count = state.tool_signature_counts.get(signature, 0) + 1
                state.tool_signature_counts[signature] = count

                # Estimate waste (tool call JSON + expected result)
                waste_tokens = len(signature) // 4 + 50  # Rough estimate
                state.total_waste_tokens += waste_tokens
                state.pattern_counts[self.pattern_name] = state.pattern_counts.get(
                    self.pattern_name, 0
                ) + 1

                # Alert on first duplicate or every occurrence based on config
                if self.alert_on_each or count == 2:
                    alerts.append(
                        Alert(
                            pattern=self.pattern_name,
                            severity="warning",
                            details={
                                "tool_signature": signature[:80],
                                "occurrence_count": count,
                                "estimated_waste_tokens": waste_tokens,
                            },
                            suggestion=f"Tool call appears {count}x. Result likely identical.",
                            timestamp=datetime.now(),
                        )
                    )

            # Add to rolling window
            state.recent_tool_signatures.append(signature)

        return alerts

    def _get_tool_signature(self, block: "ContentBlock") -> str:
        """Create unique signature from tool name + params.

        Matches the logic from waste.py but operates on ContentBlock instead of ClassifiedSpan.
        """
        parts = [block.tool_name or "unknown"]

        if block.tool_input:
            try:
                # Deterministic JSON for deduplication
                parts.append(json.dumps(block.tool_input, sort_keys=True))
            except (TypeError, ValueError):
                pass

        return "".join(parts)

    def get_default_config(self) -> dict:
        return {"window_size": 5, "alert_on_each": False}
