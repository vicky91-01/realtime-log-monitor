"""
Real-Time Log Monitor - Deployable Single-File App
------------------------------------------------------
This combines all 4 phases (generator, ingestor, dashboard, alerts)
into ONE program, so it can run on a free hosting platform like
Render, which expects a single process that stays running.

No external packages required - pure Python standard library, so
there's nothing to install on the host.

Three background pieces run inside this one process:
  1. A simulated server thread - writes logs directly to SQLite
     (combines what used to be log_generator.py + log_ingestor.py)
  2. An alert-checking thread - watches the error rate and stores
     alerts in memory (so they show up on the dashboard itself,
     since nobody can see a live server's console)
  3. An HTTP server - serves the dashboard webpage + JSON API

Run locally with:   python app.py
Then open:           http://localhost:8000

For deployment, the PORT environment variable (set automatically by
most hosting platforms) controls which port it listens on.
"""

import sqlite3
import time
import json
import random
import threading
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_FILE = "logs.db"
PORT = int(os.environ.get("PORT", 8000))

ENDPOINTS = ["/api/login", "/api/checkout", "/api/products", "/api/profile", "/api/payment"]
NORMAL_MESSAGES = ["Request completed successfully", "User authenticated", "Cache hit", "Database query executed"]
ERROR_MESSAGES = [
    "500 Internal Server Error - Payment gateway timeout",
    "503 Service Unavailable - Database connection pool exhausted",
    "500 Internal Server Error - Unhandled exception in checkout flow",
    "502 Bad Gateway - Upstream service not responding",
]

ERROR_THRESHOLD_PCT = 40
CHECK_WINDOW = 20

# Alerts are kept in memory (not the database) so the dashboard can
# show them even though nobody can see this server's console once deployed.
alerts_log = []
alerts_lock = threading.Lock()


def setup_database():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, level TEXT, endpoint TEXT, message TEXT, response_ms INTEGER
        )
    """)
    conn.commit()
    return conn


def add_alert(message):
    with alerts_lock:
        alerts_log.append({"time": datetime.now(timezone.utc).isoformat(), "message": message})
        # keep only the most recent 20 alerts
        del alerts_log[:-20]


def write_log(conn, lock, level, endpoint, message, response_ms):
    timestamp = datetime.now(timezone.utc).isoformat()
    with lock:
        conn.execute(
            "INSERT INTO logs (timestamp, level, endpoint, message, response_ms) VALUES (?, ?, ?, ?, ?)",
            (timestamp, level, endpoint, message, response_ms),
        )
        conn.commit()


def simulated_server_loop(conn, lock):
    """Background thread: acts like a real server, writing normal logs
    most of the time and periodically simulating a realistic incident."""
    tick = 0
    while True:
        endpoint = random.choice(ENDPOINTS)
        write_log(conn, lock, "INFO", endpoint, random.choice(NORMAL_MESSAGES), random.randint(20, 150))

        tick += 1
        if tick > random.randint(40, 60):
            # simulate an incident: a burst of errors + slow responses
            duration = random.randint(10, 20)
            end_time = time.time() + duration
            while time.time() < end_time:
                endpoint = random.choice(ENDPOINTS)
                write_log(conn, lock, "ERROR", endpoint, random.choice(ERROR_MESSAGES), random.randint(2000, 8000))
                time.sleep(0.3)
            tick = 0

        time.sleep(random.uniform(0.2, 0.6))


def alert_checker_loop(conn, lock):
    """Background thread: watches the error rate and records an alert
    whenever the system transitions into or out of an incident."""
    was_incident = False
    while True:
        with lock:
            rows = conn.execute(
                "SELECT level FROM logs ORDER BY id DESC LIMIT ?", (CHECK_WINDOW,)
            ).fetchall()

        if rows:
            error_count = sum(1 for (lvl,) in rows if lvl == "ERROR")
            error_rate = round(100 * error_count / len(rows), 1)
        else:
            error_rate = 0.0

        is_incident_now = error_rate >= ERROR_THRESHOLD_PCT
        if is_incident_now and not was_incident:
            add_alert(f"INCIDENT DETECTED - error rate is {error_rate}% over the last {CHECK_WINDOW} requests.")
        elif was_incident and not is_incident_now:
            add_alert(f"RESOLVED - error rate back down to {error_rate}%.")
        was_incident = is_incident_now

        time.sleep(2)


def get_stats(conn, lock):
    with lock:
        total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        recent_levels = conn.execute("SELECT level FROM logs ORDER BY id DESC LIMIT ?", (CHECK_WINDOW,)).fetchall()
        errors_by_endpoint = conn.execute(
            "SELECT endpoint, COUNT(*) FROM logs WHERE level='ERROR' GROUP BY endpoint ORDER BY COUNT(*) DESC"
        ).fetchall()
        recent = conn.execute(
            "SELECT timestamp, level, endpoint, response_ms FROM logs ORDER BY id DESC LIMIT 15"
        ).fetchall()

    if recent_levels:
        error_count = sum(1 for (lvl,) in recent_levels if lvl == "ERROR")
        error_rate_pct = round(100 * error_count / len(recent_levels), 1)
    else:
        error_rate_pct = 0

    with alerts_lock:
        recent_alerts = list(reversed(alerts_log[-10:]))

    return {
        "total": total,
        "error_rate_pct": error_rate_pct,
        "errors_by_endpoint": errors_by_endpoint,
        "recent": recent,
        "alerts": recent_alerts,
    }


DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Real-Time Log Monitor</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial, sans-serif; background: #111; color: #eee; padding: 20px; }
    h1 { color: #4CAF50; }
    .cards { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
    .card { background: #222; border-radius: 8px; padding: 20px; min-width: 160px; text-align: center; }
    .card .number { font-size: 32px; font-weight: bold; }
    .ok { color: #4CAF50; } .warn { color: #FFC107; } .danger { color: #F44336; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #1a1a1a; }
    th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
    th { color: #999; }
    .ERROR { color: #F44336; } .INFO { color: #4CAF50; }
    #status { font-size: 14px; color: #888; }
    .alert-row { color: #FFC107; }
  </style>
</head>
<body>
  <h1>Real-Time Log Monitor</h1>
  <div id="status">Connecting...</div>

  <div class="cards">
    <div class="card"><div class="number" id="total">-</div>Total Logs</div>
    <div class="card"><div class="number" id="errorRate">-</div>Error Rate (last 20)</div>
    <div class="card"><div class="number" id="alertBox">-</div>Status</div>
  </div>

  <h3>Recent Alerts</h3>
  <table id="alertsTable"><tbody></tbody></table>

  <h3>Errors by Endpoint</h3>
  <table id="endpointTable"><tbody></tbody></table>

  <h3>Recent Logs</h3>
  <table id="recentTable"><tbody></tbody></table>

  <script>
    async function refreshData() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('status').innerText = 'Live - last updated ' + new Date().toLocaleTimeString();
        document.getElementById('total').innerText = data.total;

        const errorRate = data.error_rate_pct;
        const rateEl = document.getElementById('errorRate');
        rateEl.innerText = errorRate + '%';
        rateEl.className = 'number ' + (errorRate > 40 ? 'danger' : errorRate > 10 ? 'warn' : 'ok');

        const alertEl = document.getElementById('alertBox');
        if (errorRate > 40) { alertEl.innerText = 'INCIDENT!'; alertEl.className = 'number danger'; }
        else { alertEl.innerText = 'Healthy'; alertEl.className = 'number ok'; }

        document.querySelector('#alertsTable tbody').innerHTML = data.alerts.map(
          a => `<tr class="alert-row"><td>${new Date(a.time).toLocaleTimeString()}</td><td>${a.message}</td></tr>`
        ).join('') || '<tr><td colspan="2">No alerts yet</td></tr>';

        document.querySelector('#endpointTable tbody').innerHTML = data.errors_by_endpoint.map(
          row => `<tr><td>${row[0]}</td><td>${row[1]} errors</td></tr>`
        ).join('');

        document.querySelector('#recentTable tbody').innerHTML = data.recent.map(
          row => `<tr><td>${new Date(row[0]).toLocaleTimeString()}</td><td class="${row[1]}">${row[1]}</td><td>${row[2]}</td><td>${row[3]}ms</td></tr>`
        ).join('');
      } catch (e) {
        document.getElementById('status').innerText = 'Waiting for data...';
      }
    }
    refreshData();
    setInterval(refreshData, 2000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    conn = None
    lock = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/api/stats":
            stats = get_stats(self.conn, self.lock)
            body = json.dumps(stats).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))


def main():
    conn = setup_database()
    lock = threading.Lock()

    DashboardHandler.conn = conn
    DashboardHandler.lock = lock

    threading.Thread(target=simulated_server_loop, args=(conn, lock), daemon=True).start()
    threading.Thread(target=alert_checker_loop, args=(conn, lock), daemon=True).start()

    print(f"Dashboard running on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
