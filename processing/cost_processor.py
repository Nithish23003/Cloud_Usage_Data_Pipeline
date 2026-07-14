import duckdb
import pandas as pd
import shutil

conn = duckdb.connect("database/db/finops.duckdb")

# ─────────────────────────────────────────────
# 1. Load raw data
# ─────────────────────────────────────────────
df = pd.read_csv("azure_cost_data.csv", parse_dates=["date"])

conn.execute("""
CREATE OR REPLACE TABLE AZURE_COST_DATA AS
SELECT
    CAST(date AS DATE)              AS date,
    team,
    resource_category,
    resource_name,
    ROUND(CAST(cost AS DOUBLE), 2)  AS cost,
    CAST(utilization AS INTEGER)    AS utilization,
    CAST(is_weekend AS BOOLEAN)     AS is_weekend,
    CAST(month AS INTEGER)          AS month,
    quarter
FROM df
""")

# ─────────────────────────────────────────────
# 2. Daily summary per team + category
#    → Line/bar chart: "Daily spend by team"
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_DAILY_COST_SUMMARY AS
SELECT
    date,
    team,
    resource_category,
    quarter,
    SUM(cost)                                   AS total_cost,
    AVG(utilization)                            AS avg_utilization,
    SUM(SUM(cost)) OVER (
        PARTITION BY team, resource_category
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                           AS running_total_cost
FROM AZURE_COST_DATA
GROUP BY date, team, resource_category, quarter
""")

# ─────────────────────────────────────────────
# 3. Monthly spend with MoM % change
#    → KPI cards + trend line
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_MONTHLY_COST_TREND AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', date)       AS month_start,
        strftime(date, '%Y-%m')         AS year_month,
        quarter,
        team,
        resource_category,
        SUM(cost)                       AS total_cost,
        AVG(utilization)                AS avg_utilization
    FROM AZURE_COST_DATA
    GROUP BY 1, 2, 3, 4, 5
)
SELECT
    *,
    LAG(total_cost) OVER (
        PARTITION BY team, resource_category
        ORDER BY month_start
    )                                   AS prev_month_cost,
    ROUND(
        (total_cost - LAG(total_cost) OVER (
            PARTITION BY team, resource_category
            ORDER BY month_start
        )) * 100.0
        / NULLIF(LAG(total_cost) OVER (
            PARTITION BY team, resource_category
            ORDER BY month_start
        ), 0),
    2)                                  AS mom_pct_change
FROM monthly
""")

# ─────────────────────────────────────────────
# 4. Team cost share (for pie / donut chart)
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_TEAM_COST_SHARE AS
SELECT
    team,
    resource_category,
    quarter,
    SUM(cost)                                           AS total_cost,
    ROUND(SUM(cost) * 100.0 / SUM(SUM(cost)) OVER (
        PARTITION BY quarter
    ), 2)                                               AS pct_of_quarter_spend
FROM AZURE_COST_DATA
GROUP BY team, resource_category, quarter
""")

# ─────────────────────────────────────────────
# 5. Anomaly detection
#    Flags rows where cost > mean + 2*stddev for
#    that (team, category) combo → alert table
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_COST_ANOMALIES AS
WITH stats AS (
    SELECT
        team,
        resource_category,
        AVG(cost)   AS mean_cost,
        STDDEV(cost) AS stddev_cost
    FROM AZURE_COST_DATA
    GROUP BY team, resource_category
)
SELECT
    a.date,
    a.team,
    a.resource_category,
    a.resource_name,
    a.cost,
    ROUND(s.mean_cost, 2)                           AS baseline_mean,
    ROUND(s.mean_cost + 2 * s.stddev_cost, 2)       AS anomaly_threshold,
    ROUND((a.cost - s.mean_cost) / s.stddev_cost, 2) AS z_score,
    CASE
        WHEN a.cost > s.mean_cost + 3 * s.stddev_cost THEN 'CRITICAL'
        WHEN a.cost > s.mean_cost + 2 * s.stddev_cost THEN 'WARNING'
    END                                             AS severity
FROM AZURE_COST_DATA a
JOIN stats s USING (team, resource_category)
WHERE a.cost > s.mean_cost + 2 * s.stddev_cost
ORDER BY a.cost DESC
""")

# ─────────────────────────────────────────────
# 6. Utilization efficiency
#    High cost + low utilization = wasted spend
#    → Scatter plot / heatmap
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_UTILIZATION_EFFICIENCY AS
SELECT
    team,
    resource_category,
    resource_name,
    AVG(cost)                           AS avg_daily_cost,
    AVG(utilization)                    AS avg_utilization,
    SUM(cost)                           AS total_cost,
    CASE
        WHEN AVG(utilization) < 40 AND AVG(cost) > 300 THEN 'Overprovisioned'
        WHEN AVG(utilization) > 80 AND AVG(cost) > 500 THEN 'Optimized-HighLoad'
        WHEN AVG(utilization) > 80 AND AVG(cost) <= 500 THEN 'Efficient'
        ELSE 'Normal'
    END                                 AS efficiency_label
FROM AZURE_COST_DATA
GROUP BY team, resource_category, resource_name
""")

# ─────────────────────────────────────────────
# 7. Weekend vs Weekday cost comparison
#    → Bar chart for FinOps insight
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_WEEKEND_VS_WEEKDAY AS
SELECT
    team,
    resource_category,
    is_weekend,
    ROUND(AVG(cost), 2)     AS avg_cost,
    ROUND(SUM(cost), 2)     AS total_cost,
    COUNT(*)                AS record_count
FROM AZURE_COST_DATA
GROUP BY team, resource_category, is_weekend
""")

# ─────────────────────────────────────────────
# 8. Top 10 most expensive days overall
# ─────────────────────────────────────────────
conn.execute("""
CREATE OR REPLACE VIEW VW_TOP_EXPENSIVE_DAYS AS
SELECT
    date,
    SUM(cost)       AS total_daily_spend,
    COUNT(*)        AS resource_count
FROM AZURE_COST_DATA
GROUP BY date
ORDER BY total_daily_spend DESC
LIMIT 10
""")

# ─────────────────────────────────────────────
# Verify everything
# ─────────────────────────────────────────────
checks = {
    "Raw records":        "SELECT COUNT(*) FROM AZURE_COST_DATA",
    "Anomalies (WARN+)":  "SELECT COUNT(*) FROM VW_COST_ANOMALIES",
    "Anomalies CRITICAL": "SELECT COUNT(*) FROM VW_COST_ANOMALIES WHERE severity = 'CRITICAL'",
    "Overprovisioned":    "SELECT COUNT(*) FROM VW_UTILIZATION_EFFICIENCY WHERE efficiency_label = 'Overprovisioned'",
}

print("\n✅  DuckDB load complete")
print("─" * 40)
for label, query in checks.items():
    val = conn.execute(query).fetchone()[0]
    print(f"  {label:<25}: {val:>6,}")

print("\n📋  Views available for Power BI / dashboard:")
views = conn.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
""").fetchall()
for (v,) in views:
    print(f"  • {v}")

conn.close()
print("\n✅  finops.duckdb ready.\n")
shutil.copy("database/db/finops.duckdb", "database/db/finops_export.duckdb")
print("✅ Export copy created → finops_export.duckdb")