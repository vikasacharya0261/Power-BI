"""APScheduler entry point for daily management reports."""

from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import Settings
from .notifications import build_report, deliver_report
from .pipeline import run_pipeline


def schedule_daily(settings: Settings, source_paths: list[Path] | None = None) -> None:
    def job() -> None:
        result = run_pipeline(settings, source_paths)
        deliver_report(build_report(result), settings.report_dir, settings.recipients, settings.webhook_url)

    scheduler = BlockingScheduler(timezone=settings.schedule_timezone)
    scheduler.add_job(job, "cron", hour=settings.schedule_hour, minute=0, id="daily-sales-report", replace_existing=True)
    job()
    scheduler.start()
