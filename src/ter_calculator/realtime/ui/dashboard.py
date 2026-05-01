"""Live terminal dashboard using rich.Live."""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..engine import RealtimeEngine
    from ..state import SessionState


class LiveDashboard:
    """Real-time terminal UI using rich.Live.

    Displays a 4-panel dashboard:
    - Header: Session ID and elapsed time
    - Metrics: Waste percentage progress bar
    - Patterns: Count table of detected patterns
    - Alerts: Recent alerts (last 5)
    """

    def __init__(self):
        """Initialize dashboard layout."""
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="metrics", size=6),
            Layout(name="patterns", size=12),
            Layout(name="alerts"),
        )

    def update(self, state: "SessionState"):
        """Refresh all dashboard panels with current state.

        Args:
            state: Current session state
        """
        # Header: Session ID + elapsed time
        elapsed = datetime.now() - state.start_time
        elapsed_str = (
            f"{int(elapsed.total_seconds() // 60)}m "
            f"{int(elapsed.total_seconds() % 60)}s"
        )

        header_text = Text.assemble(
            ("Session: ", "bold"),
            (state.session_id[:16], "cyan"),
            ("  |  Elapsed: ", ""),
            (elapsed_str, "yellow"),
        )
        self.layout["header"].update(Panel(header_text, border_style="blue"))

        # Metrics: Waste percentage progress bar
        waste_pct = state.waste_percentage()
        color = "red" if waste_pct > 10 else "yellow" if waste_pct > 5 else "green"

        metrics_table = Table.grid(padding=(0, 2))
        metrics_table.add_row(
            f"Waste: [{color}]{waste_pct:.1f}%[/{color}]",
            f"Total Output: {state.total_output_tokens:,}",
            f"Waste Tokens: {state.total_waste_tokens:,}",
        )

        progress = Progress(
            TextColumn("[bold]Waste Progress"),
            BarColumn(bar_width=40),
            TextColumn("{task.percentage:.1f}%"),
        )
        progress.add_task("", total=100, completed=min(waste_pct, 100))

        metrics_content = Table.grid()
        metrics_content.add_row(metrics_table)
        metrics_content.add_row(progress)

        self.layout["metrics"].update(
            Panel(metrics_content, title="[bold]Metrics", border_style="green")
        )

        # Patterns: Count table
        pattern_table = Table(show_header=True, show_edge=False)
        pattern_table.add_column("Pattern", style="bold")
        pattern_table.add_column("Count", justify="right", style="cyan")

        for pattern, count in sorted(state.pattern_counts.items()):
            pattern_name = pattern.replace("_", " ").title()
            pattern_table.add_row(pattern_name, str(count))

        if not state.pattern_counts:
            pattern_table.add_row("[dim]No patterns detected[/dim]", "")

        self.layout["patterns"].update(
            Panel(pattern_table, title="[bold]Detected Patterns", border_style="yellow")
        )

        # Alerts: Recent alerts (last 5)
        alert_table = Table(show_header=True, show_edge=False)
        alert_table.add_column("Time", style="dim", width=8)
        alert_table.add_column("Pattern", width=20)
        alert_table.add_column("Suggestion", width=50)

        recent_alerts = state.alerts[-5:] if state.alerts else []
        for alert in reversed(recent_alerts):  # Most recent first
            time_str = alert.timestamp.strftime("%H:%M:%S")
            severity = (
                alert.severity.value
                if hasattr(alert.severity, "value")
                else alert.severity
            )
            severity_color = {
                "info": "",
                "warning": "yellow",
                "critical": "red",
            }.get(severity, "")

            pattern_display = f"[{severity_color}]{alert.pattern.replace('_', ' ').title()}[/{severity_color}]"
            suggestion_short = alert.suggestion[:50]

            alert_table.add_row(time_str, pattern_display, suggestion_short)

        if not recent_alerts:
            alert_table.add_row("", "[dim]No alerts yet[/dim]", "")

        self.layout["alerts"].update(
            Panel(alert_table, title="[bold]Recent Alerts", border_style="red")
        )

    def run(self, engine: "RealtimeEngine", session_id: str, refresh_rate_hz: int = 4):
        """Run live dashboard until session ends.

        Args:
            engine: RealtimeEngine instance
            session_id: ID of session to monitor
            refresh_rate_hz: Update frequency in Hz (default 4)
        """
        with Live(self.layout, refresh_per_second=refresh_rate_hz, screen=True) as live:
            while session_id in engine.sessions:
                state = engine.sessions[session_id]
                self.update(state)
                time.sleep(1.0 / refresh_rate_hz)

    def render_snapshot(self, state: "SessionState") -> Layout:
        """Render a single snapshot of the dashboard.

        Useful for non-interactive display.

        Args:
            state: Session state to render

        Returns:
            Rendered Layout
        """
        self.update(state)
        return self.layout
