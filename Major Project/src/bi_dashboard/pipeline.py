"""Orchestrate ingestion, metric generation, exports, and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import Settings
from .database import write_sales_database
from .metrics import build_metric_tables, evaluate_alerts
from .sources import collect_sales


def run_pipeline(settings: Settings, source_paths: list[Path] | None = None) -> dict[str, object]:
    paths = source_paths or sorted(settings.data_dir.glob("*.csv")) + sorted(settings.data_dir.glob("*.sqlite"))
    sales = collect_sales(paths, settings.sql_server_url, settings.sql_server_query)
    write_sales_database(sales, settings.database_path)
    tables = build_metric_tables(sales)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(settings.output_dir / f"{name}.csv", index=False)
    alerts = evaluate_alerts(sales, settings.minimum_margin_pct, settings.minimum_daily_revenue)
    pd.DataFrame(alerts or [{"type": "none", "severity": "info", "message": "No active alerts"}]).to_csv(settings.output_dir / "alerts.csv", index=False)
    run_info = pd.DataFrame([{"run_at_utc": datetime.now(timezone.utc).isoformat(), "rows_loaded": len(sales), "tables_written": len(tables), "alerts": len(alerts)}])
    run_info.to_csv(settings.output_dir / "pipeline_runs.csv", index=False)
    return {"tables": tables, "alerts": alerts, "rows_loaded": len(sales)}
