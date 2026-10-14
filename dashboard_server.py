"""
Phase 3: Live Dashboard (The Visual Payoff)
---------------------------------------------
This turns your project into something you can literally WATCH in a
web browser, updating automatically — no manual query scripts needed.

This uses ONLY built-in Python (no extra installs), so it's simple to
run: it reads logs.db (created by Phase 2's log_ingestor.py) and
serves a webpage that refreshes itself every 2 seconds.

HOW TO USE (3 things running together):
  1. python log_generator.py   (creates logs)
  2. python log_ingestor.py    (stores logs into logs.db)
  3. python dashboard_server.py (this file - shows them live)

Then open your browser to: http://localhost:8000
"""

import sqlite3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_FILE = "logs.db"
PORT = 8000

# The webpage itself. JavaScript here calls /api/stats every 2 seconds
# and updates the numbers on screen - that's what makes it "live".
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Log Monitor Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; background: #111; color: #eee; padding: 20px; }
    h1 { color: #4CAF50; }
    .cards { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
    .card { background: #222; border-radius: 8px; padding: 20px; min-width: 160px; text-align: center; }
    .card .number { font-size: 32px; font-weight: bold; }
    .ok { color: #4CAF50; }
    .warn { color: #FFC107; }
    .danger { color: #F44336; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #1a1a1a; }
    th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
    th { color: #999; }
    .ERROR { color: #F44336; }
    .INFO { color: #4CAF50; }
    #status { font-size: 14px; color: #888; }
  </style>
</head>
<body>
  <h1>Live Log Monitor Dashboard</h1>
  <div id="status">Connecting...</div>

  <div class="cards">
    <div class="card"><div class="number" id="total">-</div>Total Logs</div>
    <div class="card"><div class="number" id="errorRate">-</div>Error Rate (last 20)</div>
    <div class="card"><div class="number" id="alertBox">-</div>Status</div>
  </div>

  <h3>Errors by Endpoint</h3>
  <table id="endpointTable"><tbody></tbody></table>

  <h3>Recent Logs</h3>
  <table id="recentTable"><tbody></tbody></table>

  <script>
    async function refreshData() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        document.getElementById('status').innerText =
          'Live - last updated ' + new Date().toLocaleTimeString();

        document.getElementById('total').innerText = data.total;

        const errorRate = data.error_rate_pct;
        const rateEl = document.getElementById('errorRate');
        rateEl.innerText = errorRate + '%';
        rateEl.className = 'number ' + (errorRate > 40 ? 'danger' : errorRate > 10 ? 'warn' : 'ok');

        const alertEl = document.getElementById('alertBox');
        if (errorRate > 40) {
          alertEl.innerText = 'INCIDENT!';
          alertEl.className = 'number danger';
        } else {
          alertEl.innerText = 'Healthy';
          alertEl.className = 'number ok';
        }

        const epBody = document.querySelector('#endpointTable tbody');
        epBody.innerHTML = data.errors_by_endpoint.map(
          row => `<tr><td>${row[0]}</td><td>${row[1]} errors</td></tr>`
        ).join('');

        const recentBody = document.querySelector('#recentTable tbody');
        recentBody.innerHTML = data.recent.map(
          row => `<tr><td>${row[0]}</td><td class="${row[1]}">${row[1]}</td><td>${row[2]}</td><td>${row[3]}ms</td></tr>`
        ).join('');
      } catch (e) {
        document.getElementById('status').innerText = 'Waiting for data... (' + e + ')';
      }
    }
    refreshData();
    setInterval(refreshData, 2000);
  </script>
</body>
</html>
"""


def get_stats():
    """Reads logs.db and returns a summary dict, ready to turn into JSON."""
    conn = sqlite3.connect(DB_FILE)

    total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]

    # Error rate over the most recent 20 logs - this is what "detects"
    # an incident: if a big chunk of recent traffic is errors, something
    # is currently wrong.
    recent_levels = conn.execute(
        "SELECT level FROM logs ORDER BY id DESC LIMIT 20"
    ).fetchall()
    if recent_levels:
        error_count = sum(1 for (lvl,) in recent_levels if lvl == "ERROR")
        error_rate_pct = round(100 * error_count / len(recent_levels), 1)
    else:
        error_rate_pct = 0

    errors_by_endpoint = conn.execute(
        "SELECT endpoint, COUNT(*) FROM logs WHERE level='ERROR' GROUP BY endpoint ORDER BY COUNT(*) DESC"
    ).fetchall()

    recent = conn.execute(
        "SELECT timestamp, level, endpoint, response_ms FROM logs ORDER BY id DESC LIMIT 15"
    ).fetchall()

    conn.close()
    return {
        "total": total,
        "error_rate_pct": error_rate_pct,
        "errors_by_endpoint": errors_by_endpoint,
        "recent": recent,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # keep the terminal quiet - no need to print every request

    def do_GET(self):
        if self.path == "/api/stats":
            try:
                stats = get_stats()
                body = json.dumps(stats).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            except sqlite3.OperationalError:
                # logs.db doesn't exist yet - send empty stats instead of crashing
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "total": 0, "error_rate_pct": 0, "errors_by_endpoint": [], "recent": []
                }).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))


def main():
    print(f"Dashboard running! Open this in your browser: http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")
    server = HTTPServer(("localhost", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
