import json
import csv
from http.server import HTTPServer
from threading import Lock, Thread
from time import sleep
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from dashboard import server


def test_indian_number_formatting():
    assert server._format_indian_number(12345678) == "1,23,45,678"


def test_pipeline_runs_are_serialized(monkeypatch):
    from bi_dashboard import pipeline

    active = 0
    maximum_active = 0
    active_lock = Lock()

    def fake_pipeline(settings):
        nonlocal active, maximum_active
        with active_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        sleep(0.05)
        with active_lock:
            active -= 1
        return {"rows_loaded": 0, "alerts": []}

    monkeypatch.setattr(pipeline, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(server, "_settings", lambda: object())
    threads = [Thread(target=server._run_pipeline) for _ in range(2)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert maximum_active == 1


def test_simulate_order_appends_to_csv_without_trailing_newline(tmp_path, monkeypatch):
    source = tmp_path / "sales_online.csv"
    source.write_text(
        "order_id,order_date,region,state,channel,category,product_id,product_name,"
        "customer_id,quantity,unit_price,unit_cost,gst_rate_pct\n"
        "A-1,2026-01-15,West,Gujarat,Online,Hardware,P-1,Widget,C-1,1,50,30,18",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "_run_pipeline", lambda: None)
    monkeypatch.setattr(server.random, "choice", lambda values: values[0])
    monkeypatch.setattr(server.random, "randint", lambda low, high: low)
    monkeypatch.setattr(server, "_sim_order_counter", 1006)
    monkeypatch.setattr(server, "_sim_log", [])

    server._simulate_order()

    with source.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [row["order_id"] for row in rows] == ["A-1", "SO-1006"]
    assert rows[-1]["state"] == "Assam"


def test_simulated_order_counter_continues_after_restart(tmp_path, monkeypatch):
    source = tmp_path / "sales_online.csv"
    source.write_text("order_id\nSO-1006\nSO-1012\n", encoding="utf-8")
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "_sim_order_counter", 1006)

    server._initialize_sim_order_counter()

    assert server._sim_order_counter == 1013


def test_refresh_endpoint_reports_pipeline_failure(monkeypatch):
    def fail_refresh():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(server, "_run_pipeline", fail_refresh)
    httpd = HTTPServer(("127.0.0.1", 0), server.DashboardHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{httpd.server_port}/api/refresh", timeout=5)

        assert error.value.code == 500
        assert json.load(error.value)["error"] == "Pipeline refresh failed"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_unknown_path_returns_404_without_handler_error():
    httpd = HTTPServer(("127.0.0.1", 0), server.DashboardHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{httpd.server_port}/not-found", timeout=5)

        assert error.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
