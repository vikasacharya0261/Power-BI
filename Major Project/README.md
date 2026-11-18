# Sales BI Platform

An automated Python pipeline that consolidates sales sources, computes management KPIs, exports Power BI-ready tables, evaluates alerts, and produces scheduled reports.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
sales-bi run
python -m pytest
```

The Indian-market demo data in `data/` produces these tables in `powerbi/exports/`: `fact_sales`, `kpi_summary`, `sales_daily`, `sales_by_region`, `sales_by_state`, `sales_by_channel`, `sales_by_product`, `alerts`, and `pipeline_runs`.
Each pipeline run also refreshes a local SQLite copy of the normalized fact table at `database/sales.sqlite` by default. Override its location with `SALES_BI_DATABASE_PATH`. The live dashboard reads transaction rows from this database; CSV exports remain the Power BI interchange format.

The demo uses Indian states and sales channels, displays values in INR, and reports sales and profit before GST with estimated GST shown separately. Sample product prices and the 18% GST rate are illustrative only; confirm actual prices and the applicable HSN/SAC rate before using the data for business or tax reporting.

## Technology stack

- **Front end and reporting:** Power BI Desktop and Power BI Service
- **Backend:** SQL Server for production; a local SQLite sales store and CSV/Excel staging for development
- **ETL:** Power Query for Excel-to-SQL shaping; Python for scheduled metric exports
- **Automation:** Power Automate for refresh, alert, and report distribution workflows
- **Formula language:** DAX

## Sources

Drop CSV files into `data/`, or configure a SQL Server connection containing a `sales` table. Every source must provide the columns listed in `powerbi/README.md`. Files and database rows are normalized, deduplicated by `order_id`, and combined on every run.

For SQL Server, set `SALES_BI_SQL_SERVER_URL` to a SQLAlchemy connection URL and optionally override `SALES_BI_SQL_SERVER_QUERY`. For example, with a local ODBC installation:

```bash
export SALES_BI_SQL_SERVER_URL='mssql+pyodbc://user:password@server/database?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
sales-bi run
```

## Operations

`SALES_BI_MINIMUM_MARGIN_PCT` and `SALES_BI_MINIMUM_DAILY_REVENUE` (INR, excluding GST) control alerts. `sales-bi report` writes a management report to `powerbi/reports/latest_report.txt` and posts it to `SALES_BI_WEBHOOK_URL` when configured. `sales-bi schedule` runs immediately and then daily at `SALES_BI_SCHEDULE_HOUR` in the configured timezone. For production, run it under a service manager or container rather than an interactive terminal.

## Power BI and automation

Open Power BI Desktop, use **Get data > Text/CSV**, and import the CSVs from `powerbi/exports/`. Follow the model and measures in `powerbi/README.md`; configure scheduled refresh in the Power BI Service after publishing.

The production flow is: Excel is loaded through Power Query into SQL Server, Power BI reads the modeled SQL Server tables or pipeline exports, and Power Automate triggers refreshes and distributes alert/report notifications.
