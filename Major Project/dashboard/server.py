#!/usr/bin/env python3
"""
Sales BI Platform — Live Dashboard API Server
Serves the dashboard UI and a JSON API backed by the pipeline CSV exports.
Also simulates new orders every 15 seconds to demonstrate real-time updates.

Usage:
    python dashboard/server.py

Then open: http://localhost:8765
"""

from __future__ import annotations

import csv
import json
import random
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
DASH_DIR  = Path(__file__).resolve().parent
EXPORTS   = ROOT / "powerbi" / "exports"
DATA_DIR  = ROOT / "data"
SRC_DIR   = ROOT / "src"

PORT = 8765

# ── Simulation state ───────────────────────────────────────────────────────
_lock             = threading.Lock()
_simulation_lock  = threading.Lock()
_pipeline_lock    = threading.Lock()
_sim_order_counter = 1006          # next simulated order number
_sim_log: list[dict] = []          # rolling log of simulated events

PRODUCTS = [
    {"id": "P-100", "name": "Analytics Gateway",   "category": "Hardware",  "price": 39_999, "cost": 24_000, "gst_rate_pct": 18},
    {"id": "P-200", "name": "BI Starter License",  "category": "Software",  "price": 9_999, "cost": 3_000, "gst_rate_pct": 18},
    {"id": "P-300", "name": "Implementation Pack", "category": "Services",  "price": 74_999, "cost": 45_000, "gst_rate_pct": 18},
]
REGION_STATES = {
    "East": ["Assam", "Odisha", "West Bengal"],
    "North": ["Delhi", "Haryana", "Punjab", "Uttar Pradesh"],
    "South": ["Karnataka", "Kerala", "Tamil Nadu", "Telangana"],
    "West": ["Gujarat", "Maharashtra", "Rajasthan"],
}
STATE_REGIONS = {state: region for region, states in REGION_STATES.items() for state in states}
STATES = list(STATE_REGIONS)
CHANNELS = ["Online", "Retail", "Distributor", "Direct"]

# ── Helpers ────────────────────────────────────────────────────────────────

def _initialize_sim_order_counter() -> None:
    """Continue simulated order numbering after a server restart."""
    global _sim_order_counter
    csv_path = DATA_DIR / "sales_online.csv"
    if not csv_path.exists():
        return

    largest_order_number = _sim_order_counter - 1
    with csv_path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            order_id = row.get("order_id", "")
            if order_id.startswith("SO-") and order_id[3:].isdigit():
                largest_order_number = max(largest_order_number, int(order_id[3:]))

    with _lock:
        _sim_order_counter = largest_order_number + 1


def _read_csv_as_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _format_indian_number(value: int) -> str:
    digits = str(value)
    if len(digits) <= 3:
        return digits
    prefix = digits[:-3]
    groups = []
    while len(prefix) > 2:
        groups.insert(0, prefix[-2:])
        prefix = prefix[:-2]
    groups.insert(0, prefix)
    return ",".join(groups + [digits[-3:]])


def _settings():
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from bi_dashboard.config import Settings

    settings = Settings(data_dir=DATA_DIR, output_dir=EXPORTS)
    if not settings.database_path.is_absolute():
        settings.database_path = ROOT / settings.database_path
    return settings


def _build_api_payload() -> dict:
    """Assemble the full API response from all export CSVs."""
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from bi_dashboard.database import read_sales_records

    settings = _settings()
    with _pipeline_lock:
        kpi     = _read_csv_as_list(EXPORTS / "kpi_summary.csv")
        daily   = _read_csv_as_list(EXPORTS / "sales_daily.csv")
        region  = _read_csv_as_list(EXPORTS / "sales_by_region.csv")
        state   = _read_csv_as_list(EXPORTS / "sales_by_state.csv")
        channel = _read_csv_as_list(EXPORTS / "sales_by_channel.csv")
        product = _read_csv_as_list(EXPORTS / "sales_by_product.csv")
        alerts  = _read_csv_as_list(EXPORTS / "alerts.csv")
        runs    = _read_csv_as_list(EXPORTS / "pipeline_runs.csv")
        transactions = read_sales_records(settings.database_path)
    with _lock:
        recent = list(_sim_log[-20:])   # last 20 simulated events

    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "kpi":         kpi[0] if kpi else {},
        "daily":       daily,
        "region":      region,
        "state":       state,
        "channel":     channel,
        "product":     product,
        "alerts":      alerts,
        "pipeline":    runs[0] if runs else {},
        "transactions": transactions,
        "live_events":  recent,
        "thresholds": {
            "minimum_margin_pct": settings.minimum_margin_pct,
            "minimum_daily_revenue": settings.minimum_daily_revenue,
        },
    }


def _run_pipeline() -> None:
    """Re-run the Python pipeline to refresh exports."""
    settings = _settings()
    from bi_dashboard.pipeline import run_pipeline

    with _pipeline_lock:
        result = run_pipeline(settings)
    print(f"[pipeline] Refreshed — {result['rows_loaded']} rows, "
          f"{len(result['alerts'])} alert(s)")


def _simulate_order() -> None:
    """Append a synthetic order to data/sales_online.csv and re-run pipeline."""
    global _sim_order_counter
    p     = random.choice(PRODUCTS)
    qty   = random.randint(1, 5)
    state = random.choice(STATES)
    reg   = STATE_REGIONS[state]
    chan  = random.choice(CHANNELS)
    today = datetime.now().strftime("%Y-%m-%d")
    cust  = f"C-{random.randint(100, 999)}"

    with _lock:
        order_id = f"SO-{_sim_order_counter}"
        _sim_order_counter += 1

    row = {
        "order_id":   order_id,
        "order_date": today,
        "region":     reg,
        "state":      state,
        "channel":    chan,
        "category":   p["category"],
        "product_id": p["id"],
        "product_name": p["name"],
        "customer_id": cust,
        "quantity":   qty,
        "unit_price": p["price"],
        "unit_cost":  p["cost"],
        "gst_rate_pct": p["gst_rate_pct"],
    }

    csv_path = DATA_DIR / "sales_online.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    revenue = qty * p["price"]
    gst_amount = round(revenue * p["gst_rate_pct"] / 100, 2)
    profit  = qty * (p["price"] - p["cost"])
    event = {
        "order_id":     order_id,
        "time":         datetime.now().strftime("%H:%M:%S"),
        "product":      p["name"],
        "state":        state,
        "region":       reg,
        "channel":      chan,
        "qty":          qty,
        "revenue":      revenue,
        "gst_amount":   gst_amount,
        "total_with_gst": revenue + gst_amount,
        "gross_profit": profit,
    }

    with _simulation_lock:
        file_is_empty = not csv_path.exists() or csv_path.stat().st_size == 0
        needs_newline = False
        if not file_is_empty:
            with csv_path.open("rb") as source:
                source.seek(-1, 2)
                needs_newline = source.read(1) not in (b"\n", b"\r")

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            writer = csv.DictWriter(f, fieldnames=list(row.keys()), lineterminator="\n")
            if file_is_empty:
                writer.writeheader()
            writer.writerow(row)

        with _lock:
            _sim_log.append(event)

        print(f"[sim] New order {order_id}: {p['name']} x{qty} from {state}/{chan} — ₹{_format_indian_number(revenue)} + GST")
        _run_pipeline()


def _simulation_loop(interval: int = 15) -> None:
    """Background thread: generate a new order every `interval` seconds."""
    time.sleep(3)   # brief startup delay
    while True:
        _simulate_order()
        time.sleep(interval)


# ── HTTP Handler ───────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    """Serve the dashboard files and /api/* JSON endpoints."""

    def log_message(self, fmt, *args):   # quieter logs
        request = args[0] if args and isinstance(args[0], str) else ""
        if "/api/" in request:
            return
        print(f"[http] {fmt % args}")

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        MIME = {
            ".html": "text/html; charset=utf-8",
            ".css":  "text/css",
            ".js":   "application/javascript",
        }
        mime = MIME.get(path.suffix, "application/octet-stream")
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        # ── API endpoints ──
        if path == "/api/data":
            self._send_json(_build_api_payload())
        elif path == "/api/refresh":
            try:
                _run_pipeline()
            except Exception as exc:
                self._send_json({"error": "Pipeline refresh failed", "detail": str(exc)}, status=500)
            else:
                self._send_json({"ok": True, "time": datetime.now(timezone.utc).isoformat()})
        elif path == "/api/simulate":
            threading.Thread(target=_simulate_order, daemon=True).start()
            self._send_json({"ok": True})
        elif path == "/api/events":
            with _lock:
                self._send_json(list(_sim_log))

        # ── Static files ──
        elif path in ("", "/", "/index.html"):
            self._send_file(DASH_DIR / "index.html")
        elif path == "/style.css":
            self._send_file(DASH_DIR / "style.css")
        elif path == "/app.js":
            self._send_file(DASH_DIR / "app.js")
        else:
            self.send_error(404)


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    # Run pipeline once on startup to ensure exports are fresh
    print("[startup] Running initial pipeline...")
    _run_pipeline()
    _initialize_sim_order_counter()

    # Start simulation thread
    sim = threading.Thread(target=_simulation_loop, args=(15,), daemon=True)
    sim.start()
    print(f"[sim] Simulation started — new order every 15 seconds")

    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"\n{'='*50}")
    print(f"  Sales BI Live Dashboard")
    print(f"  Open: http://localhost:{PORT}")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped.")


if __name__ == "__main__":
    main()
