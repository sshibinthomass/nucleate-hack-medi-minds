# Utility helper for exporting metric series to JSON
from __future__ import annotations
import json
import pandas as pd
from typing import Any

def write_metric_json(df: pd.DataFrame, column: str, out_path: str) -> None:
    """
    Write a list of {"timestamp": ISO, "value": float} entries for the given column
    in `df` to out_path as pretty JSON.

    Args:
      df: DataFrame containing a 'date' column and the metric column.
      column: name of the metric column to export (e.g. 'steps', 'calories').
      out_path: output path (string) where the JSON will be written.
    """
    records: list[dict[str, Any]] = []
    # Accept df with either a 'date' column or an index of datetimes
    if "date" in df.columns:
        it = df[["date", column]].itertuples(index=False, name=None)
        for date_val, value in it:
            ts = pd.to_datetime(date_val).isoformat()
            val = None if pd.isna(value) else float(value)
            records.append({"timestamp": ts, "value": val})
    else:
        # fallback: use index
        for idx, value in zip(df.index, df[column]):
            ts = pd.to_datetime(idx).isoformat()
            val = None if pd.isna(value) else float(value)
            records.append({"timestamp": ts, "value": val})

    # Write JSON
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)