import pandas as pd

from bi_dashboard.config import Settings
from bi_dashboard.database import read_sales_records
from bi_dashboard.pipeline import run_pipeline


def test_pipeline_persists_dashboard_transactions_to_sqlite(tmp_path):
    data_dir = tmp_path / "input"
    data_dir.mkdir()
    pd.DataFrame(
        [{
            "order_id": "A-1", "order_date": "2026-01-15", "region": "West",
            "channel": "Online", "category": "Hardware", "product_id": "P-1",
            "product_name": "Widget", "customer_id": "C-1", "quantity": 2,
            "unit_price": 50, "unit_cost": 30,
        }]
    ).to_csv(data_dir / "sales.csv", index=False)
    database_path = tmp_path / "database" / "sales.sqlite"

    result = run_pipeline(Settings(
        data_dir=data_dir,
        output_dir=tmp_path / "exports",
        database_path=database_path,
    ))

    transactions = read_sales_records(database_path)
    assert result["rows_loaded"] == 1
    assert len(transactions) == 1
    assert transactions[0]["order_id"] == "A-1"
    assert transactions[0]["revenue"] == 100
    assert transactions[0]["state"] == "West"
    assert transactions[0]["gst_amount"] == 0
    assert (tmp_path / "exports" / "sales_by_state.csv").exists()
