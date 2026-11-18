"""Canonical sales data model and normalization helpers."""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = {
    "order_id",
    "order_date",
    "region",
    "channel",
    "category",
    "product_id",
    "product_name",
    "customer_id",
    "quantity",
    "unit_price",
    "unit_cost",
}


def normalize_sales_frame(source: pd.DataFrame, source_name: str = "unknown") -> pd.DataFrame:
    """Validate, clean, and enrich a source frame into the Power BI fact table."""
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"{source_name} missing required columns: {', '.join(sorted(missing))}")

    frame = source.copy()
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce", utc=True).dt.tz_localize(None)
    for column in ("quantity", "unit_price", "unit_cost"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "state" in frame:
        frame["state"] = frame["state"].fillna(frame["region"])
        empty_states = frame["state"].astype(str).str.strip().eq("")
        frame.loc[empty_states, "state"] = frame.loc[empty_states, "region"]
    else:
        frame["state"] = frame["region"]
    if "gst_rate_pct" in frame:
        frame["gst_rate_pct"] = pd.to_numeric(frame["gst_rate_pct"], errors="coerce")
        invalid_gst_rates = frame["gst_rate_pct"].isna() | ~frame["gst_rate_pct"].between(0, 100)
        if invalid_gst_rates.any():
            raise ValueError(f"{source_name} contains invalid GST rates")
    else:
        frame["gst_rate_pct"] = 0.0
    frame = frame.dropna(subset=["order_id", "order_date", "quantity", "unit_price", "unit_cost"])
    frame = frame[frame["quantity"] > 0].copy()
    frame["revenue"] = (frame["quantity"] * frame["unit_price"]).round(2)
    frame["cost"] = (frame["quantity"] * frame["unit_cost"]).round(2)
    frame["gst_amount"] = (frame["revenue"] * frame["gst_rate_pct"] / 100).round(2)
    frame["total_with_gst"] = (frame["revenue"] + frame["gst_amount"]).round(2)
    frame["gross_profit"] = (frame["revenue"] - frame["cost"]).round(2)
    frame["gross_margin_pct"] = (
        frame["gross_profit"].div(frame["revenue"].mask(frame["revenue"].eq(0), pd.NA)) * 100
    ).fillna(0).round(2)
    frame["source_system"] = source_name
    frame["year"] = frame["order_date"].dt.year
    frame["quarter"] = "Q" + frame["order_date"].dt.quarter.astype(str)
    frame["month"] = frame["order_date"].dt.month
    frame["month_name"] = frame["order_date"].dt.strftime("%B")
    frame["week"] = frame["order_date"].dt.isocalendar().week.astype(int)
    frame["day_of_week"] = frame["order_date"].dt.day_name()
    return frame.sort_values("order_date").reset_index(drop=True)
