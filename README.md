# Real-Time Log Monitor & Alerting System

A complete, working prototype of a real-time log monitoring system — the kind of internal tool companies like Datadog, Grafana, or an in-house SRE team build to catch outages before customers notice.

## The Problem

In most companies, server logs just get written to a file and sit there. Nobody is watching them in real time, so when something breaks — a payment gateway timing out, a database connection pool exhausting — it can go unnoticed for minutes or hours, until a customer complains.

This project builds a full pipeline that catches that moment automatically: from raw logs, to structured storage, to a live dashboard, to an instant alert — turning a problem that could take hours to notice into one caught in seconds.

## Architecture

```
[Simulated Server] → writes logs to a file
       ↓
[Ingestion Pipeline] → parses & stores logs in SQLite
       ↓
[Live Dashboard] → shows error rate & status in real time (browser)
       ↓
[Alert Monitor] → fires an alert the instant an incident starts or ends
```

## Features

- **Realistic log simulation** — normal traffic plus randomly injected incidents (payment gateway timeouts, DB connection pool exhaustion, upstream service failures)
- **Structured ingestion** — tails the log file live and parses it into a queryable SQLite database
- **Live dashboard** — auto-refreshing web UI showing total logs, error rate, health status, and errors broken down by endpoint
- **Automatic alerting** — fires on incident start and resolution (not on every check, to avoid alert spam), with optional Slack webhook support

## Tech Stack

- **Language:** Python (standard library only — no external dependencies required)
- **Storage:** SQLite
- **Real-time updates:** Browser polling via a lightweight built-in HTTP server
- **Alerting:** Console output by default, with optional Slack Incoming Webhook support

## Project Structure

```
realtime-log-monitor/
├── README.md
├── .gitignore
├── log_generator.py       # Simulates a production server with realistic logs + incidents
├── log_ingestor.py        # Reads the log file and stores entries in SQLite
├── dashboard_server.py    # Serves the live dashboard at localhost:8000
├── alert_monitor.py       # Watches for incidents and fires alerts on state changes
├── query_example.py       # Example queries against the stored log data
└── screenshots/
    └── dashboard.png      # Live dashboard screenshot
```

## How to Run

```bash
# 1. Start the simulated server (writes logs)
python log_generator.py

# 2. Store logs into the database
python log_ingestor.py

# 3. Launch the live dashboard
python dashboard_server.py
# → open http://localhost:8000 in your browser

# 4. (Optional) Run the alert monitor in a separate terminal
python alert_monitor.py
```

Running the generator and ingestor simultaneously (in separate terminals) demonstrates the full real-time pipeline live, with the dashboard and alerts updating as new logs come in.

## Example Output

- **Dashboard:** live error rate, health status (Healthy / INCIDENT), and a breakdown of errors by endpoint, auto-refreshing every 2 seconds
- **Alerts:** `🔴 INCIDENT DETECTED - error rate is 80.0% over the last 20 requests` and `✅ RESOLVED - error rate back down to 0.0%`

## What I'd Improve With More Time

- Swap SQLite for a time-series database (InfluxDB/TimescaleDB) at scale
- Use a message queue (Kafka/Redis Streams) for higher-throughput ingestion
- Replace polling with WebSockets for lower-latency dashboard updates
- Add a statistical (rather than fixed-threshold) anomaly detector

## License

MIT
