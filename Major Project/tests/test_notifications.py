import pandas as pd

from bi_dashboard.metrics import build_metric_tables
from bi_dashboard.models import normalize_sales_frame
from bi_dashboard.notifications import build_report


def test_management_report_uses_indian_currency_and_shows_gst_separately():
    source = pd.DataFrame(
        [{
            "order_id": "IN-1", "order_date": "2026-01-15", "region": "West",
            "state": "Maharashtra", "channel": "Online", "category": "Hardware",
            "product_id": "P-1", "product_name": "Device", "customer_id": "C-1",
            "quantity": 1, "unit_price": 1_234_567, "unit_cost": 1_000_000,
            "gst_rate_pct": 18,
        }]
    )
    sales = normalize_sales_frame(source, "test")

    report = build_report({"tables": build_metric_tables(sales), "alerts": []})

    assert "Sales (excl. GST): ₹12,34,567.00" in report
    assert "GST estimate: ₹2,22,222.06" in report
    assert "Total (incl. GST): ₹14,56,789.06" in report
