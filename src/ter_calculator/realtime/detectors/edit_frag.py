"""Edit fragmentation detector.

Detects consecutive Edit/Write operations to the same file.
Ported from waste.py lines 345-407.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from .base import PatternDetector

if TYPE_CHECKING:
    from collections import deque

    from ...models import Message
    from ..alerts.models import Alert
    from ..state import SessionState


class EditFragmentationDetector(PatternDetector):
    """Detects consecutive Edit/Write operations to the same file."""

    pattern_name = "edit_fragmentation"

    def __init__(self, config: dict):
        super().__init__(config)
        self.min_consecutive = config.get("min_consecutive", 3)

    def process_message(
        self, message: "Message", state: "SessionState"
    ) -> list["Alert"]:
        """Check for consecutive edits to the same file."""
        from ..alerts.models import Alert

        alerts = []

        # Only process assistant messages (Edit/Write tool_use blocks)
        if message.role != "assistant":
            return alerts

        # Extract Edit/Write operations
        for block in message.content_blocks:
            if (
                block.block_type == "tool_use"
                and block.tool_name in ("Edit", "Write")
                and block.tool_input
            ):
                file_path = block.tool_input.get("file_path")
                if not file_path:
                    continue

                timestamp = time.time()
                state.edit_history.append((file_path, block.tool_name, timestamp))

                # Check for consecutive edits to same file
                consecutive_run = self._find_consecutive_run(
                    state.edit_history, file_path
                )

                if len(consecutive_run) >= self.min_consecutive:
                    # Only alert once when threshold crossed
                    if len(consecutive_run) == self.min_consecutive:
                        # Estimate waste: all but first edit are fragmentation
                        waste_tokens = (len(consecutive_run) - 1) * 100  # Rough estimate
                        state.total_waste_tokens += waste_tokens
                        state.pattern_counts[self.pattern_name] = (
                            state.pattern_counts.get(self.pattern_name, 0) + 1
                        )

                        short_name = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                        alerts.append(
                            Alert(
                                pattern=self.pattern_name,
                                severity="warning",
                                details={
                                    "file_path": file_path,
                                    "file_name": short_name,
                                    "consecutive_edit_count": len(consecutive_run),
                                    "estimated_waste_tokens": waste_tokens,
                                },
                                suggestion=(
                                    f"{len(consecutive_run)} consecutive edits to {short_name}. "
                                    f"Consider batching changes into single operation."
                                ),
                                timestamp=datetime.now(),
                            )
                        )

        return alerts

    def _find_consecutive_run(
        self, history: deque[tuple[str, str, float]], target_file: str
    ) -> list[tuple]:
        """Find most recent consecutive edits to target file."""
        run = []
        for file_path, tool_name, ts in reversed(history):
            if file_path == target_file:
                run.insert(0, (file_path, tool_name, ts))
            else:
                break  # Consecutive run broken
        return run

    def get_default_config(self) -> dict:
        return {"min_consecutive": 3}
