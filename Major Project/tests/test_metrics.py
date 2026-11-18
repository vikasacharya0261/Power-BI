import pandas as pd
import pytest

from bi_dashboard.metrics import build_metric_tables, kpi_summary
from bi_dashboard.models import normalize_sales_frame


def test_normalize_sales_frame_calculates_profit_and_date_dimensions():
    source = pd.DataFrame(
        [{
            "order_id": "A-1", "order_date": "2026-01-15", "region": "West",
            "channel": "Online", "category": "Hardware", "product_id": "P-1",
            "product_name": "Widget", "customer_id": "C-1", "quantity": 2,
            "unit_price": 50, "unit_cost": 30,
        }]
    )

    result = normalize_sales_frame(source, "test")

    assert result.loc[0, "revenue"] == 100
    assert result.loc[0, "gross_profit"] == 40
    assert result.loc[0, "gross_margin_pct"] == 40
    assert result.loc[0, "quarter"] == "Q1"
    assert result.loc[0, "source_system"] == "test"
    assert result.loc[0, "state"] == "West"
    assert result.loc[0, "gst_amount"] == 0


def test_zero_revenue_means_zero_margin_instead_of_nan():
    source = pd.DataFrame(
        [{
            "order_id": "A-2", "order_date": "2026-01-20", "region": "West",
            "channel": "Online", "category": "Hardware", "product_id": "P-2",
            "product_name": "Free Sample", "customer_id": "C-2", "quantity": 1,
            "unit_price": 0, "unit_cost": 0,
        }]
    )

    result = normalize_sales_frame(source, "test")
    assert result.loc[0, "revenue"] == 0
    assert result.loc[0, "gross_profit"] == 0
    assert result.loc[0, "gross_margin_pct"] == 0

    summary = kpi_summary(result)
    aggregated = build_metric_tables(result)

    assert summary.loc[0, "gross_margin_pct"] == 0
    assert aggregated["sales_by_region"].loc[0, "gross_margin_pct"] == 0


def test_gst_is_reported_separately_from_revenue_and_profit():
    source = pd.DataFrame(
        [{
            "order_id": "A-3", "order_date": "2026-01-21", "region": "South",
            "state": "Karnataka", "channel": "Online", "category": "Hardware",
            "product_id": "P-3", "product_name": "Device", "customer_id": "C-3",
            "quantity": 2, "unit_price": 1000, "unit_cost": 600,
            "gst_rate_pct": 18,
        }]
    )

    result = normalize_sales_frame(source, "test")
    summary = kpi_summary(result).iloc[0]

    assert result.loc[0, "revenue"] == 2000
    assert result.loc[0, "gst_amount"] == 360
    assert result.loc[0, "total_with_gst"] == 2360
    assert result.loc[0, "gross_profit"] == 800
    assert summary["gst_collected"] == 360
    assert summary["total_with_gst"] == 2360


def test_invalid_gst_rate_is_rejected():
    source = pd.DataFrame(
        [{
            "order_id": "A-4", "order_date": "2026-01-22", "region": "West",
            "channel": "Online", "category": "Hardware", "product_id": "P-4",
            "product_name": "Device", "customer_id": "C-4", "quantity": 1,
            "unit_price": 1000, "unit_cost": 600, "gst_rate_pct": 150,
        }]
    )

    with pytest.raises(ValueError, match="invalid GST rates"):
        normalize_sales_frame(source, "test")
