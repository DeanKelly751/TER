# TER Tutorials

This guide covers the two main ways to use TER:

1. **Post-Hoc Analysis** - Analyze completed sessions from JSONL files
2. **Real-Time Monitoring** - Prevent waste during active Claude API sessions

---

## Tutorial 1: Post-Hoc Analysis

**Use when:** You have completed Claude Code session JSONL files and want to analyze efficiency.

### Step 1: Install TER

```bash
cd TER
pip install -e .
```

### Step 2: Locate Session Files

Claude Code saves sessions to `~/.claude/projects/`:

```bash
# List recent sessions
ter list ~/.claude/projects/

# Output:
# abc123-session.jsonl (45.2 KB, 2 hours ago)
# def456-session.jsonl (128.5 KB, 1 day ago, 3 subagents)
```

### Step 3: Analyze a Session

```bash
# Basic analysis
ter analyze ~/.claude/projects/abc123-session.jsonl

# Output:
# TER Report: abc123-session
# ════════════════════════════════════════
# 
# TER: 0.94  |  Waste: 8.5%  |  Cost: $3.21  |  Waste $: $0.12
# Drift: stable  |  Alignment: 0.78  |  Redundancy: 0%  |  User: 15%
# 
# Phases:     Reasoning  Tool Use  Generation
#             0.98       0.87      1.00
# 
# Output Tokens: 42,150  (aligned: 38,567  waste: 3,583)
# 
# Waste Breakdown:
#   Source                      Tokens     %       Cost
#   Duplicate Tool Calls           450   12.6%   $0.0068
#   Repetitive File Reads          320    8.9%   $0.0048
#   ...
```

### Step 4: Grouped Analysis (Sessions with Subagents)

```bash
# Analyze parent + all subagents together
ter analyze ~/.claude/projects/def456-session.jsonl --group

# Output includes aggregate TER weighted by tokens
```

### Step 5: Generate Markdown Report

```bash
# Human-readable summary
ter report ~/.claude/projects/abc123-session.jsonl -o report.md

# Creates report.md with:
# - TER score and waste %
# - Cost breakdown
# - Top waste patterns
# - Actionable recommendations
```

### Step 6: Compare Sessions

```bash
# Compare multiple sessions
ter compare session1.jsonl session2.jsonl session3.jsonl --sort ter

# Before/after comparison
ter compare before.jsonl after.jsonl --baseline
```

### Advanced Options

```bash
# JSON output for programmatic use
ter analyze session.jsonl --format json > results.json

# Adjust thresholds
ter analyze session.jsonl \
  --similarity-threshold 0.50 \
  --confidence-threshold 0.80 \
  --phase-weights 0.2,0.5,0.3

# Custom cost model
ter analyze session.jsonl --cost-model "3.0,15.0,0.30,3.75"
# Format: input,output,cache_read,cache_write (per MTok)
```

---

## Tutorial 2: Real-Time Monitoring

**Use when:** You're running Claude API calls and want to prevent waste as it happens.

### Step 1: Install with Real-Time Dependencies

```bash
cd TER
pip install -e .

# Verify dependencies
python -c "import yaml, plyer; print('✓ Dependencies OK')"
```

### Step 2: Basic Integration

Create a file `my_claude_app.py`:

```python
import anthropic
from ter_calculator.realtime import TERMonitor

# Initialize Anthropic client
client = anthropic.Anthropic()

# Initialize TER monitor
monitor = TERMonitor(
    on_alert=lambda alert: print(f"⚠️  {alert.suggestion}")
)

# Start monitoring session
session = monitor.start_session()

# Your Claude conversation
messages = [{"role": "user", "content": "Analyze this codebase..."}]

while True:
    # Call Claude API
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=messages,
    )
    
    # Feed to TER for real-time detection
    session.add_assistant_message(response)
    
    # Process tool calls
    if response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "tool_use":
                # Execute tool (your implementation)
                result = execute_tool(block.name, block.input)
                
                # Report result to TER
                session.add_tool_result(block.id, result)
                
                # Also add to conversation
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }]
                })
    else:
        break  # Conversation complete

# End session and get metrics
final_report = session.end()
print(f"\n✅ Session complete!")
print(f"Waste: {final_report['waste_percentage']:.1f}%")
print(f"Patterns detected: {final_report['pattern_counts']}")
```

Run it:

```bash
python my_claude_app.py
```

**You'll see real-time alerts like:**
```
⚠️  config.json read 3x (450 waste tokens). Consider caching file contents.
⚠️  4 consecutive edits to utils.py. Consider batching changes.
🚨 Tool call failed. Check paths/permissions. 2 total failures this session.
```

### Step 3: Enable Desktop Notifications

Notifications are enabled by default. Configure via `~/.ter/config.yaml`:

```yaml
notifications:
  desktop_notifications: true
  severity_filter: ["warning", "critical"]  # info, warning, or critical
  sound_enabled: false
```

**Notification examples:**
- macOS: Notification Center
- Linux: libnotify desktop notifications
- Windows: Toast notifications

### Step 4: Enable Learning Loop

Update your app to run post-hoc analysis and learning:

```python
# End session with learning
final_report = session.end(
    run_posthoc_analysis=True,  # Run full TER with embeddings
    enable_learning=True,        # Adjust thresholds based on feedback
)

# Check learning results
if "feedback_metrics" in final_report:
    metrics = final_report["feedback_metrics"]
    print(f"\n📈 Learning Metrics:")
    print(f"  Precision: {metrics['precision']:.2%}")
    print(f"  Recall: {metrics['recall']:.2%}")
    print(f"  F1 Score: {metrics['f1_score']:.2%}")

if "threshold_adjustments" in final_report:
    print(f"\n🎯 Threshold Adjustments:")
    for key, delta in final_report["threshold_adjustments"].items():
        print(f"  {key}: {delta:+d}")
```

**What happens:**
1. Real-time alerts generated during session (5 lightweight patterns)
2. At session end, full TER analysis runs with embeddings (ground truth)
3. System compares real-time vs post-hoc to compute precision/recall
4. After 5+ sessions, thresholds auto-adjust to improve accuracy

**Learning behavior:**
- **High precision, low recall** → Lower thresholds (detect more patterns)
- **Low precision, high recall** → Raise thresholds (reduce false alarms)
- Adjustments capped at ±1 per session for stability

### Step 5: Configure Detection Patterns

Edit `~/.ter/config.yaml` to customize:

```yaml
patterns:
  # Enable/disable individual patterns
  duplicate_tool_calls:
    enabled: true
    window_size: 5        # Look back N tool calls
    alert_on_each: false  # Alert once or every time?
  
  repetitive_reads:
    enabled: true
    min_reads: 3          # Alert after Nth read of same file
    alert_on_each: false
  
  edit_fragmentation:
    enabled: true
    min_consecutive: 3    # Alert after N consecutive edits
  
  bash_antipatterns:
    enabled: true         # Flags: cat→Read, grep→Grep, find→Glob
  
  failed_tool_retries:
    enabled: true         # Detects error results

# Learning system
learning:
  enabled: true
  auto_adjust_thresholds: true
  min_sessions_before_adjust: 5  # Wait N sessions before adjusting
  target_precision: 0.80          # Target: 80% precision
  target_recall: 0.70             # Target: 70% recall
  max_adjustment_per_session: 1   # Max ±1 per session
```

### Step 6: Optional Live Dashboard

For visual monitoring during development:

```python
from ter_calculator.realtime.ui import LiveDashboard

# Create dashboard
dashboard = LiveDashboard()

# In a separate thread, run live updates
import threading

def run_dashboard():
    dashboard.run(monitor.engine, session.session_id)

dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
dashboard_thread.start()

# Your Claude API loop runs in main thread...
```

**Dashboard shows:**
- Session ID and elapsed time
- Waste percentage (color-coded: green/yellow/red)
- Pattern counts table
- Last 5 alerts

### Troubleshooting

**"Desktop notifications not working"**
```bash
# Install plyer
pip install plyer

# On Linux, may need libnotify
sudo apt-get install libnotify-bin
```

**"PyYAML not found"**
```bash
pip install pyyaml
```

**"Real-time detection too sensitive"**
```yaml
# In ~/.ter/config.yaml, raise thresholds:
patterns:
  repetitive_reads:
    min_reads: 4  # Was 3
  edit_fragmentation:
    min_consecutive: 4  # Was 3
```

**"Real-time missing patterns"**
- Enable learning: `enable_learning=True`
- After 5+ sessions, system will auto-lower thresholds if recall is low
- Or manually lower in config.yaml

---

## Common Workflows

### Workflow 1: Post-hoc session review

```bash
# Analyze yesterday's sessions
ter list ~/.claude/projects/ --limit 10
ter analyze ~/.claude/projects/session-abc123.jsonl
ter report ~/.claude/projects/session-abc123.jsonl -o report.md
```

### Workflow 2: Real-time + learning

```python
# Integrate TER into your app
monitor = TERMonitor()
session = monitor.start_session()

# ... your Claude API loop ...

# End with learning
session.end(run_posthoc_analysis=True, enable_learning=True)
```

### Workflow 3: Compare before/after

```bash
# Test a prompt change
ter analyze before-prompt.jsonl > before.txt
# ... change prompt ...
ter analyze after-prompt.jsonl > after.txt

# Or use baseline mode
ter compare before-prompt.jsonl after-prompt.jsonl --baseline
```

---

## Files Created by TER

**Post-hoc mode:**
- (None - reads existing JSONL files)

**Real-time mode:**
- `~/.ter/config.yaml` - User configuration
- `~/.ter/sessions/*.jsonl` - Session snapshots for post-hoc analysis
- `~/.ter/logs/*_alerts.jsonl` - Alert logs per session
- `~/.ter/learning_history.jsonl` - Feedback metrics over time

---

## Next Steps

- **Post-hoc:** Explore other flags with `ter analyze --help`
- **Real-time:** Run `python examples/realtime_demo.py` to see it in action
- **Learning:** Run `python examples/learning_demo.py` to see adaptive thresholds

For implementation details, see [REALTIME_IMPLEMENTATION.md](REALTIME_IMPLEMENTATION.md).
