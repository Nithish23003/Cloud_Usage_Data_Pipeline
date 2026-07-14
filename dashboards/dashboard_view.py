import duckdb
import pandas as pd
import os

conn = duckdb.connect("database/db/finops_export.duckdb", read_only=True)

os.makedirs("exports", exist_ok=True)

views = [
    "VW_DAILY_COST_SUMMARY",
    "VW_MONTHLY_COST_TREND",
    "VW_TEAM_COST_SHARE",
    "VW_COST_ANOMALIES",
    "VW_UTILIZATION_EFFICIENCY",
    "VW_WEEKEND_VS_WEEKDAY",
    "VW_TOP_EXPENSIVE_DAYS",
]

for view in views:
    df = conn.execute(f"SELECT * FROM {view}").df()
    df.to_csv(f"exports/{view}.csv", index=False)
    print(f"✅ Exported {view} → {len(df)} rows")

conn.close()
print("\nAll views exported to exports/ folder.")