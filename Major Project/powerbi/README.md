# Power BI setup

Use Power Query to load the Microsoft Excel source, apply the column contract below, and write the curated sales table to SQL Server. For local development, import `fact_sales.csv`, `kpi_summary.csv`, and the aggregate tables from this folder after running `sales-bi run`. Set `fact_sales[order_date]` to Date and numeric columns to Decimal Number. The aggregate tables are convenient for small reports; the fact table is the source of truth.

Required sales columns: `order_id`, `order_date`, `region`, `channel`, `category`, `product_id`, `product_name`, `customer_id`, `quantity`, `unit_price`, and `unit_cost`. The optional `state` column enables state-level reporting and defaults to `region` when absent. The optional `gst_rate_pct` column supplies the GST rate per order line and defaults to 0 when absent; the demo data uses an illustrative 18% rate.

`unit_price`, `revenue`, and `cost` are in INR and exclude GST. The pipeline calculates `gst_amount` and `total_with_gst` separately; gross profit and margin are based on pre-GST sales. GST rates depend on the applicable HSN/SAC classification—verify rates before using figures for tax reporting.

## Power Query staging

In Power Query, connect to the Excel workbook, promote headers, set date and numeric types, remove blank order IDs, and load the result to the SQL Server `sales` table. Keep the transformation steps deterministic so a Power Automate-triggered refresh produces the same table shape on every run.

## Recommended model

Create a one-to-many relationship from a dedicated calendar table to `fact_sales[order_date]`. Keep `kpi_summary` disconnected if it is used only for card visuals. Use `state`, `region`, `channel`, `category`, and `product_name` as slicers from `fact_sales` or dimensions created in Power Query.

Create the calendar table with:

```DAX
Calendar = CALENDAR(MIN(fact_sales[order_date]), MAX(fact_sales[order_date]))
Year = YEAR(Calendar[Date])
Month = FORMAT(Calendar[Date], "YYYY-MM")
```

## Measures

```DAX
Revenue ex GST = SUM(fact_sales[revenue])
GST Estimate = SUM(fact_sales[gst_amount])
Customer Total = SUM(fact_sales[total_with_gst])
Cost = SUM(fact_sales[cost])
Gross Profit = [Revenue ex GST] - [Cost]
Gross Margin % = DIVIDE([Gross Profit], [Revenue ex GST])
Orders = DISTINCTCOUNT(fact_sales[order_id])
Customers = DISTINCTCOUNT(fact_sales[customer_id])
Units = SUM(fact_sales[quantity])
Average Order Value = DIVIDE([Revenue ex GST], [Orders])
Revenue LY = CALCULATE([Revenue ex GST], SAMEPERIODLASTYEAR(Calendar[Date]))
Revenue YoY % = DIVIDE([Revenue ex GST] - [Revenue LY], [Revenue LY])
```

## Suggested report pages

1. **Executive overview**: INR sales before GST, estimated GST, customer total including GST, Gross Profit, Gross Margin %, Orders, and AOV; daily sales line; state and channel charts; alerts table.
2. **Product performance**: product revenue, margin, units, and category slicer.
3. **Sales operations**: daily trend, source system, channel, and region drill-through.

Use Power BI Service scheduled refresh after the export folder is available through an on-premises gateway, OneDrive/SharePoint sync, or a deployment job. The Python scheduler is responsible for producing the files and management text report; Power BI is responsible for visual refresh and distribution.

## Power Automate flow

1. Trigger on the Excel file update or a scheduled recurrence.
2. Refresh the SQL Server/Power BI dataset after the Power Query load completes.
3. Query the `alerts` output or Power BI alert state.
4. Send the management report to the configured recipients and record the flow run outcome.

Use a gateway when SQL Server is on-premises, and keep credentials in the connector or environment configuration rather than in workbook or report files.
