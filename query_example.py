"""
Phase 2: Example Queries
-------------------------
This shows WHY storing logs in a database is better than a text file.
Run this any time after log_ingestor.py has stored some logs, and it
instantly answers questions that would take manual scrolling before.

Run: python query_example.py
"""

import sqlite3

DB_FILE = "logs.db"


def main():
    conn = sqlite3.connect(DB_FILE)

    total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    print(f"Total logs stored: {total}\n")

    print("--- All ERROR logs ---")
    errors = conn.execute(
        "SELECT timestamp, endpoint, message, response_ms FROM logs WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()
    for row in errors:
        print(row)

    print("\n--- Slowest 5 requests overall ---")
    slowest = conn.execute(
        "SELECT timestamp, endpoint, response_ms FROM logs ORDER BY response_ms DESC LIMIT 5"
    ).fetchall()
    for row in slowest:
        print(row)

    print("\n--- Error count per endpoint ---")
    per_endpoint = conn.execute(
        "SELECT endpoint, COUNT(*) as error_count FROM logs WHERE level = 'ERROR' GROUP BY endpoint ORDER BY error_count DESC"
    ).fetchall()
    for row in per_endpoint:
        print(row)

    conn.close()


if __name__ == "__main__":
    main()
