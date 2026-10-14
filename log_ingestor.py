"""
Phase 2: Log Ingestion Pipeline
--------------------------------
This script watches logs/server.log (created by Phase 1) as new lines
get added, and stores each one into a real database (SQLite) instead
of leaving it as plain text.

Why this matters: once logs are in a database, you can instantly
search/filter them, e.g. "show me all errors in the last 5 minutes" —
instead of scrolling through a text file by hand.

Run Phase 1's log_generator.py in one terminal, then run this script
in another terminal (in the same folder as the logs/ directory).
"""

import sqlite3
import time
import re
import os

LOG_FILE = os.path.join("logs", "server.log")
DB_FILE = "logs.db"

# Matches lines like:
# 2026-09-26T19:06:19.906675 [ERROR] /api/profile - message text - 4487ms
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+) \[(?P<level>\w+)\] (?P<endpoint>\S+) - (?P<message>.+) - (?P<response_ms>\d+)ms$"
)


def setup_database():
    """Creates the logs table if it doesn't already exist."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            endpoint TEXT,
            message TEXT,
            response_ms INTEGER
        )
    """)
    conn.commit()
    return conn


def parse_line(line):
    """Turns one raw text log line into structured fields, or returns
    None if the line doesn't match (e.g. blank lines, incident banners)."""
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None
    data = match.groupdict()
    data["response_ms"] = int(data["response_ms"])
    return data


def follow_file(filepath):
    """Like the 'tail -f' command: waits for the log file to exist,
    then yields new lines as they get written, forever."""
    while not os.path.exists(filepath):
        print(f"Waiting for {filepath} to be created (start log_generator.py first)...")
        time.sleep(1)

    with open(filepath, "r") as f:
        # Start from the BEGINNING of the file, so any logs already
        # written (even if the generator already stopped) get processed.
        # After catching up, it keeps watching for any new lines too.
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line


def main():
    conn = setup_database()
    print(f"Ingestion started. Reading from {LOG_FILE}, storing into {DB_FILE}")
    print("Press Ctrl+C to stop.\n")

    inserted_count = 0
    try:
        for raw_line in follow_file(LOG_FILE):
            parsed = parse_line(raw_line)
            if parsed is None:
                continue  # skip banners like "*** INCIDENT STARTED ***"

            conn.execute(
                "INSERT INTO logs (timestamp, level, endpoint, message, response_ms) VALUES (?, ?, ?, ?, ?)",
                (parsed["timestamp"], parsed["level"], parsed["endpoint"], parsed["message"], parsed["response_ms"]),
            )
            conn.commit()
            inserted_count += 1
            print(f"Stored #{inserted_count}: [{parsed['level']}] {parsed['endpoint']} - {parsed['response_ms']}ms")
    except KeyboardInterrupt:
        print(f"\nIngestion stopped. Total logs stored: {inserted_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
