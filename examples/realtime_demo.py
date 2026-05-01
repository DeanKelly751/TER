"""Example: Real-time TER monitoring with visual alerts.

This demonstrates Phase 1 + Phase 2 features:
- Real-time waste detection (5 patterns)
- Desktop notifications
- Alert callbacks
- Session metrics

To run with live dashboard (requires terminal):
    python examples/realtime_demo.py --dashboard

To run with just alerts:
    python examples/realtime_demo.py
"""

import argparse
import time
from pathlib import Path

# Add src to path for development
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ter_calculator.models import ContentBlock, Message, TokenUsage
from ter_calculator.realtime import TERMonitor
from ter_calculator.realtime.alerts import AlertManager
from ter_calculator.realtime.client.config import UserConfig
from ter_calculator.realtime.detectors import get_enabled_detectors
from ter_calculator.realtime.engine import RealtimeEngine
from ter_calculator.realtime.ui import LiveDashboard


def simulate_wasteful_session(monitor: TERMonitor, use_dashboard: bool = False):
    """Simulate a Claude API session with intentional waste patterns."""

    print("\n🚀 Starting TER real-time monitoring demo...")
    print("=" * 60)

    session = monitor.start_session()
    print(f"Session ID: {session.session_id}\n")

    # Create dashboard if requested
    dashboard = None
    if use_dashboard:
        dashboard = LiveDashboard()
        print("📊 Live dashboard enabled (updating in background)\n")

    # Simulate messages with various waste patterns

    # 1. Duplicate tool calls (read same file twice)
    print("1️⃣  Testing: Duplicate tool calls...")
    for i in range(2):
        msg = Message(
            uuid=f"msg-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/src/main.py"},
                    tool_use_id=f"tool-{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)
        time.sleep(0.5)

    # 2. Repetitive reads (read same file 4 times)
    print("2️⃣  Testing: Repetitive reads...")
    for i in range(4):
        # Tool use
        msg = Message(
            uuid=f"msg-read-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/config/settings.yaml"},
                    tool_use_id=f"read-{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)

        # Tool result
        result_msg = Message(
            uuid=f"result-read-{i}",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id=f"read-{i}",
                    text="config_data = {'key': 'value'}\n" * 20,  # Simulate file content
                )
            ],
        )
        session.add_user_message(result_msg.__dict__)
        time.sleep(0.5)

    # 3. Edit fragmentation (edit same file 4 times)
    print("3️⃣  Testing: Edit fragmentation...")
    for i in range(4):
        msg = Message(
            uuid=f"msg-edit-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={
                        "file_path": "/src/utils.py",
                        "old_string": f"line{i}",
                        "new_string": f"newline{i}",
                    },
                    tool_use_id=f"edit-{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)
        time.sleep(0.5)

    # 4. Bash antipatterns
    print("4️⃣  Testing: Bash antipatterns...")
    for cmd in ["cat /src/file.py", "grep pattern /logs/app.log", "find . -name '*.py'"]:
        msg = Message(
            uuid=f"msg-bash-{cmd[:3]}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Bash",
                    tool_input={"command": cmd},
                    tool_use_id=f"bash-{cmd[:3]}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)
        time.sleep(0.5)

    # 5. Failed tool retries
    print("5️⃣  Testing: Failed tool retries...")
    for i in range(2):
        # Tool use
        msg = Message(
            uuid=f"msg-fail-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/nonexistent/file.py"},
                    tool_use_id=f"fail-{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)

        # Error result
        error_msg = Message(
            uuid=f"result-fail-{i}",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id=f"fail-{i}",
                    text="Error: File does not exist",
                )
            ],
        )
        session.add_user_message(error_msg.__dict__)
        time.sleep(0.5)

    # Show final status
    print("\n" + "=" * 60)
    print("📈 Final Session Metrics:")
    print("=" * 60)

    status = session.get_status()
    print(f"Waste Percentage: {status['waste_percentage']:.1f}%")
    print(f"Total Output Tokens: {status['total_output_tokens']:,}")
    print(f"Total Waste Tokens: {status['total_waste_tokens']:,}")
    print(f"\nPattern Counts:")
    for pattern, count in status['pattern_counts'].items():
        print(f"  {pattern.replace('_', ' ').title()}: {count}")

    print(f"\nAlert Counts by Severity:")
    for severity, count in status['alert_counts_by_severity'].items():
        print(f"  {severity.title()}: {count}")

    # End session
    final_report = session.end()
    print(f"\n✅ Session ended. Snapshot saved to:")
    print(f"   {final_report['snapshot_path']}")

    return final_report


def main():
    parser = argparse.ArgumentParser(description="TER Real-time Monitoring Demo")
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show live terminal dashboard (experimental)",
    )
    parser.add_argument(
        "--no-notifications",
        action="store_true",
        help="Disable desktop notifications",
    )
    args = parser.parse_args()

    # Load configuration
    print("⚙️  Loading configuration...")
    try:
        config = UserConfig.load()
        print(f"✅ Loaded config from ~/.ter/config.yaml")
    except Exception as e:
        print(f"⚠️  Using default config: {e}")
        config = UserConfig(**UserConfig._get_defaults())

    # Optionally disable notifications
    if args.no_notifications:
        config.notifications["desktop_notifications"] = False
        print("🔕 Desktop notifications disabled")

    # Create alert callback
    def on_alert(alert):
        severity_emoji = {"info": "ℹ️ ", "warning": "⚠️ ", "critical": "🚨"}
        emoji = severity_emoji.get(
            alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
            "",
        )
        print(f"\n{emoji} ALERT: {alert.pattern.replace('_', ' ').title()}")
        print(f"   {alert.suggestion}")

    # Initialize TER monitor
    monitor = TERMonitor(config=config.to_dict(), on_alert=on_alert)

    # Run simulation
    simulate_wasteful_session(monitor, use_dashboard=args.dashboard)

    print("\n✨ Demo complete!")
    print("\n💡 Tips:")
    print("  - Check ~/.ter/logs/ for alert logs")
    print("  - Check ~/.ter/sessions/ for JSONL snapshots")
    print("  - Adjust config at ~/.ter/config.yaml")


if __name__ == "__main__":
    main()
