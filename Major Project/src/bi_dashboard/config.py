"""Environment-backed application settings."""

from pathlib import Path
import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _HAS_PYDANTIC_SETTINGS = True
except ModuleNotFoundError:  # Keep the CLI usable before optional dependencies are installed.
    _HAS_PYDANTIC_SETTINGS = False
    class BaseSettings:
        def __init__(self, **values: object) -> None:
            for name, default in self.__class__.__annotations__.items():
                setattr(self, name, values.get(name, getattr(self, name, default)))

    class SettingsConfigDict(dict):
        pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SALES_BI_", extra="ignore")

    data_dir: Path = Path("data")
    output_dir: Path = Path("powerbi/exports")
    report_dir: Path = Path("powerbi/reports")
    database_path: Path = Path("database/sales.sqlite")
    sql_server_url: str = ""
    sql_server_query: str = "SELECT * FROM sales"
    report_recipients: str = ""
    webhook_url: str = ""
    minimum_margin_pct: float = 20
    minimum_daily_revenue: float = 100_000
    schedule_hour: int = 7
    schedule_timezone: str = "UTC"

    def __init__(self, **values: object) -> None:
        if not _HAS_PYDANTIC_SETTINGS:
            defaults = {name: getattr(self.__class__, name) for name in self.__class__.__annotations__ if hasattr(self.__class__, name)}
            values = {**defaults, **values}
            for name, default in values.items():
                raw = os.getenv(f"SALES_BI_{name.upper()}")
                if raw is None:
                    continue
                values[name] = (
                    Path(raw) if isinstance(default, Path)
                    else float(raw) if isinstance(default, float)
                    else int(raw) if isinstance(default, int)
                    else raw
                )
        super().__init__(**values)

    @property
    def recipients(self) -> list[str]:
        return [item.strip() for item in self.report_recipients.split(",") if item.strip()]
