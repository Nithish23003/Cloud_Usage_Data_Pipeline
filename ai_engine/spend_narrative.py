import google.generativeai as genai
import duckdb
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# Configure Gemini
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


# ─────────────────────────────────────────────
# 1. Pull data from DuckDB
# ─────────────────────────────────────────────
def get_cost_metrics(
    db_path="database/db/finops.duckdb"
):
    conn = duckdb.connect(
        db_path,
        read_only=True
    )

    # Month-over-month change per category
    mom_df = conn.execute("""
        SELECT
            resource_category,
            year_month,
            total_cost,
            mom_pct_change
        FROM VW_MONTHLY_COST_TREND
        WHERE year_month = (SELECT MAX(year_month) FROM VW_MONTHLY_COST_TREND)
        GROUP BY resource_category, year_month, total_cost, mom_pct_change
        ORDER BY resource_category
    """).df()

    # Top anomalies this month
    anomalies_df = conn.execute("""
        SELECT
            team,
            resource_category,
            resource_name,
            cost,
            severity,
            z_score
        FROM VW_COST_ANOMALIES
        WHERE severity = 'CRITICAL'
        ORDER BY cost DESC
        LIMIT 5
    """).df()

    # Team with highest spend
    team_df = conn.execute("""
        SELECT team, SUM(total_cost) AS total
        FROM VW_DAILY_COST_SUMMARY
        GROUP BY team
        ORDER BY total DESC
        LIMIT 3
    """).df()

    # Overprovisioned resources
    waste_df = conn.execute("""
        SELECT resource_name, team, avg_daily_cost, avg_utilization
        FROM VW_UTILIZATION_EFFICIENCY
        WHERE efficiency_label = 'Overprovisioned'
        ORDER BY avg_daily_cost DESC
        LIMIT 3
    """).df()

    conn.close()
    return mom_df, anomalies_df, team_df, waste_df


# ─────────────────────────────────────────────
# 2. Format data into a structured prompt
# ─────────────────────────────────────────────
def build_prompt(mom_df, anomalies_df, team_df, waste_df):
    # MoM changes
    mom_lines = []
    for _, row in mom_df.iterrows():
        change = row["mom_pct_change"]
        if pd.isna(change):
            continue
        sign = "+" if change > 0 else ""
        mom_lines.append(f"  - {row['resource_category']} Cost {sign}{change:.1f}%")
    mom_text = "\n".join(mom_lines) if mom_lines else "  - No MoM data available"

    # Anomalies
    anomaly_lines = []
    for _, row in anomalies_df.iterrows():
        anomaly_lines.append(
            f"  - {row['team']} / {row['resource_name']}: ${row['cost']:,.0f} "
            f"(z-score: {row['z_score']:.1f}, {row['severity']})"
        )
    anomaly_text = "\n".join(anomaly_lines) if anomaly_lines else "  - No critical anomalies"

    # Top teams
    team_lines = [
        f"  - {row['team']}: ${row['total']:,.0f}"
        for _, row in team_df.iterrows()
    ]
    team_text = "\n".join(team_lines)

    # Waste
    waste_lines = []
    for _, row in waste_df.iterrows():
        waste_lines.append(
            f"  - {row['resource_name']} ({row['team']}): "
            f"avg cost ${row['avg_daily_cost']:,.0f}/day, "
            f"utilization {row['avg_utilization']:.0f}%"
        )
    waste_text = "\n".join(waste_lines) if waste_lines else "  - No overprovisioned resources"

    prompt = f"""
You are a FinOps analyst generating a concise, business-friendly cloud cost report.
Translate the technical metrics below into a clear narrative for non-technical stakeholders.

Use this structure:
1. **Overall Spend Summary** (2-3 sentences)
2. **Key Cost Drivers** (bullet points, plain English)
3. **Anomalies & Alerts** (what happened, why it matters)
4. **Waste & Optimization Opportunities** (actionable recommendations)
5. **Executive One-liner** (one sentence summary for leadership)

Keep the tone professional but simple. Avoid jargon. Use $ amounts where relevant.

--- METRICS ---

Month-over-Month Cost Changes:
{mom_text}

Top Spending Teams:
{team_text}

Critical Cost Anomalies:
{anomaly_text}

Overprovisioned Resources (high cost, low utilization):
{waste_text}

--- END METRICS ---

Generate the report now.
""".strip()

    return prompt


# ─────────────────────────────────────────────
# 3. Call Gemini and get narrative
# ─────────────────────────────────────────────
def generate_narrative(prompt):
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# 4. Save output
# ─────────────────────────────────────────────
def save_report(narrative):
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = f"reports/finops_report_{timestamp}.md"
    with open(path, "w") as f:
        f.write(f"# FinOps AI Report — {timestamp}\n\n")
        f.write(narrative)
    print(f"\n📄 Report saved → {path}")
    return path


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Pulling metrics from DuckDB...")
    mom_df, anomalies_df, team_df, waste_df = get_cost_metrics()

    print("🧠 Building prompt...")
    prompt = build_prompt(mom_df, anomalies_df, team_df, waste_df)

    print("✨ Calling Gemini 2.5 Flash...")
    narrative = generate_narrative(prompt)

    print("\n" + "═" * 60)
    print(narrative)
    print("═" * 60)

    save_report(narrative)