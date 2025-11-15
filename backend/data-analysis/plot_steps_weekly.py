#!/usr/bin/env python3
"""
Create weekly interactive step plots (Plotly) and save to data-analysis/static/steps_plot.html.

Features:
- Robust CSV reading (tries header=1 then header=0, common delimiters, BOM).
- Auto-detect date column (or use --date-col) and steps column (default: count).
- Aggregate daily steps and multiply by --scale (default 1000).
- By default only the selected current week is visible (overlay is not the initial view).
- Writes:
    data-analysis/static/steps_plot.html   <- interactive plot
    data-analysis/static/steps_launcher.html <- small launcher page that opens the popup
- Can open a native popup window (pywebview) if --use-webview is provided and pywebview is installed.
- Otherwise you can trigger the browser popup via JavaScript window.open from your UI or by opening the launcher page.

Example:
  python interactive_step_popup.py --file step_daily_trend.csv --date-col update_time --steps-col count --scale 1000 --use-webview

"""
from __future__ import annotations
import argparse
import os
import glob
import sys
import tempfile
from datetime import datetime, timezone, timedelta
import traceback

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# optional native popup
try:
    import webview  # type: ignore
    WEBVIEW_AVAILABLE = True
except Exception:
    WEBVIEW_AVAILABLE = False

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def find_csv(data_dir: str = ".", filename: str | None = None) -> str:
    data_dir = os.path.abspath(data_dir)
    if filename:
        fp = os.path.join(data_dir, filename)
        if os.path.isfile(fp):
            return fp
        raise FileNotFoundError(f"File not found: {fp}")
    files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def _read_with_fallback(path: str, header: int) -> pd.DataFrame:
    last_exc = None
    try:
        return pd.read_csv(path, header=header, sep=",", encoding="utf-8-sig", engine="python")
    except Exception as e:
        last_exc = e
    try:
        return pd.read_csv(path, header=header, sep=None, engine="python", encoding="utf-8-sig")
    except Exception as e:
        last_exc = e
    try:
        return pd.read_csv(path, header=header, sep="\t", encoding="utf-8-sig")
    except Exception as e:
        last_exc = e
    try:
        return pd.read_csv(path, header=header, sep=",", engine="python")
    except Exception as e:
        last_exc = e
    raise last_exc


def _auto_detect_date_col(df: pd.DataFrame, preferred: list[str] | None = None) -> tuple[str | None, dict | None]:
    cols = list(df.columns)
    if preferred:
        seen = set()
        pref = [c for c in preferred if c in cols and c not in seen and not seen.add(c)]
        cols = pref + [c for c in cols if c not in pref]
    best_col = None
    best_count = -1
    best_info = None
    if len(df) == 0:
        return None, None
    sample_n = min(200, len(df))
    for col in cols:
        s = df[col].dropna().astype(str).str.strip().head(sample_n)
        if s.empty:
            continue
        numeric = pd.to_numeric(s, errors="coerce")
        parsed_count = 0
        info = {"method": None, "unit": None}
        num_valid = numeric.notna().sum()
        if num_valid >= max(1, int(len(s) * 0.2)):
            med = numeric.dropna().median()
            if med > 1e12:
                parsed = pd.to_datetime(numeric, unit="ms", errors="coerce")
                parsed_count = int(parsed.notna().sum()); info = {"method": "epoch", "unit": "ms"}
            elif med > 1e9:
                parsed_s = pd.to_datetime(numeric, unit="s", errors="coerce")
                parsed_ms = pd.to_datetime(numeric, unit="ms", errors="coerce")
                if parsed_s.notna().sum() >= parsed_ms.notna().sum():
                    parsed_count = int(parsed_s.notna().sum()); info = {"method": "epoch", "unit": "s"}
                else:
                    parsed_count = int(parsed_ms.notna().sum()); info = {"method": "epoch", "unit": "ms"}
        if parsed_count < 1:
            parsed_str = pd.to_datetime(s, errors="coerce")
            parsed_count = int(parsed_str.notna().sum())
            if parsed_count > 0:
                info = {"method": "string", "unit": None}
        if parsed_count > best_count:
            best_count = parsed_count; best_col = col; best_info = info
    if best_count <= 0:
        return None, None
    return best_col, best_info


def load_and_aggregate(csv_path: str, date_col: str | None, steps_col: str, count_unit: str, scale: float) -> pd.DataFrame:
    """Read CSV robustly, compute per-row steps_for_agg, aggregate per day (tz-aware UTC) and scale."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)

    read_attempts = []
    df = None
    chosen_header = None
    for header in (1, 0):
        try:
            cand = _read_with_fallback(csv_path, header=header)
            cand.columns = cand.columns.str.strip()
            read_attempts.append(f"header={header}; cols={list(cand.columns)[:40]}")
            if steps_col in cand.columns:
                df = cand; chosen_header = header; break
            if df is None:
                df = cand; chosen_header = header
        except Exception as e:
            read_attempts.append(f"header={header} failed: {e}")

    if df is None:
        raise ValueError("Unable to read CSV. Attempts:\n" + "\n".join(read_attempts))

    if steps_col not in df.columns:
        raise ValueError(f"Steps column '{steps_col}' not found. Available: {list(df.columns)}")

    # detect/parse date column
    used_date_col = None
    if date_col and date_col in df.columns:
        parsed = pd.to_datetime(df[date_col].astype(str).str.strip(), errors="coerce", utc=True)
        if int(parsed.notna().sum()) > 0:
            df[date_col] = parsed; used_date_col = date_col

    if used_date_col is None:
        preferred = [date_col or "", "create_time", "update_time", "day_time", "timestamp", "time"]
        candidate_col, candidate_info = _auto_detect_date_col(df, preferred=preferred)
        if candidate_col is None:
            sample = {c: df[c].astype(str).head(5).tolist() for c in df.columns[:8]}
            raise ValueError("No date-like column detected. Sample columns: " + str(sample))
        if candidate_info["method"] == "epoch":
            unit = candidate_info.get("unit", "ms")
            df[candidate_col] = pd.to_datetime(pd.to_numeric(df[candidate_col], errors="coerce"), unit=unit, errors="coerce", utc=True)
        else:
            df[candidate_col] = pd.to_datetime(df[candidate_col].astype(str).str.strip(), errors="coerce", utc=True)
        used_date_col = candidate_col

    # ensure tz-aware
    if not pd.api.types.is_datetime64_any_dtype(df[used_date_col]):
        df[used_date_col] = pd.to_datetime(df[used_date_col], errors="coerce", utc=True)
    if df[used_date_col].dt.tz is None:
        df[used_date_col] = df[used_date_col].dt.tz_localize("UTC")

    # drop invalid dates
    before = len(df)
    df = df.loc[df[used_date_col].notna()].copy()
    dropped = before - len(df)

    # choose grouping column to avoid mixing devices
    group_col = None
    for c in ("deviceuuid", "datauuid", "pkg_name", "source_pkg_name"):
        if c in df.columns:
            group_col = c; break

    # sort and compute prev/next within group
    if group_col:
        df = df.sort_values([group_col, used_date_col]).reset_index(drop=True)
        prev = df.groupby(group_col)[used_date_col].shift(1)
        nxt = df.groupby(group_col)[used_date_col].shift(-1)
    else:
        df = df.sort_values(by=used_date_col).reset_index(drop=True)
        prev = df[used_date_col].shift(1); nxt = df[used_date_col].shift(-1)

    df["prev_time"] = prev; df["next_time"] = nxt
    df["prev_gap"] = (df[used_date_col] - df["prev_time"]).dt.total_seconds()
    df["next_gap"] = (df["next_time"] - df[used_date_col]).dt.total_seconds()

    # half-gap heuristic
    df["interval_seconds"] = (df["prev_gap"].fillna(0.0) + df["next_gap"].fillna(0.0)) / 2.0
    mask_first = df["prev_gap"].isna() & df["next_gap"].notna()
    mask_last = df["next_gap"].isna() & df["prev_gap"].notna()
    df.loc[mask_first, "interval_seconds"] = df.loc[mask_first, "next_gap"]
    df.loc[mask_last, "interval_seconds"] = df.loc[mask_last, "prev_gap"]
    median_interval = float(df.loc[df["interval_seconds"] > 0, "interval_seconds"].median(skipna=True) or 0.0)
    df["interval_seconds"] = df["interval_seconds"].fillna(median_interval).clip(lower=0.0)

    df["_steps_raw"] = pd.to_numeric(df[steps_col], errors="coerce").fillna(0.0)

    # Interpret count_unit
    if count_unit == "absolute":
        df["steps_for_agg"] = df["_steps_raw"]
    elif count_unit == "per_second":
        df["steps_for_agg"] = df["_steps_raw"] * df["interval_seconds"]
    elif count_unit == "per_minute":
        df["steps_for_agg"] = df["_steps_raw"] * (df["interval_seconds"] / 60.0)
    elif count_unit == "cumulative":
        if group_col:
            df["_steps_diff"] = df.groupby(group_col)["_steps_raw"].diff().fillna(0.0)
        else:
            df["_steps_diff"] = df["_steps_raw"].diff().fillna(0.0)
        df["_steps_diff"] = df["_steps_diff"].clip(lower=0.0)
        df["steps_for_agg"] = df["_steps_diff"]
    else:
        raise ValueError(f"Unsupported count_unit: {count_unit}")

    df["date_only"] = df[used_date_col].dt.normalize()
    agg = df.groupby("date_only", as_index=False)["steps_for_agg"].sum().rename(columns={"date_only": "date", "steps_for_agg": "steps"})
    agg["steps"] = agg["steps"] * float(scale)
    agg["date"] = pd.to_datetime(agg["date"], utc=True)
    agg = agg.sort_values("date").reset_index(drop=True)
    return agg


def compute_week_start(date_series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(date_series)
    week_start = dates - pd.to_timedelta(dates.dt.weekday, unit="D")
    return week_start.dt.normalize()


def build_weekly_traces(df_daily: pd.DataFrame):
    df = df_daily.copy()
    df["week_start"] = compute_week_start(df["date"])
    df["weekday"] = df["date"].dt.weekday
    weeks = sorted(df["week_start"].unique())
    week_ranges = {}
    for w in weeks:
        week_df = df[df["week_start"] == w]
        s = pd.Series(0.0, index=range(7), dtype=float)
        for _, row in week_df.iterrows():
            s[int(row["weekday"])] = row["steps"]
        week_ranges[w] = s
    return weeks, week_ranges


def make_figure(weeks, week_ranges, default_week=None):
    if not weeks:
        raise ValueError("No weeks available")
    if default_week is None:
        default_week = weeks[-1]

    fig = go.Figure()
    # one trace per week, only default_week visible initially
    for w in weeks:
        y = week_ranges[w].values.tolist()
        label = f"{w.date().isoformat()} → {(w + timedelta(days=6)).date().isoformat()}"
        visible = (w == default_week)
        fig.add_trace(go.Bar(x=WEEKDAY_NAMES, y=y, name=label, visible=visible,
                             hovertemplate="%{x} (%{customdata})<br>Steps: %{y:.0f}<extra></extra>",
                             customdata=[(w + timedelta(days=i)).date().isoformat() for i in range(7)]))
    # buttons: overlay at index 0, weeks afterwards
    buttons = []
    visibility_all = [True] * len(weeks)
    buttons.append(dict(method="update", label="Overlay: All weeks", args=[{"visible": visibility_all}, {"title": "Daily Steps — Overlay of all weeks", "yaxis": {"title": "Steps"}}]))
    for idx, w in enumerate(weeks):
        vis = [False] * len(weeks); vis[idx] = True
        label = f"{w.date().isoformat()} → {(w + timedelta(days=6)).date().isoformat()}"
        buttons.append(dict(method="update", label=label, args=[{"visible": vis}, {"title": f"Daily Steps for week: {label}", "yaxis": {"title": "Steps"}}]))

    # set active to the week's button (overlay is 0 so index = default_idx + 1)
    default_idx = weeks.index(default_week) if default_week in weeks else len(weeks) - 1
    active_index = default_idx + 1

    default_label = f"{weeks[default_idx].date().isoformat()} → {(weeks[default_idx] + timedelta(days=6)).date().isoformat()}"
    fig.update_layout(title=f"Daily Steps for week: {default_label}",
                      updatemenus=[dict(active=active_index, buttons=buttons, x=0.0, y=1.12, xanchor="left", yanchor="top")],
                      xaxis=dict(title="Weekday"), yaxis=dict(title="Steps", tickformat=","), bargap=0.2, template="plotly_white", hovermode="x")
    return fig


def write_files(fig, static_dir: str, output_name: str = "steps_plot.html", launcher_name: str = "steps_launcher.html"):
    os.makedirs(static_dir, exist_ok=True)
    out_path = os.path.join(static_dir, output_name)
    # write HTML for the plot
    pio.write_html(fig, file=out_path, auto_open=False, include_plotlyjs="cdn", full_html=True)
    # write a small launcher that opens the popup window on user click (helps avoid popup blockers)
    launcher_path = os.path.join(static_dir, launcher_name)
    abs_plot = os.path.abspath(out_path).replace("\\", "/")
    # launcher opens the popup sized and focuses it
    launcher_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Open Steps Popup</title></head>
<body>
  <button id="openBtn">Open Steps Popup</button>
  <script>
    document.getElementById('openBtn').addEventListener('click', function() {{
      var url = "file://{abs_plot}";
      var w = window.open(url, "StepsPopup", "width=900,height=600,resizable=yes,scrollbars=yes");
      if(w) {{
        w.focus();
      }} else {{
        alert("Popup blocked — please allow popups or open the file directly: {abs_plot}");
      }}
    }});
  </script>
</body></html>"""
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_html)
    return out_path, launcher_path


def open_native_popup(html_path: str, width: int = 900, height: int = 600):
    # use pywebview to open a native popup window (blocks until closed)
    if not WEBVIEW_AVAILABLE:
        raise RuntimeError("pywebview not available")
    url = "file://" + os.path.abspath(html_path)
    window = webview.create_window("Weekly Steps", url, width=width, height=height, resizable=True)
    webview.start()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interactive weekly step popup")
    parser.add_argument("--data-dir", default="data", help="Directory with CSVs")
    parser.add_argument("--file", default="step_daily_trend.csv", help="CSV filename inside data dir")
    parser.add_argument("--date-col", default=None, help="date column name (auto-detect if omitted)")
    parser.add_argument("--steps-col", default="count", help="steps column name")
    parser.add_argument("--count-unit", choices=["absolute", "per_second", "per_minute", "cumulative"], default="absolute")
    parser.add_argument("--scale", type=float, default=1000.0, help="Multiply aggregated totals by this factor")
    parser.add_argument("--use-webview", action="store_true", help="Open native popup via pywebview (if installed)")
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--static-dir", default=os.path.join("data-analysis", "static"), help="Directory to write static HTML")
    args = parser.parse_args(argv)

    try:
        csv_path = find_csv(args.data_dir, args.file)
    except Exception as e:
        print("Error locating CSV:", e, file=sys.stderr); sys.exit(2)

    try:
        df_daily = load_and_aggregate(csv_path, args.date_col, args.steps_col, args.count_unit, args.scale)
    except Exception as e:
        print("Error loading CSV:", e, file=sys.stderr); traceback.print_exc(); sys.exit(3)

    if df_daily.empty:
        print("No aggregated data found", file=sys.stderr); sys.exit(4)

    weeks, week_ranges = build_weekly_traces(df_daily)

    # pick current week start in tz-aware UTC
    now = datetime.now(timezone.utc)
    current_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    chosen_week = None
    weeks_sorted = sorted(weeks)
    for w in reversed(weeks_sorted):
        if w <= pd.Timestamp(current_week_start):
            chosen_week = w; break
    if chosen_week is None and weeks_sorted:
        chosen_week = weeks_sorted[-1]

    fig = make_figure(weeks_sorted, week_ranges, default_week=chosen_week)

    # write static files
    out_path, launcher_path = write_files(fig, args.static_dir)
    print("Wrote plot to:", out_path)
    print("Wrote launcher to:", launcher_path)

    # open popup: prefer native if requested and available
    if args.use_webview and WEBVIEW_AVAILABLE:
        try:
            open_native_popup(out_path, width=args.width, height=args.height)
            return
        except Exception as e:
            print("pywebview failed:", e, file=sys.stderr)
            traceback.print_exc()

    # otherwise print instructions and open the launcher (which contains a user-clickable button)
    print("\nTo open a small popup from your web UI use JavaScript on a user click (example):")
    print(f'window.open("file://{os.path.abspath(out_path)}", "StepsPopup", "width={args.width},height={args.height},resizable=yes,scrollbars=yes");')
    print(f"Or open the launcher (click the button) at: {os.path.abspath(launcher_path)}")

if __name__ == "__main__":
    main()