"""
Phase 4: Instant Alerting (Nobody Has To Be Watching)
--------------------------------------------------------
Right now, someone has to be staring at the dashboard to notice a
problem. This script fixes that: it watches logs.db in the background
and automatically sends an alert the SECOND an incident starts - and
another one when it ends.

TWO MODES:
  1. CONSOLE MODE (default, no setup needed) - just prints alerts to
     your screen. Good for testing everything works first.
  2. SLACK MODE (optional) - sends a real message to a Slack channel.
     To enable: paste your Slack "Incoming Webhook" URL into
     SLACK_WEBHOOK_URL below. (Ask me for step-by-step help getting
     one if you want this part.)

HOW TO USE:
  1. python log_generator.py    (creates logs)
  2. python log_ingestor.py     (stores logs into logs.db)
  3. python alert_monitor.py    (this file - watches for trouble)
"""

import sqlite3
import time
import json
import urllib.request

DB_FILE = "logs.db"

# Leave this as "" to just print alerts to your screen (console mode).
# To use real Slack alerts, paste your webhook URL between the quotes.
SLACK_WEBHOOK_URL = ""

# If this % or more of the last CHECK_WINDOW logs are errors, it's an incident.
ERROR_THRESHOLD_PCT = 40
CHECK_WINDOW = 20
CHECK_INTERVAL_SECONDS = 2


def get_error_rate():
    """Returns (error_rate_pct, total_logs_seen) for the most recent logs."""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT level FROM logs ORDER BY id DESC LIMIT ?", (CHECK_WINDOW,)
    ).fetchall()
    total_seen = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    conn.close()

    if not rows:
        return 0.0, total_seen

    error_count = sum(1 for (lvl,) in rows if lvl == "ERROR")
    rate = round(100 * error_count / len(rows), 1)
    return rate, total_seen


def send_alert(message):
    """Sends the alert either to Slack (if configured) or just prints it."""
    print(f"\n>>> ALERT: {message}\n")

    if not SLACK_WEBHOOK_URL:
        return  # console-only mode, nothing more to do

    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        print("(Slack message sent successfully)")
    except Exception as e:
        print(f"(Could not send to Slack: {e})")


def main():
    print("Alert monitor started.")
    print(f"Watching logs.db - will alert if error rate crosses {ERROR_THRESHOLD_PCT}%")
    if not SLACK_WEBHOOK_URL:
        print("(Running in CONSOLE mode - no Slack webhook set yet)")
    print("Press Ctrl+C to stop.\n")

    was_incident = False
    last_total_seen = -1

    try:
        while True:
            try:
                error_rate, total_seen = get_error_rate()
            except sqlite3.OperationalError:
                # logs.db doesn't exist yet - just wait
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            is_incident_now = error_rate >= ERROR_THRESHOLD_PCT

            # Only alert on a CHANGE of state, not every single check -
            # otherwise you'd get spammed every 2 seconds during an outage.
            if is_incident_now and not was_incident:
                send_alert(
                    f"🔴 INCIDENT DETECTED - error rate is {error_rate}% "
                    f"over the last {CHECK_WINDOW} requests. Investigate immediately."
                )
            elif was_incident and not is_incident_now:
                send_alert(
                    f"✅ RESOLVED - error rate back down to {error_rate}%. "
                    f"Service appears to have recovered."
                )
            elif total_seen != last_total_seen:
                # quiet heartbeat so you know it's alive without spamming alerts
                print(f"Monitoring... total logs seen: {total_seen}, current error rate: {error_rate}%")

            was_incident = is_incident_now
            last_total_seen = total_seen
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nAlert monitor stopped.")


if __name__ == "__main__":
    main()
