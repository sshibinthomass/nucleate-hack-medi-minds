# save as inspect_steps.py and run: python inspect_steps.py
import pandas as pd
import os

csv_path = "data/step_daily_trend.csv"   # adjust if needed
# If your CSV really has the header on the second row, use header=1; otherwise header=0
header = 1

print("Reading:", csv_path, "header=", header)
df = pd.read_csv(csv_path, header=header, encoding="utf-8-sig")
df.columns = df.columns.str.strip()
print("Columns:", list(df.columns))
print("\nFirst 10 rows:")
print(df.head(10).to_string(index=False))

steps_col = "count"   # same as script --steps-col; change if you use a different column
date_col = "update_time"  # change to the date column you use

print("\nColumn dtype for steps_col '{}':".format(steps_col), df[steps_col].dtype)
print(df[steps_col].head(20))

print("\nSteps column describe():")
print(pd.to_numeric(df[steps_col], errors="coerce").describe())

# show sample of the column values that are fractional
frac = pd.to_numeric(df[steps_col], errors="coerce")
print("\nExamples of fractional values (non-integer):")
print(frac[frac.notna() & (frac != frac.astype(int))].head(20).to_string(index=False))

# Parse date column reliably (try the most appropriate column)
df[date_col + "_parsed"] = pd.to_datetime(df[date_col].astype(str).str.strip(), errors="coerce")
print("\nParsed date sample for '{}':".format(date_col))
print(df[[date_col, date_col + "_parsed"]].head(10).to_string(index=False))

# Aggregate exactly like the plotting script (sum per day)
df_valid = df.loc[df[date_col + "_parsed"].notna()].copy()
df_valid["date_only"] = df_valid[date_col + "_parsed"].dt.normalize()
daily = df_valid.groupby("date_only")[steps_col].agg(["sum", "mean", "count"]).reset_index()
print("\nDaily aggregated (first 20 days):")
print(daily.head(20).to_string(index=False))
print("\nDaily sum dtype:", daily["sum"].dtype)