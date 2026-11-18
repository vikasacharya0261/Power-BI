"""Sales source adapters."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .models import normalize_sales_frame


def read_csv(path: Path) -> pd.DataFrame:
    return normalize_sales_frame(pd.read_csv(path), path.stem)


def read_sqlite(path: Path, query: str = "SELECT * FROM sales") -> pd.DataFrame:
    with sqlite3.connect(path) as connection:
        return normalize_sales_frame(pd.read_sql_query(query, connection), path.stem)


def read_sql_server(connection_url: str, query: str = "SELECT * FROM sales") -> pd.DataFrame:
    """Read a sales table or query through a SQLAlchemy SQL Server URL."""
    from sqlalchemy import create_engine

    engine = create_engine(connection_url)
    try:
        return normalize_sales_frame(pd.read_sql_query(query, engine), "sql_server")
    finally:
        engine.dispose()


def collect_sales(
    source_paths: list[Path],
    sql_server_url: str = "",
    sql_server_query: str = "SELECT * FROM sales",
) -> pd.DataFrame:
    """Read configured files and SQL Server data, then remove duplicate orders."""
    frames = []
    for path in source_paths:
        frames.append(read_sqlite(path) if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} else read_csv(path))
    if sql_server_url:
        frames.append(read_sql_server(sql_server_url, sql_server_query))
    if not frames:
        raise ValueError("At least one CSV, SQLite, or SQL Server source is required")
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["order_id"], keep="last").sort_values("order_date").reset_index(drop=True)
