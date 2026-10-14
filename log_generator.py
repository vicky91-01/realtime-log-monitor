"""
Phase 1: Simulated Production Server Log Generator
----------------------------------------------------
This script pretends to be a real application server.
It writes logs to a plain text file (logs/server.log),
just like most companies do before adding any monitoring.

Most of the time it produces normal traffic logs.
Every so often, it simulates a "problem" — a burst of errors,
like a payment service failing or a database timing out.

Run this, then open logs/server.log in another terminal with:
    tail -f logs/server.log
...to see logs appear in real time (the "old way" of watching logs).
"""

import time
import random
import os
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "server.log")

ENDPOINTS = ["/api/login", "/api/checkout", "/api/products", "/api/profile", "/api/payment"]

NORMAL_MESSAGES = [
    "Request completed successfully",
    "User authenticated",
    "Cache hit",
    "Database query executed",
]

ERROR_MESSAGES = [
    "500 Internal Server Error - Payment gateway timeout",
    "503 Service Unavailable - Database connection pool exhausted",
    "500 Internal Server Error - Unhandled exception in checkout flow",
    "502 Bad Gateway - Upstream service not responding",
]


def write_log(message, level="INFO", response_time_ms=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    endpoint = random.choice(ENDPOINTS)
    rt = response_time_ms if response_time_ms is not None else random.randint(20, 150)
    line = f"{timestamp} [{level}] {endpoint} - {message} - {rt}ms\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line.strip())


def simulate_normal_traffic():
    message = random.choice(NORMAL_MESSAGES)
    write_log(message, level="INFO")


def simulate_incident(duration_seconds=15):
    """Simulates a real outage: a burst of errors and slow responses,
    just like a payment service or database failing under load."""
    print("\n*** INCIDENT STARTED: simulating service degradation ***\n")
    end_time = time.time() + duration_seconds
    while time.time() < end_time:
        message = random.choice(ERROR_MESSAGES)
        slow_response = random.randint(2000, 8000)  # 2-8 seconds, very slow
        write_log(message, level="ERROR", response_time_ms=slow_response)
        time.sleep(0.3)
    print("\n*** INCIDENT ENDED: service recovered ***\n")


def main():
    print(f"Simulated server started. Writing logs to {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")

    tick = 0
    try:
        while True:
            simulate_normal_traffic()

            # Roughly every ~40-60 ticks, trigger a random incident
            tick += 1
            if tick > random.randint(40, 60):
                simulate_incident(duration_seconds=random.randint(10, 20))
                tick = 0

            time.sleep(random.uniform(0.2, 0.6))
    except KeyboardInterrupt:
        print("\nServer simulation stopped.")


if __name__ == "__main__":
    main()
