import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

TEAMS = ["Finance", "HR", "MAC1", "MAC2", "MAC3", "MAC4", "MAC5", "MAC6"]

RESOURCE_CATEGORIES = {
    "Compute": [
        "CustomerPortal-App",
        "OrderProcessing-Service",
        "Analytics-Engine",
        "Notification-Service",
        "Integration-Gateway",
    ],
    "Storage": [
        "CustomerDataStorage",
        "BackupStorageAccount",
        "AuditLogStorage",
        "DataLakeStorage",
        "DocumentArchive",
    ],
    "Database": [
        "CustomerDB",
        "FinanceDB",
        "EmployeeDB",
        "ReportingDB",
        "InventoryDB",
    ],
}

# ─────────────────────────────────────────────
# Realistic base costs per team × category  (monthly USD)
# ─────────────────────────────────────────────
BASE_COSTS = {
    # (team, category) → typical monthly spend
    ("Finance",  "Compute"):  12_000,
    ("Finance",  "Storage"):   4_500,
    ("Finance",  "Database"):  8_000,
    ("HR",       "Compute"):   6_500,
    ("HR",       "Storage"):   2_200,
    ("HR",       "Database"):  3_800,
    ("MAC1",     "Compute"):  18_000,
    ("MAC1",     "Storage"):   7_000,
    ("MAC1",     "Database"): 11_000,
    ("MAC2",     "Compute"):  15_500,
    ("MAC2",     "Storage"):   5_800,
    ("MAC2",     "Database"):  9_500,
    ("MAC3",     "Compute"):  22_000,
    ("MAC3",     "Storage"):   8_500,
    ("MAC3",     "Database"): 13_000,
    ("MAC4",     "Compute"):  10_000,
    ("MAC4",     "Storage"):   3_500,
    ("MAC4",     "Database"):  6_000,
    ("MAC5",     "Compute"):  28_000,
    ("MAC5",     "Storage"):  11_000,
    ("MAC5",     "Database"): 16_000,
    ("MAC6",     "Compute"):  19_500,
    ("MAC6",     "Storage"):   7_500,
    ("MAC6",     "Database"): 12_500,
}

# ─────────────────────────────────────────────
# Seasonal multipliers (month 1-12)
# Higher in Q4 (year-end), lower in Q1
# ─────────────────────────────────────────────
SEASONAL = {
    1: 0.82, 2: 0.85, 3: 0.90,
    4: 0.95, 5: 1.00, 6: 1.05,
    7: 1.08, 8: 1.10, 9: 1.12,
    10: 1.15, 11: 1.20, 12: 1.28,
}

# Weekend discount: cloud infra often scales down on weekends
WEEKDAY_MULT = {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.95, 5: 0.72, 6: 0.68}

# ─────────────────────────────────────────────
# Team-level growth trend (annual growth rate)
# ─────────────────────────────────────────────
TEAM_GROWTH = {
    "Finance": 0.08,
    "HR":      0.04,
    "MAC1":    0.12,
    "MAC2":    0.15,
    "MAC3":    0.20,   # fast-growing team
    "MAC4":    0.06,
    "MAC5":    0.25,   # biggest spender, aggressive growth
    "MAC6":    0.10,
}

# ─────────────────────────────────────────────
# Planned spike events (date range, team/None=all, category/None=all, multiplier)
# ─────────────────────────────────────────────
SPIKE_EVENTS = [
    # Quarter-end reporting spikes – Finance & Database
    {"start": "2024-03-28", "end": "2024-03-31", "team": "Finance",  "category": "Database", "mult": 3.5},
    {"start": "2024-06-28", "end": "2024-06-30", "team": "Finance",  "category": "Database", "mult": 3.2},
    {"start": "2024-09-28", "end": "2024-09-30", "team": "Finance",  "category": "Database", "mult": 3.4},
    {"start": "2024-12-28", "end": "2024-12-31", "team": "Finance",  "category": "Database", "mult": 4.0},
    # ML training burst – MAC3/MAC5 Compute
    {"start": "2024-02-10", "end": "2024-02-17", "team": "MAC3",    "category": "Compute",   "mult": 5.5},
    {"start": "2024-08-05", "end": "2024-08-12", "team": "MAC5",    "category": "Compute",   "mult": 6.0},
    # Annual HR open-enrollment – HR Storage spike
    {"start": "2024-10-15", "end": "2024-10-25", "team": "HR",      "category": "Storage",   "mult": 2.8},
    # Data migration project – MAC1 Storage
    {"start": "2024-05-01", "end": "2024-05-14", "team": "MAC1",    "category": "Storage",   "mult": 4.2},
    # Year-end everything spike
    {"start": "2024-12-15", "end": "2024-12-24", "team": None,      "category": None,         "mult": 1.8},
    # Infra incident – MAC2 Compute runaway (cost anomaly)
    {"start": "2024-07-22", "end": "2024-07-23", "team": "MAC2",    "category": "Compute",   "mult": 8.0},
    # Black Friday surge
    {"start": "2024-11-29", "end": "2024-12-02", "team": None,      "category": "Compute",   "mult": 2.5},
]


def get_spike_multiplier(date, team, category):
    mult = 1.0
    for evt in SPIKE_EVENTS:
        s = datetime.strptime(evt["start"], "%Y-%m-%d").date()
        e = datetime.strptime(evt["end"],   "%Y-%m-%d").date()
        if s <= date <= e:
            if (evt["team"] is None or evt["team"] == team) and \
               (evt["category"] is None or evt["category"] == category):
                mult = max(mult, evt["mult"])
    return mult


def generate_cost_data(days=365):
    records = []
    start_date = datetime(2024, 1, 1)

    for day in range(days):
        current_date = (start_date + timedelta(days=day)).date()
        year_fraction = day / 365.0

        for team in TEAMS:
            for category, resources in RESOURCE_CATEGORIES.items():
                monthly_base = BASE_COSTS[(team, category)]
                daily_base = monthly_base / 30.0

                # --- Growth trend ---
                growth = (1 + TEAM_GROWTH[team]) ** year_fraction
                daily_base *= growth

                # --- Seasonality ---
                daily_base *= SEASONAL[current_date.month]

                # --- Weekend scaling ---
                daily_base *= WEEKDAY_MULT[current_date.weekday()]

                # --- Planned spike events ---
                spike_mult = get_spike_multiplier(current_date, team, category)
                daily_base *= spike_mult

                # --- Random daily noise (±15%) ---
                noise = np.random.normal(1.0, 0.08)
                cost = max(10.0, daily_base * noise)

                # --- Occasional random anomaly (separate from planned spikes) ---
                if random.random() < 0.015:   # 1.5% chance
                    cost *= random.uniform(2.5, 7.0)

                # --- Utilization: correlated with cost ---
                base_util = min(95, 30 + (cost / daily_base) * 35)
                utilization = int(np.clip(np.random.normal(base_util, 8), 5, 100))

                # --- Resource name: sticky per team/category (not random every row) ---
                resource_seed = hash((team, category)) % len(resources)
                resource_name = resources[resource_seed]

                records.append({
                    "date":              current_date,
                    "team":              team,
                    "resource_category": category,
                    "resource_name":     resource_name,
                    "cost":              round(cost, 2),
                    "utilization":       utilization,
                    "is_weekend":        current_date.weekday() >= 5,
                    "month":             current_date.month,
                    "quarter":           f"Q{(current_date.month - 1) // 3 + 1}",
                })

    return pd.DataFrame(records)


if __name__ == "__main__":
    df = generate_cost_data(days=365)

    print("=== Sample rows ===")
    print(df.head(10).to_string(index=False))

    print("\n=== Cost range per team ===")
    summary = (
        df.groupby("team")["cost"]
        .agg(["min", "mean", "max", "sum"])
        .round(2)
    )
    print(summary)

    print("\n=== Monthly total spend ===")
    monthly = df.groupby("month")["cost"].sum().round(2)
    print(monthly)

    out = "azure_cost_data.csv"
    df.to_csv(out, index=False)
    print(f"\n✅  Generated {len(df):,} records → {out}")