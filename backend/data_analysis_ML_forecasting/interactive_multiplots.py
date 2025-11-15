#!/usr/bin/env python3
"""
Per-metric interactive popups with stable future forecasting and consistent
aggregation across granularities.

What this does
- Generates reproducible mock daily health data (seedable).
- Aggregates each metric server-side into daily/weekly/monthly/quarterly series
  using consistent rules (sum for steps/calories/water; mean for heart_rate/spo2/sleep).
- Computes a FUTURE forecast (default 14 days) for each metric+granularity pair
  server-side and embeds both the aggregated history and forecast into each metric HTML.
  -> Because history is pre-aggregated and embedded, switching granularity on the client
     will always show the same values (no client re-aggregation discrepancies).
- Forecasting: tries SARIMAX (statsmodels) with safe settings (enforce_invertibility=False,
  enforce_stationarity=False) in a scoped warnings catcher to avoid noisy messages.
  If statsmodels is not available or fitting fails, falls back to a RandomForest iterative forecast.
- Contrasting colors: each metric has main color; forecasts use a contrasting (darker) color;
  steps are green, water is blue as requested.
- No historical backtest (only future forecasts) to keep UI focused and simple.
- Produces one HTML per metric (interactive Plotly, year + granularity selectors) and a small launcher.

Usage
  pip install pandas numpy plotly statsmodels scikit-learn
  python interactive_health_forecast_pergran.py --out-dir data-analysis/static --days 730 --seed 42 --forecast-days 14

Serve and open
  cd data-analysis/static
  python -m http.server 8000
  http://localhost:8000/health_launcher.html

React integration
  Call from an onClick handler (user gesture):
    window.open('/health_dashboard/steps_plot.html', 'StepsPopup', 'width=900,height=600,resizable=yes,scrollbars=yes')
  Adjust paths to match where you serve the generated files.

Notes
- This is intentionally conservative about ARIMA/SARIMAX (uses safe options and scoped warning suppression).
- Because history is pre-aggregated server-side and embedded per granularity, values remain identical when switching granularity.
"""

from __future__ import annotations
import argparse
import json
import os
import random
import warnings
from datetime import datetime, timedelta, timezone
from textwrap import dedent

import numpy as np
import pandas as pd

# Try SARIMAX; if missing we'll use RandomForest fallback
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX  # type: ignore
    HAVE_SARIMAX = True
except Exception:
    HAVE_SARIMAX = False

# sklearn RF fallback
try:
    from sklearn.ensemble import RandomForestRegressor  # type: ignore
    HAVE_SKRF = True
except Exception:
    HAVE_SKRF = False

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.24.1.min.js"

# Per-metric popup sizes and colors
METRIC_POPUP_SIZES = {
    "steps": (900, 600),
    "calories": (1000, 640),
    "heart_rate": (1000, 640),
    "spo2": (900, 600),
    "sleep_hours": (900, 600),
    "water_ml": (900, 600),
}
METRIC_COLORS = {
    "steps": {"main": "#10B981", "forecast": "#86efac"},  # Green for steps (light forecast)
    "calories": {"main": "#F59E0B", "forecast": "#fcd34d"},  # Amber/Orange for calories (light forecast)
    "heart_rate": {"main": "#EF4444", "forecast": "#fca5a5"},  # Red for heart rate (light forecast)
    "spo2": {"main": "#8B5CF6", "forecast": "#c4b5fd"},  # Purple for oxygen (light forecast)
    "sleep_hours": {"main": "#6366F1", "forecast": "#a5b4fc"},  # Indigo for sleep (light forecast)
    "water_ml": {"main": "#3B82F6", "forecast": "#93c5fd"},  # Blue for water (light forecast)
}

# ---------------- Mock data ----------------
def set_seed(seed: int | None):
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)

def generate_mock_health_data(days: int = 730, seed: int | None = 42) -> pd.DataFrame:
    set_seed(seed)
    rng = np.random.default_rng(seed if seed is not None else None)
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [end - timedelta(days=i) for i in reversed(range(days))]
    df = pd.DataFrame({"date": pd.to_datetime(dates)})
    n = len(df)

    base_steps = 5500 + 600 * np.sin(np.linspace(0, 3.5 * np.pi, n))
    trend = np.linspace(0, 800, n)
    noise = rng.normal(0, 600, n)
    df["steps"] = np.clip(base_steps + trend + noise, 0, None).round(0).astype(int)

    df["calories"] = np.clip(1700 + (df["steps"] / 1000) * 70 + rng.normal(0, 60, n), 1200, None).round(0).astype(int)

    hr_base = 62 + 1.8 * np.sin(np.linspace(0, 6 * np.pi, n))
    hr_noise = rng.normal(0, 3.2, n)
    spikes = (rng.random(n) < 0.04).astype(int) * rng.integers(8, 20, n)
    df["heart_rate"] = np.clip(hr_base + hr_noise + spikes, 40, 180).round(1)

    df["spo2"] = np.clip(98 + rng.normal(0, 0.5, n) - 0.2 * (rng.random(n) < 0.02), 90, 100).round(1)

    df["sleep_hours"] = np.clip(7 + rng.normal(0, 1.0, n) + 0.3 * np.sin(np.linspace(0, 4 * np.pi, n)), 0, 13).round(2)

    water_base = 2000 + 300 * np.sin(np.linspace(0, 4 * np.pi, n))
    water_noise = rng.normal(0, 250, n)
    df["water_ml"] = np.clip(water_base + water_noise, 300, 4000).round(0).astype(int)

    return df

# ---------------- Aggregation (server-side explicit freq) ----------------
def aggregate_series(df: pd.DataFrame, value_col: str, gran: str, agg_type: str) -> pd.Series:
    s = df[["date", value_col]].copy()
    s["date"] = pd.to_datetime(s["date"])
    if gran == "daily":
        s["period"] = s["date"].dt.normalize(); freq = "D"
    elif gran == "weekly":
        s["period"] = (s["date"] - pd.to_timedelta(s["date"].dt.weekday, unit="D")).dt.normalize(); freq = "W-MON"
    elif gran == "monthly":
        s["period"] = s["date"].dt.to_period("M").dt.start_time; freq = "MS"
    elif gran == "quarterly":
        s["period"] = s["date"].dt.to_period("Q").dt.start_time; freq = "QS"
    else:
        s["period"] = s["date"].dt.normalize(); freq = "D"

    agg = s.groupby("period", sort=True)[value_col].sum() if agg_type == "sum" else s.groupby("period", sort=True)[value_col].mean()
    idx = pd.to_datetime(agg.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    agg.index = idx
    full_idx = pd.date_range(start=agg.index.min(), end=agg.index.max(), freq=freq, tz="UTC")
    agg = agg.reindex(full_idx)
    if agg_type == "sum":
        agg = agg.fillna(0.0)
    else:
        agg = agg.fillna(method="ffill").fillna(method="bfill")
        if agg.isna().any():
            agg = agg.fillna(float(agg.mean(skipna=True) or 0.0))
    try:
        agg.index.freq = pd.tseries.frequencies.to_offset(freq)
    except Exception:
        pass
    return agg.astype(float)

# ---------------- Forecasting (FUTURE ONLY) ----------------
def forecast_sarimax_safe(series: pd.Series, steps_ahead: int = 14):
    """Forecast future values only using SARIMAX"""
    series = series.dropna()
    if len(series) < 15:
        last = float(series.iloc[-1]) if len(series) else 0.0
        last_dt = series.index[-1] if len(series) else pd.Timestamp(datetime.now(timezone.utc))
        freq_offset = pd.Timedelta(days=1)
        return [last_dt + freq_offset * (i + 1) for i in range(steps_ahead)], [last] * steps_ahead, [last] * steps_ahead, [last] * steps_ahead
    
    # Infer frequency from series
    try:
        freq = pd.infer_freq(series.index)
        if freq:
            freq_offset = pd.tseries.frequencies.to_offset(freq)
        else:
            freq_offset = series.index[-1] - series.index[-2] if len(series) > 1 else pd.Timedelta(days=1)
    except:
        freq_offset = series.index[-1] - series.index[-2] if len(series) > 1 else pd.Timedelta(days=1)
    
    # Scoped suppression for known harmless messages only during fit
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="No frequency information was provided, so inferred frequency")
        warnings.filterwarnings("ignore", message="Non-invertible starting MA parameters found. Using zeros as starting parameters.")
        model = SARIMAX(series, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
        fit = model.fit(disp=False)
        fc = fit.get_forecast(steps=steps_ahead)
        mean = fc.predicted_mean.tolist()
        ci = fc.conf_int(alpha=0.05)
        lower = ci.iloc[:, 0].tolist()
        upper = ci.iloc[:, 1].tolist()
        last_date = pd.to_datetime(series.index[-1])
        dates = [last_date + freq_offset * (i + 1) for i in range(steps_ahead)]
        return dates, mean, lower, upper

def forecast_rf(series: pd.Series, steps_ahead: int = 14, seed: int | None = 42):
    """Forecast future values only using RandomForest"""
    series = series.dropna()
    if len(series) < 10:
        last = float(series.iloc[-1]) if len(series) else 0.0
        last_dt = series.index[-1] if len(series) else pd.Timestamp(datetime.now(timezone.utc))
        freq_offset = pd.Timedelta(days=1)
        return [last_dt + freq_offset * (i + 1) for i in range(steps_ahead)], [last] * steps_ahead, [last] * steps_ahead, [last] * steps_ahead
    
    # Infer frequency
    try:
        freq_offset = series.index[-1] - series.index[-2] if len(series) > 1 else pd.Timedelta(days=1)
    except:
        freq_offset = pd.Timedelta(days=1)
    
    lags = min(7, len(series) - 1)
    df = pd.DataFrame({"y": series.values}, index=series.index)
    for lag in range(1, lags + 1):
        df[f"lag_{lag}"] = df["y"].shift(lag)
    df["t"] = np.arange(len(df))
    df = df.dropna()
    X = df.drop(columns=["y"]).values; y = df["y"].values
    
    if not HAVE_SKRF:
        # Fallback naive
        last = float(series.iloc[-1])
        last_dt = series.index[-1]
        return [last_dt + freq_offset * (i + 1) for i in range(steps_ahead)], [last] * steps_ahead, [last] * steps_ahead, [last] * steps_ahead
    
    rf = RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=-1)
    rf.fit(X, y)
    last_window = series.iloc[-lags:].tolist()
    preds = []; per_tree = []
    
    for step in range(steps_ahead):
        feat = [last_window[-lag] for lag in range(1, lags + 1)]
        feat.append(len(series) + step)
        Xp = np.array(feat).reshape(1, -1)
        tree_preds = np.array([est.predict(Xp)[0] for est in rf.estimators_])
        mean_pred = float(tree_preds.mean())
        preds.append(mean_pred)
        per_tree.append(tree_preds)
        last_window.append(mean_pred); last_window.pop(0)
    
    per_tree = np.vstack(per_tree)
    lower = np.percentile(per_tree, 5, axis=1).tolist()
    upper = np.percentile(per_tree, 95, axis=1).tolist()
    last_date = pd.to_datetime(series.index[-1])
    dates = [last_date + freq_offset * (i + 1) for i in range(steps_ahead)]
    return dates, preds, lower, upper

def forecast_future(series: pd.Series, steps_ahead: int = 14, prefer_rf: bool = False, seed: int | None = 42):
    """Forecast FUTURE values only (no historical backtest)"""
    if prefer_rf or not HAVE_SARIMAX:
        return forecast_rf(series, steps_ahead=steps_ahead, seed=seed)
    try:
        return forecast_sarimax_safe(series, steps_ahead=steps_ahead)
    except Exception:
        return forecast_rf(series, steps_ahead=steps_ahead, seed=seed)

# ---------------- HTML template (fixed year filtering) ----------------
METRIC_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.container {
  width: 100%;
  max-width: 1400px;
}

.card {
  background: #ffffff;
  padding: 32px;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

h2 {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 8px;
}

.subtitle {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 24px;
  font-weight: 500;
}

.controls {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 20px;
  background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
  border-radius: 12px;
  margin-bottom: 24px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.control-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  letter-spacing: 0.3px;
}

select {
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  min-width: 140px;
}

select:hover {
  border-color: #9ca3af;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

select:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

button {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  letter-spacing: 0.3px;
}

button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
}

button:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

#plot {
  width: 100%;
  height: 620px;
  margin-top: 12px;
  border-radius: 12px;
  overflow: hidden;
}

.metric-badge {
  display: inline-block;
  padding: 6px 14px;
  background: __MAIN_COLOR__;
  color: white;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  margin-left: 12px;
  letter-spacing: 0.5px;
}

@media (max-width: 768px) {
  .card {
    padding: 20px;
  }
  
  .controls {
    flex-direction: column;
    align-items: stretch;
  }
  
  .control-group {
    flex-direction: column;
    align-items: stretch;
  }
  
  select, button {
    width: 100%;
  }
  
  h2 {
    font-size: 22px;
  }
}
</style>
<script src="__PLOTLY__"></script>
</head>
<body>
<div class="container">
  <div class="card">
    <h2>__TITLE__<span class="metric-badge">__METRIC_LABEL__</span></h2>
    <div class="subtitle">__SUBTITLE__</div>
    <div class="controls">
      <div class="control-group">
        <span class="control-label">📅 Year:</span>
        <select id="yearSelect"></select>
      </div>
      <div class="control-group">
        <span class="control-label">📊 Granularity:</span>
        <select id="granSelect">
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="quarterly">Quarterly</option>
        </select>
      </div>
      <button id="downloadRaw">💾 Download JSON</button>
    </div>
    <div id="plot"></div>
  </div>
</div>

<script>
const DATA_BY_GRAN = __DATA_BY_GRAN__;   // {daily:{history:{dates,values}, forecast:{...}}, ...}
const RAW_DAILY = __RAW_DAILY__;        // raw daily timestamps + values (for download)
const MAIN_COLOR = "__MAIN_COLOR__";
const FORECAST_COLOR = "__FORECAST_COLOR__";

// Compute years from history (daily gran)
function availableYears(){
  const arr = DATA_BY_GRAN.daily.history.dates.map(d => new Date(d).getUTCFullYear());
  return Array.from(new Set(arr)).sort();
}

function populateYears(){
  const years = availableYears();
  const sel = document.getElementById('yearSelect');
  sel.innerHTML = '<option value="all">All</option>';
  years.forEach(y => { 
    const o = document.createElement('option'); 
    o.value = String(y); 
    o.text = String(y); 
    sel.appendChild(o); 
  });
}

// FIXED: Properly handle year filtering with granularity awareness
function filterHistoryByYear(history, year, gran){
  if(year === 'all') return history;
  const idx = []; 
  const vals = [];
  const yearNum = Number(year);
  
  for(let i=0; i<history.dates.length; i++){
    const d = new Date(history.dates[i]);
    let include = false;
    
    // For granularities that might span year boundaries,
    // include the period if it overlaps with the selected year
    if(gran === 'weekly') {
      // Include if week starts in year OR overlaps with year
      const weekEnd = new Date(d);
      weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
      include = d.getUTCFullYear() === yearNum || weekEnd.getUTCFullYear() === yearNum;
    } 
    else if(gran === 'monthly') {
      // Include if month is in year
      include = d.getUTCFullYear() === yearNum;
    }
    else if(gran === 'quarterly') {
      // Include if quarter starts in year
      include = d.getUTCFullYear() === yearNum;
    }
    else { // daily
      include = d.getUTCFullYear() === yearNum;
    }
    
    if(include){ 
      idx.push(history.dates[i]); 
      vals.push(history.values[i]); 
    }
  }
  return {dates: idx, values: vals};
}

function render(){
  const gran = document.getElementById('granSelect').value;
  const year = document.getElementById('yearSelect').value;
  const hist = DATA_BY_GRAN[gran].history;
  const histFiltered = filterHistoryByYear(hist, year, gran); // Pass gran parameter
  const x = histFiltered.dates;
  const y = histFiltered.values;
  
  Plotly.purge('plot');
  const isBar = "__AGGTYPE__" === "sum" && (gran === 'daily' || gran === 'weekly' || gran === 'monthly' || gran === 'quarterly');
  const baseTrace = isBar 
    ? {x:x, y:y, type:'bar', marker:{color:MAIN_COLOR}, name:'History'} 
    : {x:x, y:y, mode:'lines+markers', line:{color:MAIN_COLOR}, name:'History'};
  const layout = {
    title: "__TITLE__", 
    xaxis:{title:"Period"}, 
    yaxis:{title: "__YLABEL__"},
    hovermode: 'closest'
  };
  
  Plotly.newPlot('plot', [baseTrace], layout, {responsive:true});
  
  // Add forecast (FUTURE ONLY) - always shown regardless of year filter
  const f = DATA_BY_GRAN[gran].forecast;
  if(f && f.dates && f.dates.length){
    Plotly.addTraces('plot', [
      {
        x: f.dates, 
        y: f.values, 
        mode:'lines+markers', 
        line:{dash:'dash', color:FORECAST_COLOR, width: 2.5}, 
        marker:{size:7, color:FORECAST_COLOR, opacity: 0.8},
        name:'Forecast (Future)',
        opacity: 0.85
      }
    ]);
    // Confidence interval with lighter fill
    const xci = f.dates.concat(f.dates.slice().reverse());
    const yci = f.upper.concat(f.lower.slice().reverse());
    Plotly.addTraces('plot', [
      {
        x: xci, 
        y: yci, 
        fill:'toself', 
        fillcolor:'rgba(0,0,0,0.04)', 
        line:{color:'rgba(255,255,255,0)'}, 
        name:'95% CI',
        showlegend: false,
        hoverinfo: 'skip'
      }
    ]);
  }
}

// Debug function to verify stable aggregation
function debugGranularitySwitch() {
  console.log("=== Data Stability Check ===");
  ['daily', 'weekly', 'monthly', 'quarterly'].forEach(gran => {
    const hist = DATA_BY_GRAN[gran].history;
    const sum = hist.values.reduce((a,b) => a+b, 0);
    const avg = sum / hist.values.length;
    console.log(`${gran}: ${hist.dates.length} periods, total=${sum.toFixed(2)}, avg=${avg.toFixed(2)}`);
  });
}

document.addEventListener('DOMContentLoaded', function(){
  populateYears();
  debugGranularitySwitch(); // Log data stability
  document.getElementById('granSelect').addEventListener('change', render);
  document.getElementById('yearSelect').addEventListener('change', render);
  document.getElementById('downloadRaw').addEventListener('click', function(){
    const blob = new Blob([JSON.stringify(RAW_DAILY, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); 
    a.href = url; 
    a.download = '__METRIC__' + '_raw_daily.json'; 
    document.body.appendChild(a); 
    a.click(); 
    a.remove(); 
    URL.revokeObjectURL(url);
  });
  render();
});
</script>
</body></html>
"""

# ---------------- Writer helpers ----------------
def write_json(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)

# ---------------- Build outputs ----------------
def build_outputs(out_dir: str, df: pd.DataFrame, forecast_days: int, seed: int | None, prefer_rf: bool, scale_steps: float):
    os.makedirs(out_dir, exist_ok=True)

    # Scaled steps
    df_steps = df[["date", "steps"]].copy()
    df_steps["steps"] = df_steps["steps"].astype(float) * float(scale_steps)

    metrics = {
        "steps": (df_steps.rename(columns={"steps":"value"}), "Steps (thousands)", METRIC_COLORS["steps"]["main"], METRIC_COLORS["steps"]["forecast"], "sum", "Steps (thousands)"),
        "calories": (df[["date","calories"]].rename(columns={"calories":"value"}), "Calories (kcal)", METRIC_COLORS["calories"]["main"], METRIC_COLORS["calories"]["forecast"], "sum", "kcal"),
        "heart_rate": (df[["date","heart_rate"]].rename(columns={"heart_rate":"value"}), "Heart Rate (BPM)", METRIC_COLORS["heart_rate"]["main"], METRIC_COLORS["heart_rate"]["forecast"], "mean", "BPM"),
        "spo2": (df[["date","spo2"]].rename(columns={"spo2":"value"}), "SpO2 (%)", METRIC_COLORS["spo2"]["main"], METRIC_COLORS["spo2"]["forecast"], "mean", "%"),
        "sleep_hours": (df[["date","sleep_hours"]].rename(columns={"sleep_hours":"value"}), "Sleep (hours)", METRIC_COLORS["sleep_hours"]["main"], METRIC_COLORS["sleep_hours"]["forecast"], "mean", "Hours"),
        "water_ml": (df[["date","water_ml"]].rename(columns={"water_ml":"value"}), "Water (ml)", METRIC_COLORS["water_ml"]["main"], METRIC_COLORS["water_ml"]["forecast"], "sum", "ml"),
    }

    outputs = {}
    for key, (dframe, title, main_color, f_color, agg_type, ylabel) in metrics.items():
        # Build per-gran history + FUTURE forecasts
        data_by_gran = {}
        for gran in ["daily", "weekly", "monthly", "quarterly"]:
            agg_series = aggregate_series(dframe.rename(columns={"date":"date","value":"value"}), "value", gran, agg_type)
            hist_dates = [d.isoformat() for d in agg_series.index.to_pydatetime()]
            hist_values = agg_series.values.tolist()
            
            # Forecast FUTURE values only
            f_dates, f_vals, f_lower, f_upper = forecast_future(agg_series, steps_ahead=forecast_days, prefer_rf=prefer_rf, seed=seed)
            data_by_gran[gran] = {
                "history": {"dates": hist_dates, "values": hist_values},
                "forecast": {"dates": [d.isoformat() for d in f_dates], "values": f_vals, "lower": f_lower, "upper": f_upper}
            }

        # Write metric HTML embedding data_by_gran and raw daily
        raw_daily = [{"timestamp": r["date"].isoformat(), "value": float(r["value"])} for _, r in dframe.iterrows()]
        
        # Metric label for badge
        metric_labels = {
            "steps": "STEPS",
            "calories": "CALORIES", 
            "heart_rate": "HEART",
            "spo2": "OXYGEN",
            "sleep_hours": "SLEEP",
            "water_ml": "WATER"
        }
        
        html = METRIC_HTML.replace("__PLOTLY__", PLOTLY_CDN)\
                          .replace("__TITLE__", title)\
                          .replace("__METRIC_LABEL__", metric_labels.get(key, key.upper()))\
                          .replace("__SUBTITLE__", "Interactive visualization • Switch granularity to view pre-aggregated series with future forecasts")\
                          .replace("__DATA_BY_GRAN__", json.dumps(data_by_gran))\
                          .replace("__RAW_DAILY__", json.dumps(raw_daily))\
                          .replace("__MAIN_COLOR__", main_color)\
                          .replace("__FORECAST_COLOR__", f_color)\
                          .replace("__METRIC__", key)\
                          .replace("__AGGTYPE__", agg_type)\
                          .replace("__YLABEL__", ylabel)
        fname = f"{key}_plot.html"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(html)
        # Write raw daily JSON file (also useful for React)
        write_json(raw_daily, os.path.join(out_dir, f"{key}_data.json"))
        outputs[key] = fname

    # Launcher
    launcher = ["""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>Health Dashboard</title>
<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap' rel='stylesheet'>
<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  padding: 40px 20px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  color: white;
  font-size: 42px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 16px;
  text-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.intro {
  color: rgba(255, 255, 255, 0.95);
  text-align: center;
  font-size: 16px;
  margin-bottom: 12px;
  font-weight: 500;
}

.forecast-note {
  color: rgba(255, 255, 255, 0.85);
  text-align: center;
  font-size: 14px;
  margin-bottom: 40px;
  font-weight: 500;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.metric-card {
  background: white;
  padding: 28px;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  text-align: center;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-main), var(--color-accent));
}

.metric-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}

.metric-icon {
  font-size: 48px;
  margin-bottom: 16px;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.1));
}

.metric-title {
  font-weight: 700;
  font-size: 20px;
  color: #1f2937;
  margin-bottom: 16px;
  letter-spacing: 0.3px;
}

.open-btn {
  width: 100%;
  padding: 14px 24px;
  font-size: 15px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, var(--color-main), var(--color-accent));
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  letter-spacing: 0.5px;
}

.open-btn:hover {
  transform: scale(1.02);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

.metric-note {
  margin-top: 12px;
  color: #9ca3af;
  font-size: 12px;
  font-weight: 500;
}

.footer {
  text-align: center;
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  margin-top: 32px;
  font-weight: 500;
}

/* Metric-specific colors */
.steps-card { --color-main: #10B981; --color-accent: #059669; }
.calories-card { --color-main: #F59E0B; --color-accent: #D97706; }
.heart-card { --color-main: #EF4444; --color-accent: #DC2626; }
.spo2-card { --color-main: #8B5CF6; --color-accent: #7C3AED; }
.sleep-card { --color-main: #6366F1; --color-accent: #4F46E5; }
.water-card { --color-main: #3B82F6; --color-accent: #2563EB; }

@media (max-width: 768px) {
  h1 { font-size: 32px; }
  .grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="container">
  <h1>🏥 Health Dashboard</h1>
  <p class="intro">Click any metric card to explore interactive visualizations</p>
  <p class="forecast-note">📊 All forecasts show future values with ML-powered predictions</p>
  <div class="grid">"""]
    
    metric_info = {
        "steps": ("🚶", "Steps", "steps-card"),
        "calories": ("🔥", "Calories", "calories-card"),
        "heart_rate": ("❤️", "Heart Rate", "heart-card"),
        "spo2": ("💜", "Blood Oxygen", "spo2-card"),
        "sleep_hours": ("😴", "Sleep", "sleep-card"),
        "water_ml": ("💧", "Water Intake", "water-card")
    }
    
    for k, fname in outputs.items():
        if k == "launcher":
            continue
        icon, display_name, card_class = metric_info.get(k, ("📊", k.replace('_',' ').title(), "metric-card"))
        w, h = METRIC_POPUP_SIZES.get(k, (900, 600))
        launcher.append(f"""
    <div class="metric-card {card_class}" onclick="(function(){{
      var w=window.open('./{fname}','{k}Popup','width={w},height={h},resizable=yes,scrollbars=yes'); 
      if(w) w.focus(); 
      else alert('⚠️ Popup blocked — please allow popups or open ./{fname} directly');
    }})()">
      <div class="metric-icon">{icon}</div>
      <div class="metric-title">{display_name}</div>
      <button class="open-btn">View Dashboard</button>
      <div class="metric-note">{fname}</div>
    </div>""")
    launcher.append("""
  </div>
  <div class="footer">
    📁 Files saved in: """ + os.path.abspath(out_dir) + """
  </div>
</div>
</body>
</html>""")
    launcher_path = os.path.join(out_dir, "health_launcher.html")
    with open(launcher_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(launcher))
    outputs["launcher"] = "health_launcher.html"
    return outputs

# ---------------- CLI ----------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Interactive health plots with server-side FUTURE forecasts per granularity")
    parser.add_argument("--out-dir", default=os.path.join("data-analysis","static"), help="output directory")
    parser.add_argument("--days", type=int, default=730, help="days of mock data")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--forecast-days", type=int, default=14, help="future forecast horizon in days (future only, no backtest)")
    parser.add_argument("--prefer-rf", action="store_true", help="force RandomForest fallback (skip SARIMAX)")
    parser.add_argument("--scale-steps", type=float, default=0.001, help="scale factor for steps (divide by 1000 default)")
    args = parser.parse_args(argv)

    df = generate_mock_health_data(days=args.days, seed=args.seed)
    outputs = build_outputs(args.out_dir, df, forecast_days=args.forecast_days, seed=args.seed, prefer_rf=args.prefer_rf, scale_steps=args.scale_steps)
    print("✅ Wrote files to:", os.path.abspath(args.out_dir))
    for k,v in outputs.items():
        print(" ", k, ":", v)
    print("\n📊 All forecasts show FUTURE values only (no historical backtest)")
    print("\n🚀 To serve:")
    print(f"   cd {args.out_dir}")
    print("   python -m http.server 8000")
    print("   Open: http://localhost:8000/health_launcher.html")
    print("\n💡 React integration:")
    print("   window.open('/health_dashboard/steps_plot.html', 'StepsPopup', 'width=900,height=600')")

if __name__ == "__main__":
    main()
