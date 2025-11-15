#!/usr/bin/env python3
"""
Generate interactive Plotly health visualizations (one popup HTML per metric) and mock data.

What this script does
- Generates realistic mock daily health data for N days (steps, calories, heart_rate, spo2, sleep_hours, water_ml).
- Builds interactive Plotly visualizations for each metric:
  - steps: weekly bar chart (one trace per week, dropdown to choose week). Default view shows the chosen week only (no overlay).
  - calories: time-series line with rolling average and a simple linear trend forecast (next 7 days) + shaded CI.
  - heart_rate: line + scatter and histogram / boxplot modal (main plot shows time series and avg lines).
  - spo2: scatter/area with threshold band and % below threshold summary.
  - sleep_hours: bar chart (daily) + weekly averages and forecast.
  - water_ml: area chart with rolling mean and forecast.
- Writes static HTML files to data-analysis/static/<metric>.html and a launcher page data-analysis/static/health_launcher.html
  The launcher contains buttons that open small popup windows (via window.open) — this is ideal for triggering from a React click handler.
- All plots are fully interactive Plotly HTML (no server needed).
- Forecast method: a lightweight linear-regression trend fitted to the last 30 days (numpy.polyfit). Produces mean forecast and +/-1.96*residual_std confidence band.

Requirements
- python 3.8+
- pip install pandas numpy plotly

Usage
- Generate mock data and HTMLs:
    python interactive_multi_health_plots.py --out-dir data-analysis/static --days 180 --scale-steps 1000
- Open data-analysis/static/health_launcher.html in a browser (or use window.open("/path/to/static/steps.html", ... ) from React).
- From React you should call: window.open("/static/steps_plot.html", "StepsPopup", "width=900,height=600") (see the sample React snippet below).

Notes about integration with React
- The launcher HTML created is designed to be opened directly (it contains clickable buttons which call window.open). Use that or call window.open to the specific metric HTML from a button click in your React app.
- If you need a native desktop popup instead, install pywebview and adapt the script to call webview.create_window for the file:// path (not included here to keep installation minimal).

Output files (written to --out-dir):
- steps_plot.html
- calories_plot.html
- heart_rate_plot.html
- spo2_plot.html
- sleep_plot.html
- water_plot.html
- health_launcher.html  (tiny page with buttons that open each popup)

"""

from __future__ import annotations
import argparse
import os
import json
from datetime import datetime, timedelta
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

# ------- Utilities: mock data & simple forecasting ------------------


def generate_mock_health_data(days: int = 180, seed: int | None = 42) -> pd.DataFrame:
    """
    Generate mock daily health metrics for `days` days ending today (UTC).
    Columns:
      date, steps, calories, heart_rate (resting average), spo2 (percent), sleep_hours, water_ml
    """
    rng = np.random.default_rng(seed)
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [end - timedelta(days=i) for i in reversed(range(days))]
    df = pd.DataFrame({"date": pd.to_datetime(dates)})
    # Steps: base sinusoidal weekly pattern + trend + noise
    base_steps = 6000 + 500 * np.sin(np.linspace(0, 3.5 * math.pi, days))  # weekly-ish variation
    trend = np.linspace(0, 1200, days)  # gentle upward trend across period
    steps_noise = rng.normal(0, 800, size=days)
    df["steps"] = np.clip(base_steps + trend + steps_noise, 0, None)

    # calories: correlate with steps (roughly)
    calories_base = 1800 + (df["steps"] / 1000) * 80 + rng.normal(0, 60, size=days)
    df["calories"] = np.clip(calories_base, 1200, None)

    # heart_rate (resting): mean ~ 62, with day-to-day noise and occasional spikes
    hr_base = 62 + 2 * np.sin(np.linspace(0, 6 * math.pi, days))
    hr_noise = rng.normal(0, 4, size=days)
    hr_spikes = rng.choice([0, 1], size=days, p=[0.95, 0.05]) * rng.integers(10, 25, size=days)
    df["heart_rate"] = np.clip(hr_base + hr_noise + hr_spikes, 40, 180)

    # spo2: mostly high (96-99) small random dips
    df["spo2"] = np.clip(98 + rng.normal(0, 0.6, size=days) - 0.2 * (rng.random(days) < 0.02), 90, 100)

    # sleep: average ~ 7h +/- 1.2, occasional long or short nights
    df["sleep_hours"] = np.clip(7 + rng.normal(0, 1.1, size=days) + 0.3 * np.sin(np.linspace(0, 4 * math.pi, days)), 0, 13)

    # water intake: ml per day, ~2000-3000 ml plus randomness
    df["water_ml"] = np.clip(2000 + 500 * np.sin(np.linspace(0, 4 * math.pi, days)) + rng.normal(0, 350, size=days), 200, 10000)

    # Round reasonable columns
    df["steps"] = df["steps"].round(0)
    df["calories"] = df["calories"].round(0)
    df["heart_rate"] = df["heart_rate"].round(1)
    df["spo2"] = df["spo2"].round(1)
    df["sleep_hours"] = df["sleep_hours"].round(2)
    df["water_ml"] = df["water_ml"].round(0)

    return df


def simple_linear_forecast(series: pd.Series, days_ahead: int = 7, fit_days: int = 30):
    """
    Fit a simple linear trend on the last `fit_days` points and forecast `days_ahead` days.
    Returns forecast_index (datetime), forecast_values (np.array), lower_ci, upper_ci
    Lower/upper computed using residual std (approx).
    """
    y = series.dropna()
    if len(y) < 5:
        # not enough data: repeat last value
        last = y.iloc[-1] if len(y) > 0 else 0.0
        last_idx = series.index[-1]
        return [last_idx + timedelta(days=i + 1) for i in range(days_ahead)], np.full(days_ahead, last), np.full(days_ahead, last), np.full(days_ahead, last)

    y_tail = y[-fit_days:]
    # x as integer days
    x = np.arange(len(y_tail))
    coeffs = np.polyfit(x, y_tail.values, deg=1)
    slope, intercept = coeffs[0], coeffs[1]
    # residual std
    preds_in_sample = slope * x + intercept
    resid = y_tail.values - preds_in_sample
    resid_std = float(np.nanstd(resid))
    # forecasts
    start = y_tail.index[-1]
    xs_fore = np.arange(len(y_tail), len(y_tail) + days_ahead)
    fcasts = slope * xs_fore + intercept
    # CI using resid_std (approx normal)
    lower = fcasts - 1.96 * resid_std
    upper = fcasts + 1.96 * resid_std
    # build datetime index (assume index is datetime)
    dt_index = []
    last_date = y.index[-1]
    for i in range(days_ahead):
        dt_index.append(pd.to_datetime(last_date) + timedelta(days=i + 1))
    return dt_index, fcasts, lower, upper


# ------- Plot builders for each metric ---------------------------------


def build_steps_weekly_plot(df: pd.DataFrame, default_week_start=None):
    # Aggregate by date (already aggregated), compute week_start (Monday)
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["week_start"] = data["date"] - pd.to_timedelta(data["date"].dt.weekday, unit="D")
    data["weekday"] = data["date"].dt.weekday  # 0..6
    weeks = sorted(data["week_start"].unique())
    # Build week_ranges dict
    week_ranges = {}
    for w in weeks:
        week_df = data[data["week_start"] == w]
        s = pd.Series(0, index=range(7), dtype=float)
        for _, r in week_df.iterrows():
            s[int(r["weekday"])] = float(r["steps"])
        week_ranges[pd.Timestamp(w)] = s

    if default_week_start is None:
        default_week_start = weeks[-1]

    # Build figure: one trace per week, only default visible
    fig = go.Figure()
    for w in weeks:
        y = week_ranges[pd.Timestamp(w)].values.tolist()
        label = f"{pd.to_datetime(w).date().isoformat()} → {(pd.to_datetime(w) + timedelta(days=6)).date().isoformat()}"
        visible = (pd.Timestamp(w) == pd.Timestamp(default_week_start))
        fig.add_trace(go.Bar(x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], y=y, name=label, visible=visible,
                             hovertemplate="%{x} (%{customdata})<br>Steps: %{y:.0f}<extra></extra>",
                             customdata=[(pd.to_datetime(w) + timedelta(days=i)).date().isoformat() for i in range(7)]))

    # Build dropdown buttons: overlay + per-week choices
    buttons = []
    # overlay
    visibility_all = [True] * len(weeks)
    buttons.append(dict(method="update", label="Overlay: All weeks",
                        args=[{"visible": visibility_all},
                              {"title": "Daily Steps — Overlay of all weeks", "yaxis": {"title": "Steps"}}]))
    for idx, w in enumerate(weeks):
        vis = [False] * len(weeks)
        vis[idx] = True
        label = f"{pd.to_datetime(w).date().isoformat()} → {(pd.to_datetime(w) + timedelta(days=6)).date().isoformat()}"
        buttons.append(dict(method="update", label=label,
                            args=[{"visible": vis},
                                  {"title": f"Daily Steps for week: {label}", "yaxis": {"title": "Steps"}}]))

    # compute active index: overlay is 0, default week button index = idx + 1
    default_idx = weeks.index(default_week_start) if default_week_start in weeks else len(weeks) - 1
    active_index = default_idx + 1

    default_label = f"{pd.to_datetime(default_week_start).date().isoformat()} → {(pd.to_datetime(default_week_start) + timedelta(days=6)).date().isoformat()}"
    fig.update_layout(title=f"Daily Steps for week: {default_label}",
                      updatemenus=[dict(active=active_index, buttons=buttons, x=0.0, y=1.12, xanchor="left", yanchor="top")],
                      xaxis=dict(title="Weekday"),
                      yaxis=dict(title="Steps", tickformat=","),
                      template="plotly_white",
                      bargap=0.2)
    return fig


def build_line_with_forecast(df: pd.DataFrame, column: str, ylabel: str, rolling: int = 7):
    data = df.copy().set_index("date").sort_index()
    series = data[column]
    # rolling mean for smoothing
    rolling_mean = series.rolling(rolling, min_periods=1).mean()
    # forecast based on last 30 days
    forecast_idx, fcasts, lower, upper = simple_linear_forecast(series, days_ahead=7, fit_days=30)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines+markers", name=ylabel, line=dict(color="#636efa")))
    fig.add_trace(go.Scatter(x=rolling_mean.index, y=rolling_mean.values, mode="lines", name=f"{rolling}-day avg", line=dict(color="#ef553b")))
    # forecast trace
    fig.add_trace(go.Scatter(x=forecast_idx, y=fcasts, mode="lines+markers", name="Forecast", line=dict(color="#00cc96", dash="dash")))
    # CI shading
    fig.add_trace(go.Scatter(x=list(forecast_idx) + list(reversed(forecast_idx)), y=list(upper) + list(reversed(lower)),
                             fill="toself", fillcolor="rgba(0,204,150,0.15)", line=dict(color="rgba(255,255,255,0)"),
                             showlegend=True, name="Forecast CI"))

    fig.update_layout(title=f"{ylabel} (history + forecast)", xaxis_title="Date", yaxis_title=ylabel, template="plotly_white")
    return fig


def build_heart_rate_plot(df: pd.DataFrame):
    data = df.copy().set_index("date").sort_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["heart_rate"], mode="lines+markers", name="Heart Rate (bpm)", line=dict(color="#636efa")))
    avg = data["heart_rate"].mean()
    fig.add_trace(go.Scatter(x=[data.index.min(), data.index.max()], y=[avg, avg], mode="lines", name=f"Avg {avg:.1f} bpm", line=dict(color="#00cc96", dash="dash")))
    fig.update_layout(title="Heart rate (daily) — interactive", xaxis_title="Date", yaxis_title="BPM", template="plotly_white")
    return fig


def build_spo2_plot(df: pd.DataFrame):
    data = df.copy().set_index("date").sort_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["spo2"], mode="markers+lines", name="SpO2", line=dict(color="#FFA15A")))
    # threshold band
    fig.add_trace(go.Scatter(x=list(data.index) + list(reversed(data.index)),
                             y=list(np.full(len(data.index), 95.0)) + list(reversed(np.full(len(data.index), 100.0))),
                             fill="toself", fillcolor="rgba(255,165,0,0.08)", line=dict(color="rgba(255,165,0,0)"),
                             name="95-100% band"))
    fig.update_layout(title="Blood oxygen (SpO2)", xaxis_title="Date", yaxis_title="SpO2 (%)", template="plotly_white")
    return fig


def build_sleep_plot(df: pd.DataFrame):
    data = df.copy().set_index("date").sort_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=data.index, y=data["sleep_hours"], name="Sleep (hours)", marker_color="#AB63FA"))
    # weekly average line
    weekly_avg = data["sleep_hours"].rolling(7, min_periods=1).mean()
    fig.add_trace(go.Scatter(x=weekly_avg.index, y=weekly_avg.values, mode="lines", name="7-day avg", line=dict(color="#19D3F3")))
    fig.update_layout(title="Sleep hours (daily)", xaxis_title="Date", yaxis_title="Hours", template="plotly_white")
    return fig


def build_water_plot(df: pd.DataFrame):
    data = df.copy().set_index("date").sort_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["water_ml"], mode="lines", fill="tozeroy", name="Water (ml)", line=dict(color="#00CC96")))
    # 7-day rolling
    fig.add_trace(go.Scatter(x=data.index, y=data["water_ml"].rolling(7, min_periods=1).mean(), mode="lines", name="7-day avg", line=dict(color="#636efa")))
    fig.update_layout(title="Water intake (ml)", xaxis_title="Date", yaxis_title="ml", template="plotly_white")
    return fig


# ------- File write helpers -------------------------------------------


def write_plot_html(fig: go.Figure, out_path: str):
    # include_plotlyjs=cdn keeps file smaller and reusable
    pio.write_html(fig, file=out_path, auto_open=False, include_plotlyjs="cdn", full_html=True)


def build_all_outputs(df: pd.DataFrame, out_dir: str, scale_steps: float = 1.0):
    os.makedirs(out_dir, exist_ok=True)
    # apply step scaling if requested
    df2 = df.copy()
    if scale_steps != 1.0 and "steps" in df2.columns:
        df2["steps"] = df2["steps"].astype(float) * float(scale_steps)

    # Steps: determine default week start (most recent week in data)
    df2 = df2.sort_values("date").reset_index(drop=True)
    last_date = pd.to_datetime(df2["date"]).max()
    current_week_start = (last_date - pd.to_timedelta(pd.to_datetime(last_date).weekday(), unit="D")).normalize()
    steps_fig = build_steps_weekly_plot(df2, default_week_start=current_week_start)
    steps_path = os.path.join(out_dir, "steps_plot.html")
    write_plot_html(steps_fig, steps_path)

    calories_fig = build_line_with_forecast(df2[["date", "calories"]].rename(columns={"calories": "calories"}), column="calories", ylabel="Calories")
    calories_path = os.path.join(out_dir, "calories_plot.html")
    write_plot_html(calories_fig, calories_path)

    hr_fig = build_heart_rate_plot(df2[["date", "heart_rate"]].rename(columns={"heart_rate": "heart_rate"}))
    hr_path = os.path.join(out_dir, "heart_rate_plot.html")
    write_plot_html(hr_fig, hr_path)

    spo2_fig = build_spo2_plot(df2[["date", "spo2"]].rename(columns={"spo2": "spo2"}))
    spo2_path = os.path.join(out_dir, "spo2_plot.html")
    write_plot_html(spo2_fig, spo2_path)

    sleep_fig = build_sleep_plot(df2[["date", "sleep_hours"]].rename(columns={"sleep_hours": "sleep_hours"}))
    sleep_path = os.path.join(out_dir, "sleep_plot.html")
    write_plot_html(sleep_fig, sleep_path)

    water_fig = build_water_plot(df2[["date", "water_ml"]].rename(columns={"water_ml": "water_ml"}))
    water_path = os.path.join(out_dir, "water_plot.html")
    write_plot_html(water_fig, water_path)

    # Create a launcher HTML that provides easy popup buttons; this launcher calls window.open on click.
    launcher_html = build_launcher_html({
        "Steps": os.path.abspath(steps_path),
        "Calories": os.path.abspath(calories_path),
        "HeartRate": os.path.abspath(hr_path),
        "SpO2": os.path.abspath(spo2_path),
        "Sleep": os.path.abspath(sleep_path),
        "Water": os.path.abspath(water_path),
    })
    launcher_path = os.path.join(out_dir, "health_launcher.html")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_html)

    return {
        "steps": steps_path,
        "calories": calories_path,
        "heart_rate": hr_path,
        "spo2": spo2_path,
        "sleep": sleep_path,
        "water": water_path,
        "launcher": launcher_path,
    }


def build_launcher_html(mapping: dict[str, str]) -> str:
    # mapping: FriendlyName -> absolute file path
    buttons_html = []
    for label, abs_path in mapping.items():
        safe = abs_path.replace("\\", "/")
        # create JS that opens a small popup (user must click in browser to avoid popup blockers)
        btn = f"""<button onclick="(function(){{var w = window.open('file://{safe}','{label}Popup','width=900,height=600,resizable=yes,scrollbars=yes'); if(w) w.focus(); else alert('Popup blocked - please allow popups or open the file: {safe}');}})()">{label}</button>"""
        buttons_html.append(btn)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Health Plots Launcher</title></head>
<body>
  <h2>Health Plots Launcher</h2>
  <p>Click a button to open a small popup with the selected metric.</p>
  {" ".join(buttons_html)}
  <p>Files are stored on disk in the static folder. Use the absolute path or serve them via a static web server.</p>
</body></html>"""
    return html


# ---------- Command line ------------------------------------------------


def main_cli(argv=None):
    parser = argparse.ArgumentParser(description="Generate interactive health plots (static HTML) from mock data")
    parser.add_argument("--out-dir", default=os.path.join("data-analysis", "static"), help="Directory to write static HTML files")
    parser.add_argument("--days", type=int, default=180, help="Number of days of mock data to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--scale-steps", type=float, default=1000.0, help="Multiply steps totals by this factor (e.g., 1000)")
    parser.add_argument("--no-launcher", action="store_true", help="Do not create the launcher.html file")
    args = parser.parse_args(argv)

    df = generate_mock_health_data(days=args.days, seed=args.seed)
    outputs = build_all_outputs(df, out_dir=args.out_dir, scale_steps=args.scale_steps)
    print("Wrote files:")
    for k, v in outputs.items():
        print(f"  {k}: {v}")
    if args.no_launcher:
        print("Launcher not written (--no-launcher).")
    else:
        print("Open the launcher to open popups (click required for popup):", outputs["launcher"])


if __name__ == "__main__":
    main_cli()