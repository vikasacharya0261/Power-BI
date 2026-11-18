"""Business metrics and management alert rules."""

from __future__ import annotations

import pandas as pd


def kpi_summary(sales: pd.DataFrame) -> pd.DataFrame:
    revenue = sales["revenue"].sum()
    gross_profit = sales["gross_profit"].sum()
    return pd.DataFrame([{
        "orders": sales["order_id"].nunique(),
        "customers": sales["customer_id"].nunique(),
        "units": sales["quantity"].sum(),
        "revenue": round(revenue, 2),
        "gst_collected": round(sales["gst_amount"].sum(), 2),
        "total_with_gst": round(sales["total_with_gst"].sum(), 2),
        "cost": round(sales["cost"].sum(), 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round((gross_profit / revenue) * 100, 2) if revenue else 0,
        "average_order_value": round(revenue / sales["order_id"].nunique(), 2) if sales["order_id"].nunique() else 0,
        "last_order_date": sales["order_date"].max(),
    }])


def _grouped(sales: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    grouped = sales.groupby(dimensions, dropna=False, as_index=False).agg(
        orders=("order_id", "nunique"),
        units=("quantity", "sum"),
        revenue=("revenue", "sum"),
        gst_collected=("gst_amount", "sum"),
        total_with_gst=("total_with_gst", "sum"),
        cost=("cost", "sum"),
        gross_profit=("gross_profit", "sum"),
    )
    grouped["gross_margin_pct"] = (
        grouped["gross_profit"].div(grouped["revenue"].mask(grouped["revenue"].eq(0), pd.NA)) * 100
    ).fillna(0).round(2)
    return grouped


def build_metric_tables(sales: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "fact_sales": sales,
        "kpi_summary": kpi_summary(sales),
        "sales_daily": _grouped(sales, ["order_date"]),
        "sales_by_region": _grouped(sales, ["region"]),
        "sales_by_state": _grouped(sales, ["state"]),
        "sales_by_channel": _grouped(sales, ["channel"]),
        "sales_by_product": _grouped(sales, ["product_id", "product_name", "category"]),
    }


def evaluate_alerts(sales: pd.DataFrame, minimum_margin_pct: float = 20, minimum_daily_revenue: float = 100_000) -> list[dict[str, object]]:
    """Return alert records that management can act on."""
    alerts: list[dict[str, object]] = []
    summary = kpi_summary(sales).iloc[0]
    if float(summary["gross_margin_pct"]) < minimum_margin_pct:
        alerts.append({"type": "low_margin", "severity": "high", "message": f"Gross margin is {summary['gross_margin_pct']:.2f}%"})
    daily = _grouped(sales, ["order_date"])
    if not daily.empty and float(daily.iloc[-1]["revenue"]) < minimum_daily_revenue:
        alerts.append({"type": "low_daily_revenue", "severity": "medium", "message": f"Sales on {daily.iloc[-1]['order_date']:%Y-%m-%d} were below the daily INR target (excluding GST)"})
    return alerts
