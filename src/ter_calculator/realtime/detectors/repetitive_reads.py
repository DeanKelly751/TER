"""Repetitive reads detector.

Detects repeated Read tool calls to the same file.
Ported from waste.py lines 280-342.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .base import PatternDetector

if TYPE_CHECKING:
    from ...models import Message
    from ..alerts.models import Alert
    from ..state import SessionState


class RepetitiveReadsDetector(PatternDetector):
    """Detects repeated Read tool calls to the same file."""

    pattern_name = "repetitive_read"

    def __init__(self, config: dict):
        super().__init__(config)
        self.min_reads = config.get("min_reads", 3)
        self.alert_on_each = config.get("alert_on_each", False)

    def process_message(
        self, message: "Message", state: "SessionState"
    ) -> list["Alert"]:
        """Check for repetitive file reads."""
        from ..alerts.models import Alert

        alerts = []

        # Phase 1: Map tool_use_id → file_path for Read calls (assistant messages)
        if message.role == "assistant":
            for block in message.content_blocks:
                if (
                    block.block_type == "tool_use"
                    and block.tool_name == "Read"
                    and block.tool_use_id
                    and block.tool_input
                ):
                    file_path = block.tool_input.get("file_path")
                    if file_path:
                        state.tool_use_id_to_file[block.tool_use_id] = file_path

        # Phase 2: Process tool_result blocks (user messages)
        if message.role == "user":
            for block in message.content_blocks:
                if block.block_type == "tool_result" and block.tool_use_id:
                    file_path = state.tool_use_id_to_file.get(block.tool_use_id)
                    if not file_path:
                        continue

                    # Count read
                    state.file_read_counts[file_path] = (
                        state.file_read_counts.get(file_path, 0) + 1
                    )

                    # Estimate tokens
                    content = block.text or ""
                    tokens = max(1, len(content) // 4)
                    state.file_read_tokens.setdefault(file_path, []).append(tokens)

                    count = state.file_read_counts[file_path]

                    # Alert if threshold crossed
                    if count >= self.min_reads:
                        if self.alert_on_each or count == self.min_reads:
                            # First read is necessary; subsequent are waste
                            redundant_tokens = sum(state.file_read_tokens[file_path][1:])
                            state.total_waste_tokens += tokens  # This read's waste
                            state.pattern_counts[self.pattern_name] = (
                                state.pattern_counts.get(self.pattern_name, 0) + 1
                            )

                            short_name = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                            severity = "critical" if count >= 5 else "warning"

                            alerts.append(
                                Alert(
                                    pattern=self.pattern_name,
                                    severity=severity,
                                    details={
                                        "file_path": file_path,
                                        "file_name": short_name,
                                        "read_count": count,
                                        "estimated_waste_tokens": redundant_tokens,
                                    },
                                    suggestion=(
                                        f"{short_name} read {count}x "
                                        f"({redundant_tokens:,} waste tokens). "
                                        f"Consider caching file contents."
                                    ),
                                    timestamp=datetime.now(),
                                )
                            )

        return alerts

    def get_default_config(self) -> dict:
        return {"min_reads": 3, "alert_on_each": False}
