"""Command-line interface for the sales BI platform."""

import argparse
from pathlib import Path

from .config import Settings
from .notifications import build_report, deliver_report
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated sales BI pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "report", "schedule"):
        subparsers.add_parser(name)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "schedule":
        from .scheduler import schedule_daily

        schedule_daily(settings)
        return
    result = run_pipeline(settings)
    if args.command == "report":
        path = deliver_report(build_report(result), settings.report_dir, settings.recipients, settings.webhook_url)
        print(path)
    else:
        print(f"Loaded {result['rows_loaded']} rows and wrote {len(result['tables'])} Power BI tables")
