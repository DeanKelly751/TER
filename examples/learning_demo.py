"""Example: TER Learning Loop Demo

Demonstrates Phase 3: Post-hoc analysis and adaptive threshold learning.

This example:
1. Runs a wasteful session (real-time detection)
2. Performs post-hoc analysis with embeddings
3. Compares real-time alerts to post-hoc patterns
4. Computes precision/recall metrics
5. Auto-adjusts thresholds based on feedback

Run multiple times to see thresholds adapt over sessions!
"""

import sys
import time
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ter_calculator.models import ContentBlock, Message, TokenUsage
from ter_calculator.realtime import TERMonitor
from ter_calculator.realtime.client.config import UserConfig


def simulate_session_with_learning(monitor: TERMonitor, session_num: int):
    """Simulate a session with learning enabled."""

    print(f"\n{'='*60}")
    print(f"SESSION #{session_num}")
    print(f"{'='*60}\n")

    session = monitor.start_session()

    # Simulate various waste patterns
    print("📝 Simulating wasteful patterns...")

    # Pattern 1: Repetitive reads (will trigger on 3rd read)
    for i in range(4):
        msg = Message(
            uuid=f"s{session_num}-read-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Read",
                    tool_input={"file_path": "/data/config.json"},
                    tool_use_id=f"s{session_num}-r{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)

        result = Message(
            uuid=f"s{session_num}-result-{i}",
            role="user",
            content_blocks=[
                ContentBlock(
                    block_type="tool_result",
                    tool_use_id=f"s{session_num}-r{i}",
                    text='{"config": "data"}\n' * 30,
                )
            ],
        )
        session.add_user_message(result.__dict__)

    # Pattern 2: Edit fragmentation
    for i in range(4):
        msg = Message(
            uuid=f"s{session_num}-edit-{i}",
            role="assistant",
            content_blocks=[
                ContentBlock(
                    block_type="tool_use",
                    tool_name="Edit",
                    tool_input={
                        "file_path": "/src/main.py",
                        "old_string": f"old{i}",
                        "new_string": f"new{i}",
                    },
                    tool_use_id=f"s{session_num}-e{i}",
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        session.add_assistant_message(msg.__dict__)

    # Pattern 3: Failed tool retry
    msg = Message(
        uuid=f"s{session_num}-fail",
        role="assistant",
        content_blocks=[
            ContentBlock(
                block_type="tool_use",
                tool_name="Read",
                tool_input={"file_path": "/missing/file.py"},
                tool_use_id=f"s{session_num}-fail",
            )
        ],
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    )
    session.add_assistant_message(msg.__dict__)

    error = Message(
        uuid=f"s{session_num}-error",
        role="user",
        content_blocks=[
            ContentBlock(
                block_type="tool_result",
                tool_use_id=f"s{session_num}-fail",
                text="Error: File does not exist",
            )
        ],
    )
    session.add_user_message(error.__dict__)

    # Show real-time metrics
    status = session.get_status()
    print(f"\n📊 Real-Time Metrics:")
    print(f"  Alerts Generated: {len(status['recent_alerts'])}")
    print(f"  Waste %: {status['waste_percentage']:.1f}%")
    print(f"  Pattern Counts: {status['pattern_counts']}")

    # End session with learning
    print(f"\n🧠 Running post-hoc analysis + learning...")
    final_report = session.end(run_posthoc_analysis=True, enable_learning=True)

    # Display learning results
    if "feedback_metrics" in final_report:
        metrics = final_report["feedback_metrics"]
        print(f"\n📈 Feedback Metrics:")
        print(f"  Precision: {metrics['precision']:.2%}")
        print(f"  Recall: {metrics['recall']:.2%}")
        print(f"  F1 Score: {metrics['f1_score']:.2%}")
        print(f"  True Positives: {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")

        if final_report.get("threshold_adjustments"):
            print(f"\n🎯 Threshold Adjustments:")
            for key, delta in final_report["threshold_adjustments"].items():
                print(f"  {key}: {delta:+d}")
        else:
            print(f"\n✓ No threshold adjustments needed")

    if "learning_summary" in final_report:
        summary = final_report["learning_summary"]
        print(f"\n📚 Learning Summary:")
        print(f"  Sessions Analyzed: {summary['sessions_analyzed']}")
        if summary["sessions_analyzed"] >= 5:
            print(f"  Average Precision: {summary['average_precision']:.2%}")
            print(f"  Average Recall: {summary['average_recall']:.2%}")

    return final_report


def main():
    print("🚀 TER Learning Loop Demo")
    print("=" * 60)

    # Load or create config
    print("\n⚙️  Loading configuration...")
    try:
        config = UserConfig.load()
        print(f"✅ Loaded config from ~/.ter/config.yaml")

        # Show current thresholds
        patterns = config.patterns
        print(f"\n📋 Current Thresholds:")
        print(f"  Repetitive Reads: min_reads = {patterns['repetitive_reads']['min_reads']}")
        print(
            f"  Edit Fragmentation: min_consecutive = {patterns['edit_fragmentation']['min_consecutive']}"
        )

    except Exception as e:
        print(f"⚠️  Using default config: {e}")
        config = UserConfig(**UserConfig._get_defaults())

    # Create monitor
    def on_alert(alert):
        emoji = {"info": "ℹ️ ", "warning": "⚠️ ", "critical": "🚨"}
        severity = (
            alert.severity.value
            if hasattr(alert.severity, "value")
            else alert.severity
        )
        print(f"{emoji.get(severity, '')}[RT] {alert.pattern}: {alert.suggestion[:60]}")

    monitor = TERMonitor(config=config.to_dict(), on_alert=on_alert)

    # Run multiple sessions to demonstrate learning
    num_sessions = int(input("\nHow many sessions to run? (1-10): ") or "3")
    num_sessions = max(1, min(10, num_sessions))

    print(f"\n🔄 Running {num_sessions} session(s) with learning enabled...")
    print("Watch how thresholds adapt based on precision/recall!")

    for i in range(1, num_sessions + 1):
        simulate_session_with_learning(monitor, i)
        if i < num_sessions:
            print(f"\n⏸  Pausing before next session...")
            time.sleep(1)

    # Final summary
    print(f"\n{'='*60}")
    print("✨ Learning Demo Complete!")
    print(f"{'='*60}")

    print(f"\n💡 What Happened:")
    print(
        f"  - Each session generated real-time alerts (5 lightweight patterns)"
    )
    print(
        f"  - Post-hoc analysis ran full TER with embeddings (ground truth)"
    )
    print(f"  - Precision/recall compared real-time vs post-hoc")
    print(
        f"  - After {config.learning['min_sessions_before_adjust']} sessions, thresholds auto-adjust"
    )

    print(f"\n📁 Check these files:")
    print(f"  ~/.ter/config.yaml - Updated thresholds")
    print(f"  ~/.ter/learning_history.jsonl - Feedback metrics over time")
    print(f"  ~/.ter/sessions/ - Session snapshots for post-hoc analysis")

    print(f"\n🔁 Run this demo again to see continued learning!")


if __name__ == "__main__":
    main()
