"""
Report generator — builds structured report data and renders it to HTML.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# Data gathering
# ------------------------------------------------------------------

def generate_report_data(
    mongo_handler,
    tags: List[Dict],
    start_dt: datetime,
    end_dt: datetime,
    zscore_threshold: float = 2.5,
) -> Dict[str, Any]:
    """
    Fetch and analyse data for all tags.
    Returns a structured dict consumed by render functions.
    """
    tag_reports = []

    for tag in tags:
        docs = mongo_handler.query(tag["path"], start=start_dt, end=end_dt)
        if not docs:
            tag_reports.append(
                {
                    "name": tag.get("name", tag["path"]),
                    "path": tag["path"],
                    "unit": tag.get("unit", ""),
                    "min_range": tag.get("min_range", 0),
                    "max_range": tag.get("max_range", 100),
                    "records": 0,
                    "stats": {},
                    "anomaly_count": 0,
                    "anomaly_pct": 0.0,
                    "trend": "—",
                    "df": pd.DataFrame(),
                }
            )
            continue

        df = pd.DataFrame(docs)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"]).sort_values("timestamp").reset_index(drop=True)
        vals = df["value"].astype(float)

        # Stats
        stats = {
            "Count": int(len(vals)),
            "Mean": round(float(vals.mean()), 4),
            "Std Dev": round(float(vals.std()), 4),
            "Min": round(float(vals.min()), 4),
            "Max": round(float(vals.max()), 4),
            "P25": round(float(vals.quantile(0.25)), 4),
            "Median": round(float(vals.median()), 4),
            "P75": round(float(vals.quantile(0.75)), 4),
            "P95": round(float(vals.quantile(0.95)), 4),
        }

        # Anomalies (Z-score)
        z = np.abs((vals - vals.mean()) / (vals.std() or 1.0))
        n_anom = int((z > zscore_threshold).sum())
        anom_pct = round(100 * n_anom / len(vals), 2)

        # Trend
        if len(vals) > 1:
            slope = float(np.polyfit(np.arange(len(vals)), vals, 1)[0])
            rel = slope / abs(float(vals.mean())) if vals.mean() != 0 else slope
            trend = "↑ Increasing" if rel > 0.001 else "↓ Decreasing" if rel < -0.001 else "→ Stable"
        else:
            trend = "—"

        tag_reports.append(
            {
                "name": tag.get("name", tag["path"]),
                "path": tag["path"],
                "unit": tag.get("unit", ""),
                "min_range": float(tag.get("min_range", 0)),
                "max_range": float(tag.get("max_range", 100)),
                "records": int(len(df)),
                "stats": stats,
                "anomaly_count": n_anom,
                "anomaly_pct": anom_pct,
                "trend": trend,
                "df": df,
            }
        )

    return {
        "generated_at": datetime.now(tz=timezone.utc),
        "period_start": start_dt,
        "period_end": end_dt,
        "tag_count": len(tags),
        "total_records": sum(t["records"] for t in tag_reports),
        "tags": tag_reports,
    }


# ------------------------------------------------------------------
# HTML rendering
# ------------------------------------------------------------------

def render_html_report(report: Dict[str, Any]) -> str:
    """Return a self-contained HTML string with embedded Plotly charts."""
    import plotly.graph_objects as go

    gen_at = report["generated_at"].strftime("%Y-%m-%d %H:%M UTC")
    start_s = report["period_start"].strftime("%d %b %Y %H:%M")
    end_s = report["period_end"].strftime("%d %b %Y %H:%M")

    # ---- summary table rows ----
    summary_rows = ""
    for t in report["tags"]:
        trend_color = (
            "#e74c3c" if "↓" in t["trend"]
            else "#27ae60" if "↑" in t["trend"]
            else "#7f8c8d"
        )
        anom_color = "#e74c3c" if t["anomaly_count"] > 0 else "#27ae60"
        mean_val = f"{t['stats'].get('Mean', '—')} {t['unit']}" if t["stats"] else "No data"
        summary_rows += f"""
        <tr>
          <td><b>{t["name"]}</b></td>
          <td>{t["records"]:,}</td>
          <td>{mean_val}</td>
          <td>{t["stats"].get("Min", "—")} – {t["stats"].get("Max", "—")} {t["unit"]}</td>
          <td style="color:{anom_color}"><b>{t["anomaly_count"]}</b> ({t["anomaly_pct"]}%)</td>
          <td style="color:{trend_color}"><b>{t["trend"]}</b></td>
        </tr>"""

    # ---- per-tag detail sections ----
    tag_sections = ""
    for t in report["tags"]:
        if t["df"].empty:
            tag_sections += f"""
            <div class="tag-card">
              <h3>{t["name"]} ({t["unit"]})</h3>
              <p style="color:#7f8c8d">No data available for this period.</p>
            </div>"""
            continue

        # stats table
        stats_rows = "".join(
            f"<tr><td>{k}</td><td><b>{v} {t['unit']}</b></td></tr>"
            for k, v in t["stats"].items()
        )

        # Plotly chart
        df = t["df"]
        vals = df["value"].astype(float)
        z_scores = np.abs((vals - vals.mean()) / (vals.std() or 1.0))
        anomaly_mask = z_scores > 2.5
        normal_df = df[~anomaly_mask]
        anom_df = df[anomaly_mask]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=normal_df["timestamp"], y=normal_df["value"],
            mode="lines", name="Normal",
            line=dict(color="#4a90e2", width=1.5),
        ))
        if not anom_df.empty:
            fig.add_trace(go.Scatter(
                x=anom_df["timestamp"], y=anom_df["value"],
                mode="markers", name="Anomaly",
                marker=dict(color="#e74c3c", size=8, symbol="circle"),
            ))
        fig.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=10, b=30),
            paper_bgcolor="white",
            plot_bgcolor="#f8f9fa",
            showlegend=True,
            legend=dict(orientation="h"),
            xaxis=dict(showgrid=True, gridcolor="#e9ecef"),
            yaxis=dict(showgrid=True, gridcolor="#e9ecef", title=t["unit"]),
        )
        chart_html = fig.to_html(include_plotlyjs="cdn", full_html=False)

        anom_status = (
            f'<span style="color:#e74c3c">⚠ {t["anomaly_count"]} anomalies ({t["anomaly_pct"]}%)</span>'
            if t["anomaly_count"] > 0
            else '<span style="color:#27ae60">✓ No anomalies</span>'
        )

        tag_sections += f"""
        <div class="tag-card">
          <h3>{t["name"]}
            <span class="badge">{t["unit"]}</span>
            <span class="badge badge-trend">{t["trend"]}</span>
          </h3>
          <div class="grid-2">
            <table class="stats-table">
              <thead><tr><th>Metric</th><th>Value</th></tr></thead>
              <tbody>{stats_rows}</tbody>
            </table>
            <div>
              <p>{anom_status}</p>
              <p><b>Records:</b> {t["records"]:,}</p>
            </div>
          </div>
          {chart_html}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IIoT Report — {start_s} to {end_s}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #2c3e50; }}
  .container {{ max-width: 1100px; margin: 30px auto; padding: 0 20px 40px; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white;
             padding: 32px; border-radius: 12px; margin-bottom: 24px; }}
  .header h1 {{ font-size: 26px; margin-bottom: 6px; }}
  .header p {{ opacity: 0.75; font-size: 14px; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .meta-card {{ background: white; border-radius: 10px; padding: 16px 20px;
                box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .meta-card .label {{ font-size: 11px; text-transform: uppercase; color: #7f8c8d; letter-spacing: .5px; }}
  .meta-card .value {{ font-size: 24px; font-weight: 700; color: #1a1a2e; margin-top: 4px; }}
  .section-title {{ font-size: 18px; font-weight: 600; margin: 28px 0 12px; color: #1a1a2e; }}
  .summary-table {{ width: 100%; background: white; border-radius: 10px;
                    box-shadow: 0 1px 4px rgba(0,0,0,.08); border-collapse: collapse; overflow: hidden; }}
  .summary-table th {{ background: #1a1a2e; color: white; padding: 11px 14px;
                       text-align: left; font-size: 12px; text-transform: uppercase; }}
  .summary-table td {{ padding: 10px 14px; border-bottom: 1px solid #f0f2f5; font-size: 14px; }}
  .summary-table tr:last-child td {{ border-bottom: none; }}
  .tag-card {{ background: white; border-radius: 10px; padding: 22px 24px; margin-bottom: 18px;
               box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .tag-card h3 {{ font-size: 17px; margin-bottom: 14px; color: #1a1a2e; }}
  .badge {{ background: #eef2f7; color: #4a5568; font-size: 12px; font-weight: 500;
            padding: 2px 8px; border-radius: 20px; margin-left: 6px; }}
  .badge-trend {{ background: #e8f5e9; color: #2e7d32; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 16px; }}
  .stats-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .stats-table td {{ padding: 5px 8px; border-bottom: 1px solid #f0f2f5; }}
  .stats-table td:first-child {{ color: #7f8c8d; }}
  .footer {{ text-align: center; color: #aaa; font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏭 Industrial IoT Data Platform</h1>
    <p>Analysis Report &nbsp;·&nbsp; {start_s} → {end_s} UTC</p>
    <p style="margin-top:6px;font-size:12px">Generated: {gen_at}</p>
  </div>

  <div class="meta-grid">
    <div class="meta-card"><div class="label">Tags Analysed</div><div class="value">{report["tag_count"]}</div></div>
    <div class="meta-card"><div class="label">Total Records</div><div class="value">{report["total_records"]:,}</div></div>
    <div class="meta-card"><div class="label">Total Anomalies</div>
      <div class="value" style="color:#e74c3c">{sum(t["anomaly_count"] for t in report["tags"]):,}</div></div>
    <div class="meta-card"><div class="label">Period</div>
      <div class="value" style="font-size:15px">{start_s} – {end_s}</div></div>
  </div>

  <div class="section-title">Summary</div>
  <table class="summary-table">
    <thead>
      <tr><th>Tag</th><th>Records</th><th>Mean</th><th>Range</th><th>Anomalies</th><th>Trend</th></tr>
    </thead>
    <tbody>{summary_rows}</tbody>
  </table>

  <div class="section-title">Tag Details</div>
  {tag_sections}

  <div class="footer">Industrial IoT Data Platform — Open-Source</div>
</div>
</body>
</html>"""
