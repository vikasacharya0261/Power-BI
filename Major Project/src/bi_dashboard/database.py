"""SQLite persistence for the normalized sales fact table."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def write_sales_database(sales: pd.DataFrame, path: Path) -> None:
    """Atomically replace the local sales table with the latest pipeline data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        sales.to_sql("sales_staging", connection, if_exists="replace", index=False)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DROP TABLE IF EXISTS sales")
        connection.execute("ALTER TABLE sales_staging RENAME TO sales")
        connection.execute("CREATE UNIQUE INDEX sales_order_id_idx ON sales (order_id)")


def read_sales_records(path: Path) -> list[dict[str, object]]:
    """Return persisted sales rows in stable order for the dashboard API."""
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM sales ORDER BY order_date, order_id"
        ).fetchall()
    return [dict(row) for row in rows]
