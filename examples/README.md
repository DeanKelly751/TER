# TER Real-Time Monitoring Examples

This directory contains example applications demonstrating TER's real-time waste detection capabilities.

## Examples

### `learning_demo.py` - Phase 3: Learning Loop Demo ⭐ NEW

**Demonstrates the complete adaptive learning system:**
- Real-time waste detection (5 patterns)
- Post-hoc analysis with embeddings (ground truth)
- Precision/recall feedback metrics
- Automatic threshold adjustment
- Multi-session learning

**Run:**
```bash
python examples/learning_demo.py
```

**What it does:**
1. Simulates wasteful sessions (repetitive reads, edit fragmentation, failed tools)
2. Runs post-hoc TER analysis with embeddings on each session
3. Compares real-time alerts to post-hoc WastePatterns
4. Computes precision (false positive rate) and recall (false negative rate)
5. After 5 sessions, automatically adjusts thresholds to improve accuracy

**Example output:**
```
SESSION #1
==========
📝 Simulating wasteful patterns...
⚠️ [RT] repetitive_read: config.json read 3x (450 waste tokens)...

📊 Real-Time Metrics:
  Alerts Generated: 3
  Waste %: 6.2%

🧠 Running post-hoc analysis + learning...

📈 Feedback Metrics:
  Precision: 100.00%  (0 false positives)
  Recall: 80.00%      (2 missed by real-time)
  F1 Score: 88.89%

✓ No threshold adjustments needed (need 4 more sessions)

SESSION #5
==========
...
🎯 Threshold Adjustments:
  patterns.repetitive_reads.min_reads: -1  (lowering to catch more)
```

**Learning behavior:**
- **High precision, low recall** → Lower thresholds (detect more, accept some false positives)
- **Low precision, high recall** → Raise thresholds (reduce false alarms)
- Adjustments capped at ±1 per session to prevent oscillation
- Learning history saved to `~/.ter/learning_history.jsonl`

---

### `realtime_demo.py` - Phase 1 + Phase 2 Demo

Demonstrates all real-time features:
- 5 embedding-free pattern detectors
- Desktop notifications (macOS/Linux/Windows)
- Alert callbacks
- Session lifecycle management
- Configuration system

**Run basic demo:**
```bash
cd TER
python examples/realtime_demo.py
```

**Run with live dashboard (experimental):**
```bash
python examples/realtime_demo.py --dashboard
```

**Disable desktop notifications:**
```bash
python examples/realtime_demo.py --no-notifications
```

### What the Demo Tests

The demo simulates a Claude API session with intentional waste patterns:

1. **Duplicate Tool Calls** - Reads same file twice
2. **Repetitive Reads** - Reads config file 4 times (triggers alert on 3rd)
3. **Edit Fragmentation** - Edits same file 4 times consecutively
4. **Bash Antipatterns** - Uses `cat`, `grep`, `find` instead of dedicated tools
5. **Failed Tool Retries** - Attempts to read non-existent files

### Expected Output

```
🚀 Starting TER real-time monitoring demo...
============================================================
Session ID: abc123...

1️⃣  Testing: Duplicate tool calls...
⚠️  ALERT: Duplicate Tool Call
   Tool call appears 2x. Result likely identical.

2️⃣  Testing: Repetitive reads...
⚠️  ALERT: Repetitive Read
   settings.yaml read 3x (450 waste tokens). Consider caching file contents.

...

📈 Final Session Metrics:
============================================================
Waste Percentage: 8.2%
Total Output Tokens: 1,200
Total Waste Tokens: 98

Pattern Counts:
  Duplicate Tool Call: 1
  Repetitive Read: 1
  Edit Fragmentation: 1
  Bash Antipattern: 3
  Failed Tool Retry: 2
```

### Desktop Notifications

If `plyer` is installed, you'll receive native desktop notifications for warning/critical alerts:

- **macOS**: Notification Center
- **Linux**: libnotify
- **Windows**: Toast notifications

### Configuration

The demo creates a config file at `~/.ter/config.yaml` on first run. You can customize:

```yaml
patterns:
  repetitive_reads:
    enabled: true
    min_reads: 3  # Adjust threshold

notifications:
  desktop_notifications: true
  severity_filter: ["warning", "critical"]  # Which alerts to show
```

### Files Created

After running the demo:

- `~/.ter/config.yaml` - Configuration
- `~/.ter/logs/{session_id}_alerts.jsonl` - Alert log
- `~/.ter/sessions/{session_id}.jsonl` - Session snapshot for post-hoc analysis

## Integration Example

To integrate TER into your own application:

```python
from ter_calculator.realtime import TERMonitor

# Initialize monitor
monitor = TERMonitor(
    on_alert=lambda alert: print(f"⚠️  {alert.suggestion}")
)

# Start session
session = monitor.start_session()

# In your Claude API loop:
response = anthropic.messages.create(
    model="claude-sonnet-4-5",
    messages=[...],
)

# Feed to TER (triggers real-time detection)
session.add_assistant_message(response)

# Process tool results
for block in response.content:
    if block.type == "tool_use":
        result = execute_tool(block)
        session.add_tool_result(block.id, result)

# Check for critical issues
if session.has_critical_alerts():
    print("WARNING: High waste detected!")

# End session
final_report = session.end()
print(f"Waste: {final_report['waste_percentage']:.1f}%")
```

## Requirements

```bash
pip install pyyaml plyer  # For full functionality
```

Or install TER with all dependencies:
```bash
pip install -e ".[dev]"
```
