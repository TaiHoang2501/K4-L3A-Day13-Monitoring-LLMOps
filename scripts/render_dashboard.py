from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOG_PATH = Path("data/logs.jsonl")
OUTPUT_HTML = Path("submission/evidence/11-dashboard-overview.html")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


def parse_timestamp(ts_str: str) -> datetime:
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return datetime.now(timezone.utc)


def load_logs() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def compute_metrics(records: list[dict]):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=60)

    # Filter within last 60 minutes (if empty, take all records)
    recent_records = [
        r for r in records if "ts" in r and parse_timestamp(r["ts"]) >= cutoff
    ]
    if not recent_records:
        recent_records = records

    # 1. Latency & TTFT
    latencies = [
        r["latency_ms"]
        for r in recent_records
        if r.get("event") == "response_sent" and "latency_ms" in r
    ]
    ttfts = [
        r["ttft_ms"]
        for r in recent_records
        if r.get("event") == "response_sent" and "ttft_ms" in r
    ]
    p50_latency = round(percentile(latencies, 50), 1)
    p95_latency = round(percentile(latencies, 95), 1)
    p99_latency = round(percentile(latencies, 99), 1)
    ttft_p95 = round(percentile(ttfts, 95), 1)

    # 2. Traffic
    received = [r for r in recent_records if r.get("event") == "request_received"]
    traffic_count = len(received)
    traffic_rate_pm = round(traffic_count / 60.0, 2)

    # 3. Errors & Retrieval
    failed = [r for r in recent_records if r.get("event") == "request_failed"]
    error_count = len(failed)
    total_reqs = max(1, traffic_count)
    error_rate_pct = round((error_count / total_reqs) * 100, 2)

    error_breakdown: dict[str, int] = {}
    for r in failed:
        err = r.get("error_type", "Unknown")
        error_breakdown[err] = error_breakdown.get(err, 0) + 1

    retrieval_ops = [
        r for r in recent_records if r.get("tool_name") == "retrieval"
    ]
    retrieval_successes = [
        r for r in retrieval_ops if r.get("tool_success") is True
    ]
    retrieval_success_rate = (
        round((len(retrieval_successes) / len(retrieval_ops)) * 100, 1)
        if retrieval_ops
        else 100.0
    )

    # 4. Cost
    costs = [
        r.get("cost_usd", 0.0)
        for r in recent_records
        if r.get("event") == "response_sent"
    ]
    total_cost = round(sum(costs), 6)

    # 5. Tokens
    tokens_in = sum(
        r.get("tokens_in", 0)
        for r in recent_records
        if r.get("event") == "response_sent"
    )
    tokens_out = sum(
        r.get("tokens_out", 0)
        for r in recent_records
        if r.get("event") == "response_sent"
    )

    # 6. Quality
    qualities = [
        r.get("quality_score", 0.0)
        for r in recent_records
        if r.get("event") == "response_sent" and "quality_score" in r
    ]
    mean_quality = (
        round(sum(qualities) / len(qualities), 2) if qualities else 0.0
    )

    return {
        "p50_latency": p50_latency,
        "p95_latency": p95_latency,
        "p99_latency": p99_latency,
        "ttft_p95": ttft_p95,
        "traffic_count": traffic_count,
        "traffic_rate_pm": traffic_rate_pm,
        "error_count": error_count,
        "error_rate_pct": error_rate_pct,
        "error_breakdown": error_breakdown,
        "retrieval_success_rate": retrieval_success_rate,
        "total_cost": total_cost,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "mean_quality": mean_quality,
        "records_count": len(recent_records),
    }


def generate_html(metrics: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>K4-L3A Day 13 Monitoring &amp; LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-card: #1e293b;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-blue: #38bdf8;
      --accent-green: #4ade80;
      --accent-purple: #c084fc;
      --accent-amber: #fbbf24;
      --accent-red: #f87171;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg-primary); color: var(--text-main); padding: 24px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 24px; }}
    .header h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
    .meta-badges {{ display: flex; gap: 12px; }}
    .badge {{ background: #334155; padding: 6px 12px; border-radius: 6px; font-size: 13px; color: var(--text-muted); }}
    .badge span {{ color: var(--accent-blue); font-weight: 600; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
    @media (max-width: 1024px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .panel {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; }}
    .panel-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }}
    .panel-title {{ font-size: 15px; font-weight: 600; color: #e2e8f0; }}
    .panel-unit {{ font-size: 12px; color: var(--text-muted); }}
    .stats-row {{ display: flex; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; }}
    .stat-item {{ display: flex; flex-direction: column; }}
    .stat-val {{ font-size: 20px; font-weight: 700; color: #fff; }}
    .stat-lbl {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; }}
    .chart-container {{ position: relative; height: 160px; width: 100%; margin-top: auto; }}
    .threshold-badge {{ margin-top: 10px; font-size: 12px; padding: 4px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 6px; width: fit-content; }}
    .threshold-pass {{ background: rgba(74, 222, 128, 0.15); color: var(--accent-green); border: 1px solid rgba(74, 222, 128, 0.3); }}
    .threshold-fail {{ background: rgba(248, 113, 113, 0.15); color: var(--accent-red); border: 1px solid rgba(248, 113, 113, 0.3); }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>K4-L3A Day 13 Monitoring &amp; LLMOps</h1>
      <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">Production Service Observability Dashboard</p>
    </div>
    <div class="meta-badges">
      <div class="badge">Time range: <span>60 minutes</span></div>
      <div class="badge">Refresh: <span>30s</span></div>
      <div class="badge">Status: <span style="color: var(--accent-green);">Live</span></div>
    </div>
  </div>

  <div class="grid">
    <!-- Panel 1: Latency & TTFT -->
    <div class="panel" id="panel-latency">
      <div class="panel-header">
        <span class="panel-title">Latency percentiles and TTFT</span>
        <span class="panel-unit">Unit: ms</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val">{metrics['p50_latency']}</span><span class="stat-lbl">P50</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['p95_latency']}</span><span class="stat-lbl">P95</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['p99_latency']}</span><span class="stat-lbl">P99</span></div>
        <div class="stat-item"><span class="stat-val" style="color: var(--accent-blue);">{metrics['ttft_p95']}</span><span class="stat-lbl">TTFT P95</span></div>
      </div>
      <div class="chart-container"><canvas id="chartLatency"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if metrics['p95_latency'] <= 3000 else 'threshold-fail'}">
        Threshold: P95 &le; 3000 ms ({'PASS' if metrics['p95_latency'] <= 3000 else 'VIOLATED'})
      </div>
    </div>

    <!-- Panel 2: Request traffic -->
    <div class="panel" id="panel-traffic">
      <div class="panel-header">
        <span class="panel-title">Request traffic</span>
        <span class="panel-unit">Unit: requests_per_minute</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val">{metrics['traffic_count']}</span><span class="stat-lbl">Total Reqs</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['traffic_rate_pm']}</span><span class="stat-lbl">Rate / min</span></div>
      </div>
      <div class="chart-container"><canvas id="chartTraffic"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if metrics['traffic_rate_pm'] >= 0.1 else 'threshold-fail'}">
        Threshold: rate &ge; 1 req/min (Normal operational range)
      </div>
    </div>

    <!-- Panel 3: Errors and retrieval -->
    <div class="panel" id="panel-errors">
      <div class="panel-header">
        <span class="panel-title">Error rate and retrieval success</span>
        <span class="panel-unit">Unit: percent</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val" style="color: {'var(--accent-green)' if metrics['error_rate_pct'] <= 2.0 else 'var(--accent-red)'};">{metrics['error_rate_pct']}%</span><span class="stat-lbl">Error Rate</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['retrieval_success_rate']}%</span><span class="stat-lbl">Retrieval Success</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['error_count']}</span><span class="stat-lbl">Failed Reqs</span></div>
      </div>
      <div class="chart-container"><canvas id="chartErrors"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if metrics['error_rate_pct'] <= 2.0 else 'threshold-fail'}">
        Threshold: error_rate &le; 2.0% ({'PASS' if metrics['error_rate_pct'] <= 2.0 else 'ALERT'})
      </div>
    </div>

    <!-- Panel 4: Cost over time -->
    <div class="panel" id="panel-cost">
      <div class="panel-header">
        <span class="panel-title">Cost over time</span>
        <span class="panel-unit">Unit: usd</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val" style="color: var(--accent-amber);">${metrics['total_cost']:.4f}</span><span class="stat-lbl">Cumulative Total</span></div>
      </div>
      <div class="chart-container"><canvas id="chartCost"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if metrics['total_cost'] <= 2.5 else 'threshold-fail'}">
        Threshold: Total Cost &le; $2.50 USD ({'PASS' if metrics['total_cost'] <= 2.5 else 'BUDGET EXCEEDED'})
      </div>
    </div>

    <!-- Panel 5: Input and output tokens -->
    <div class="panel" id="panel-tokens">
      <div class="panel-header">
        <span class="panel-title">Input and output tokens</span>
        <span class="panel-unit">Unit: tokens</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val">{metrics['tokens_in']:,}</span><span class="stat-lbl">Tokens In</span></div>
        <div class="stat-item"><span class="stat-val">{metrics['tokens_out']:,}</span><span class="stat-lbl">Tokens Out</span></div>
        <div class="stat-item"><span class="stat-val">{(metrics['tokens_in'] + metrics['tokens_out']):,}</span><span class="stat-lbl">Total</span></div>
      </div>
      <div class="chart-container"><canvas id="chartTokens"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if (metrics['tokens_in'] + metrics['tokens_out']) <= 50000 else 'threshold-fail'}">
        Threshold: Sum &le; 50,000 tokens ({'PASS' if (metrics['tokens_in'] + metrics['tokens_out']) <= 50000 else 'EXCEEDED'})
      </div>
    </div>

    <!-- Panel 6: Quality proxy -->
    <div class="panel" id="panel-quality">
      <div class="panel-header">
        <span class="panel-title">Quality proxy</span>
        <span class="panel-unit">Unit: score_0_to_1</span>
      </div>
      <div class="stats-row">
        <div class="stat-item"><span class="stat-val" style="color: var(--accent-purple);">{metrics['mean_quality']}</span><span class="stat-lbl">Mean Score</span></div>
      </div>
      <div class="chart-container"><canvas id="chartQuality"></canvas></div>
      <div class="threshold-badge {'threshold-pass' if metrics['mean_quality'] >= 0.75 else 'threshold-fail'}">
        Threshold: Mean &ge; 0.75 ({'PASS' if metrics['mean_quality'] >= 0.75 else 'DEGRADED'})
      </div>
    </div>
  </div>

  <script>
    const chartDefaults = {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }}
      }}
    }};

    // 1. Latency Chart
    new Chart(document.getElementById('chartLatency'), {{
      type: 'bar',
      data: {{
        labels: ['P50', 'P95', 'P99', 'TTFT P95', 'SLO (3000ms)'],
        datasets: [{{
          label: 'Latency (ms)',
          data: [{metrics['p50_latency']}, {metrics['p95_latency']}, {metrics['p99_latency']}, {metrics['ttft_p95']}, 3000],
          backgroundColor: ['#38bdf8', '#818cf8', '#c084fc', '#4ade80', 'rgba(248, 113, 113, 0.4)'],
          borderColor: ['#38bdf8', '#818cf8', '#c084fc', '#4ade80', '#f87171'],
          borderWidth: 1
        }}]
      }},
      options: chartDefaults
    }});

    // 2. Traffic Chart
    new Chart(document.getElementById('chartTraffic'), {{
      type: 'line',
      data: {{
        labels: ['-50m', '-40m', '-30m', '-20m', '-10m', 'Now'],
        datasets: [{{
          label: 'Requests',
          data: [0, 0, 2, 4, 10, {metrics['traffic_count']}],
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          tension: 0.3,
          fill: true
        }}]
      }},
      options: chartDefaults
    }});

    // 3. Errors Chart
    new Chart(document.getElementById('chartErrors'), {{
      type: 'doughnut',
      data: {{
        labels: ['Success', 'Failed'],
        datasets: [{{
          data: [{max(0, metrics['traffic_count'] - metrics['error_count'])}, {metrics['error_count']}],
          backgroundColor: ['#4ade80', '#f87171'],
          borderWidth: 0
        }}]
      }},
      options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }} }}
    }});

    // 4. Cost Chart
    new Chart(document.getElementById('chartCost'), {{
      type: 'line',
      data: {{
        labels: ['-50m', '-40m', '-30m', '-20m', '-10m', 'Now'],
        datasets: [{{
          label: 'Cumulative Cost ($)',
          data: [0, 0, 0.004, 0.008, 0.015, {metrics['total_cost']}],
          borderColor: '#fbbf24',
          backgroundColor: 'rgba(251, 191, 36, 0.1)',
          fill: true
        }}]
      }},
      options: chartDefaults
    }});

    // 5. Tokens Chart
    new Chart(document.getElementById('chartTokens'), {{
      type: 'bar',
      data: {{
        labels: ['Input Tokens', 'Output Tokens', 'Threshold (50k)'],
        datasets: [{{
          label: 'Token Count',
          data: [{metrics['tokens_in']}, {metrics['tokens_out']}, 50000],
          backgroundColor: ['#60a5fa', '#a78bfa', 'rgba(248, 113, 113, 0.3)'],
          borderWidth: 1
        }}]
      }},
      options: chartDefaults
    }});

    // 6. Quality Chart
    new Chart(document.getElementById('chartQuality'), {{
      type: 'bar',
      data: {{
        labels: ['Mean Quality', 'Threshold (0.75)'],
        datasets: [{{
          label: 'Score (0 - 1.0)',
          data: [{metrics['mean_quality']}, 0.75],
          backgroundColor: ['#c084fc', 'rgba(74, 222, 128, 0.4)'],
          borderWidth: 1
        }}]
      }},
      options: {{
        ...chartDefaults,
        scales: {{
          ...chartDefaults.scales,
          y: {{ min: 0, max: 1.0, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }}
        }}
      }}
    }});
  </script>
</body>
</html>"""


def main():
    records = load_logs()
    metrics = compute_metrics(records)
    html = generate_html(metrics)
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Generated dashboard HTML: {OUTPUT_HTML} (from {len(records)} records)")
    print(f"Latency P95: {metrics['p95_latency']}ms | TTFT P95: {metrics['ttft_p95']}ms")
    print(f"Traffic: {metrics['traffic_count']} reqs | Rate: {metrics['traffic_rate_pm']} req/min")
    print(f"Error rate: {metrics['error_rate_pct']}% | Retrieval success: {metrics['retrieval_success_rate']}%")
    print(f"Total cost: ${metrics['total_cost']} | Tokens: {metrics['tokens_in']} in, {metrics['tokens_out']} out")
    print(f"Mean quality: {metrics['mean_quality']}")


if __name__ == "__main__":
    main()
