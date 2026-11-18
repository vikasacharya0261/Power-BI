"""Scheduled report and alert delivery."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


def _format_inr(amount: float) -> str:
    whole, fraction = f"{abs(float(amount)):.2f}".split(".")
    if len(whole) > 3:
        groups = [whole[-3:]]
        whole = whole[:-3]
        while whole:
            groups.insert(0, whole[-2:])
            whole = whole[:-2]
        whole = ",".join(groups)
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{whole}.{fraction}"


def build_report(result: dict[str, object]) -> str:
    tables = result["tables"]
    summary = tables["kpi_summary"].iloc[0]
    lines = [
        "Sales BI management report",
        f"Sales (excl. GST): {_format_inr(summary['revenue'])}",
        f"GST estimate: {_format_inr(summary['gst_collected'])}",
        f"Total (incl. GST): {_format_inr(summary['total_with_gst'])}",
        f"Gross profit: {_format_inr(summary['gross_profit'])}",
        f"Gross margin: {summary['gross_margin_pct']:.2f}%",
        f"Orders: {int(summary['orders']):,}",
    ]
    for alert in result["alerts"]:
        lines.append(f"ALERT [{alert['severity']}]: {alert['message']}")
    return "\n".join(lines)


def deliver_report(report: str, report_dir: Path, recipients: list[str], webhook_url: str = "") -> Path:
    """Persist every report; optionally post the same report to a webhook."""
    report_dir.mkdir(parents=True, exist_ok=True)
    output = report_dir / "latest_report.txt"
    output.write_text(report + "\n", encoding="utf-8")
    if webhook_url:
        request = Request(webhook_url, data=json.dumps({"text": report}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15):
            pass
    return output
