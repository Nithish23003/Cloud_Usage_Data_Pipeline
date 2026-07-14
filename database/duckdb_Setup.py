import duckdb
import pandas as pd

# Connect to DuckDB
conn = duckdb.connect("database/db/finops.duckdb")

# Read CSV
df = pd.read_csv("azure_cost_data.csv")

# Create table and load data
conn.execute("""
CREATE OR REPLACE TABLE AZURE_COST_DATA AS
SELECT * FROM df
""")

# Verify
count = conn.execute(
    "SELECT COUNT(*) FROM AZURE_COST_DATA"
).fetchone()[0]

print(f"Records loaded successfully: {count}")

conn.close()