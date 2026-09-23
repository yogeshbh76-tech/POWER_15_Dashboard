"""
Power 15 — Professional Live Dashboard
Run: .\venv\Scripts\python.exe dashboard.py
Open: http://localhost:5000
"""
import json, os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

load_dotenv(r"C:\power15_bot\.env")
LOG_FILE  = r"C:\power15_bot\trade_log.json"
CAP_FILE  = r"C:\power15_bot\paper_capital.json"
IST       = pytz.timezone("Asia/Kolkata")

POWER_15_SECTORS = {
    "NATIONALUM":"Metals & Mining","VEDL":"Metals & Mining","HINDALCO":"Metals & Mining","HINDZINC":"Metals & Mining",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Financials","MANAPPURAM":"Financials","ABCAPITAL":"Financials","LTF":"Financials","BAJFINANCE":"Financials",
    "FEDERALBNK":"Private Bank","AUBANK":"Private Bank",
}
SECTOR_COLORS = {
    "Metals & Mining":"#F59E0B",
    "PSU Bank":"#3B82F6",
    "Financials":"#8B5CF6",
    "Private Bank":"#10B981",
}

def get_cmp(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
        r   = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

def load_data():
    trades  = json.load(open(LOG_FILE))  if os.path.exists(LOG_FILE)  else []
    capital = json.load(open(CAP_FILE))  if os.path.exists(CAP_FILE)  else {
        "initial":500000,"available":500000,"invested":0,
        "total_pnl":0,"total_trades":0,"winning_trades":0
    }
    return trades, capital

def build_dashboard():
    trades, capital = load_data()
    open_tr  = [t for t in trades if t["status"] == "OPEN"]
    closed   = [t for t in trades if t["status"] == "CLOSED"]
    now      = datetime.now(IST)

    # Enrich open trades with live prices
    total_unrealised = 0
    enriched = []
    for t in open_tr:
        cmp   = get_cmp(t["symbol"]) or t["entry_price"]
        pnl   = (cmp - t["entry_price"]) * t["quantity"]
        pct   = (cmp - t["entry_price"]) / t["entry_price"] * 100
        days  = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        left  = max(0, 90 - days)
        total_unrealised += pnl
        enriched.append({**t, "cmp":cmp, "pnl":pnl, "pct":pct, "days":days, "left":left,
                         "sector": POWER_15_SECTORS.get(t["symbol"],"Other")})

    total_pnl    = capital["total_pnl"] + total_unrealised
    total_return = (total_pnl / capital["initial"] * 100) if capital["initial"] > 0 else 0
    win_rate     = (capital["winning_trades"] / capital["total_trades"] * 100) if capital["total_trades"] > 0 else 0

    # Sector allocation data for pie chart
    sector_data = {}
    for t in enriched:
        s = t["sector"]
        sector_data[s] = sector_data.get(s, 0) + t["entry_price"] * t["quantity"]

    # Build position rows
    rows = ""
    for t in enriched:
        pnl_color  = "#10B981" if t["pnl"] >= 0 else "#EF4444"
        row_bg     = "rgba(16,185,129,0.05)" if t["pnl"] >= 0 else "rgba(239,68,68,0.05)"
        status     = "🔴 EXIT" if t["days"]>=90 or t["cmp"]<=t["sl_price"] else ("🟡 WATCH" if t["left"]<=10 else "🟢 HOLD")
        progress   = min(100, (t["days"] / 90) * 100)
        rows += f"""
        <tr style="background:{row_bg};border-bottom:1px solid rgba(255,255,255,0.05)">
          <td style="padding:14px 16px">
            <div style="font-weight:700;font-size:15px;color:#F1F5F9">{t["symbol"]}</div>
            <div style="font-size:11px;color:#64748B;margin-top:2px">{t["sector"]}</div>
          </td>
          <td style="padding:14px 16px;color:#94A3B8">Rs.{t["entry_price"]:.2f}</td>
          <td style="padding:14px 16px;font-weight:700;color:#F1F5F9">Rs.{t["cmp"]:.2f}</td>
          <td style="padding:14px 16px;font-weight:700;color:{pnl_color}">{t["pct"]:+.1f}%</td>
          <td style="padding:14px 16px;font-weight:700;color:{pnl_color}">Rs.{t["pnl"]:+.0f}</td>
          <td style="padding:14px 16px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px">
                <div style="width:{progress:.0f}%;height:100%;background:{'#EF4444' if t['left']<=10 else '#F59E0B' if t['left']<=30 else '#10B981'};border-radius:2px"></div>
              </div>
              <span style="font-size:12px;color:#94A3B8;white-space:nowrap">{t["days"]}d / 90d</span>
            </div>
          </td>
          <td style="padding:14px 16px;color:#EF4444;font-size:12px">Rs.{t["sl_price"]:.2f}</td>
          <td style="padding:14px 16px"><span style="font-size:13px">{status}</span></td>
        </tr>"""

    closed_rows = ""
    for t in closed[-10:]:
        pnl   = t.get("pnl", 0)
        pct   = t.get("pnl_pct", 0)
        color = "#10B981" if pnl >= 0 else "#EF4444"
        emoji = "✅" if pnl >= 0 else "❌"
        closed_rows += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
          <td style="padding:12px 16px;font-weight:600;color:#F1F5F9">{emoji} {t["symbol"]}</td>
          <td style="padding:12px 16px;color:#94A3B8">{t["entry_date"]}</td>
          <td style="padding:12px 16px;color:#94A3B8">{t.get("exit_date","—")}</td>
          <td style="padding:12px 16px;color:#94A3B8">Rs.{t["entry_price"]:.2f}</td>
          <td style="padding:12px 16px;color:#94A3B8">Rs.{t.get("exit_price",0):.2f}</td>
          <td style="padding:12px 16px;font-weight:700;color:{color}">Rs.{pnl:+.0f}</td>
          <td style="padding:12px 16px;font-weight:700;color:{color}">{pct:+.1f}%</td>
          <td style="padding:12px 16px;font-size:12px;color:#64748B">{t.get("exit_reason","—")}</td>
        </tr>"""

    # Sector pie chart data
    sector_js = json.dumps([
        {"label": k, "value": round(v), "color": SECTOR_COLORS.get(k,"#6B7280")}
        for k,v in sector_data.items()
    ])

    # P&L history for sparkline (closed trades)
    pnl_history = []
    running = 0
    for t in sorted(closed, key=lambda x: x.get("exit_date","0")):
        running += t.get("pnl",0)
        pnl_history.append(round(running))
    pnl_js = json.dumps(pnl_history if pnl_history else [0])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="120">
<title>Power 15 — Live Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #070B14;
    --surface: #0D1424;
    --surface2: #111827;
    --border: rgba(255,255,255,0.06);
    --text: #F1F5F9;
    --muted: #64748B;
    --green: #10B981;
    --red: #EF4444;
    --yellow: #F59E0B;
    --blue: #3B82F6;
    --purple: #8B5CF6;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; overflow-x:hidden; }}
  body::before {{ content:''; position:fixed; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,transparent,var(--yellow),transparent); z-index:100; }}

  /* Header */
  .header {{ padding:24px 32px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); backdrop-filter:blur(10px); position:sticky; top:0; background:rgba(7,11,20,0.95); z-index:50; }}
  .logo {{ display:flex; align-items:center; gap:12px; }}
  .logo-icon {{ width:36px; height:36px; background:linear-gradient(135deg,#F59E0B,#EF4444); border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:18px; }}
  .logo-text {{ font-family:'Space Mono',monospace; font-size:18px; font-weight:700; letter-spacing:-0.5px; }}
  .logo-text span {{ color:var(--yellow); }}
  .header-right {{ display:flex; align-items:center; gap:20px; }}
  .live-badge {{ display:flex; align-items:center; gap:6px; font-size:12px; color:var(--green); font-family:'Space Mono',monospace; }}
  .live-dot {{ width:7px; height:7px; background:var(--green); border-radius:50%; animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:0.5;transform:scale(1.3)}} }}
  .last-updated {{ font-size:12px; color:var(--muted); font-family:'Space Mono',monospace; }}

  /* Layout */
  .main {{ padding:28px 32px; max-width:1400px; margin:0 auto; }}

  /* Cards Row */
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:24px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:20px; position:relative; overflow:hidden; transition:transform 0.2s; }}
  .card:hover {{ transform:translateY(-2px); }}
  .card::after {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; }}
  .card.green::after {{ background:linear-gradient(90deg,var(--green),transparent); }}
  .card.red::after {{ background:linear-gradient(90deg,var(--red),transparent); }}
  .card.yellow::after {{ background:linear-gradient(90deg,var(--yellow),transparent); }}
  .card.blue::after {{ background:linear-gradient(90deg,var(--blue),transparent); }}
  .card.purple::after {{ background:linear-gradient(90deg,var(--purple),transparent); }}
  .card-label {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; font-family:'Space Mono',monospace; }}
  .card-value {{ font-size:26px; font-weight:700; font-family:'Space Mono',monospace; line-height:1; }}
  .card-sub {{ font-size:12px; color:var(--muted); margin-top:6px; }}
  .card-icon {{ position:absolute; right:16px; top:50%; transform:translateY(-50%); font-size:32px; opacity:0.15; }}

  /* Charts Row */
  .charts-row {{ display:grid; grid-template-columns:1fr 1fr 2fr; gap:16px; margin-bottom:24px; }}
  .chart-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:20px; }}
  .chart-title {{ font-size:13px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.8px; margin-bottom:16px; font-family:'Space Mono',monospace; }}
  canvas {{ max-width:100%; }}

  /* Table */
  .table-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; margin-bottom:24px; overflow:hidden; }}
  .table-header {{ padding:18px 20px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }}
  .table-title {{ font-size:14px; font-weight:600; font-family:'Space Mono',monospace; }}
  .badge {{ background:rgba(245,158,11,0.15); color:var(--yellow); font-size:11px; padding:3px 10px; border-radius:20px; font-family:'Space Mono',monospace; }}
  table {{ width:100%; border-collapse:collapse; }}
  thead th {{ padding:12px 16px; text-align:left; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:0.8px; font-weight:500; border-bottom:1px solid var(--border); font-family:'Space Mono',monospace; }}
  .empty-state {{ padding:48px; text-align:center; color:var(--muted); }}
  .empty-state .emoji {{ font-size:40px; margin-bottom:12px; }}

  /* Capital bar */
  .capital-bar {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:20px; margin-bottom:24px; }}
  .capital-bar-header {{ display:flex; justify-content:space-between; margin-bottom:12px; }}
  .bar-track {{ height:8px; background:rgba(255,255,255,0.08); border-radius:4px; overflow:hidden; }}
  .bar-fill {{ height:100%; border-radius:4px; background:linear-gradient(90deg,var(--green),var(--yellow)); transition:width 1s ease; }}
  .bar-labels {{ display:flex; justify-content:space-between; margin-top:8px; font-size:12px; color:var(--muted); font-family:'Space Mono',monospace; }}

  /* Responsive */
  @media(max-width:1100px) {{ .cards{{grid-template-columns:repeat(3,1fr)}} .charts-row{{grid-template-columns:1fr 1fr}} }}
  @media(max-width:700px) {{ .cards{{grid-template-columns:1fr 1fr}} .charts-row{{grid-template-columns:1fr}} .main{{padding:16px}} }}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div class="logo-text">POWER<span>15</span></div>
  </div>
  <div class="header-right">
    <div class="live-badge"><div class="live-dot"></div>LIVE</div>
    <div class="last-updated">Updated {now.strftime('%d %b %Y %H:%M IST')}</div>
  </div>
</div>

<div class="main">

  <!-- KPI Cards -->
  <div class="cards">
    <div class="card blue">
      <div class="card-label">Available Capital</div>
      <div class="card-value" style="color:var(--blue)">Rs.{capital['available']/1000:.1f}K</div>
      <div class="card-sub">of Rs.{capital['initial']/1000:.0f}K total</div>
      <div class="card-icon">💰</div>
    </div>
    <div class="card {'green' if total_pnl >= 0 else 'red'}">
      <div class="card-label">Total P&L</div>
      <div class="card-value" style="color:{'var(--green)' if total_pnl >= 0 else 'var(--red)'}">Rs.{total_pnl:+,.0f}</div>
      <div class="card-sub">{total_return:+.1f}% return</div>
      <div class="card-icon">{'📈' if total_pnl >= 0 else '📉'}</div>
    </div>
    <div class="card yellow">
      <div class="card-label">Open Positions</div>
      <div class="card-value" style="color:var(--yellow)">{len(open_tr)}</div>
      <div class="card-sub">Rs.{capital['invested']/1000:.1f}K deployed</div>
      <div class="card-icon">📊</div>
    </div>
    <div class="card purple">
      <div class="card-label">Win Rate</div>
      <div class="card-value" style="color:var(--purple)">{win_rate:.0f}%</div>
      <div class="card-sub">{capital['winning_trades']}/{capital['total_trades']} trades</div>
      <div class="card-icon">🎯</div>
    </div>
    <div class="card {'green' if total_unrealised >= 0 else 'red'}">
      <div class="card-label">Unrealised P&L</div>
      <div class="card-value" style="color:{'var(--green)' if total_unrealised >= 0 else 'var(--red)'}">Rs.{total_unrealised:+,.0f}</div>
      <div class="card-sub">{len(open_tr)} open positions</div>
      <div class="card-icon">⚡</div>
    </div>
  </div>

  <!-- Capital Utilisation Bar -->
  <div class="capital-bar">
    <div class="capital-bar-header">
      <span style="font-size:13px;font-weight:600;font-family:'Space Mono',monospace">CAPITAL UTILISATION</span>
      <span style="font-size:13px;color:var(--yellow);font-family:'Space Mono',monospace">{(capital['invested']/capital['initial']*100) if capital['initial']>0 else 0:.1f}% deployed</span>
    </div>
    <div class="bar-track">
      <div class="bar-fill" style="width:{min(100,(capital['invested']/capital['initial']*100)) if capital['initial']>0 else 0:.1f}%"></div>
    </div>
    <div class="bar-labels">
      <span>Rs.0</span>
      <span>Invested: Rs.{capital['invested']:,.0f}</span>
      <span>Rs.{capital['initial']:,.0f}</span>
    </div>
  </div>

  <!-- Charts Row -->
  <div class="charts-row">
    <!-- Sector Allocation Pie -->
    <div class="chart-card">
      <div class="chart-title">Sector Allocation</div>
      {'<canvas id="pieChart" width="220" height="220"></canvas>' if sector_data else '<div class="empty-state"><div class="emoji">🥧</div><div>No positions yet</div></div>'}
    </div>

    <!-- Stock P&L Bar -->
    <div class="chart-card">
      <div class="chart-title">Position P&L</div>
      {'<canvas id="barChart" height="220"></canvas>' if enriched else '<div class="empty-state"><div class="emoji">📊</div><div>No open positions</div></div>'}
    </div>

    <!-- P&L Sparkline -->
    <div class="chart-card">
      <div class="chart-title">Cumulative P&L History</div>
      <canvas id="lineChart" height="220"></canvas>
    </div>
  </div>

  <!-- Open Positions Table -->
  <div class="table-card">
    <div class="table-header">
      <div class="table-title">OPEN POSITIONS</div>
      <div class="badge">{len(open_tr)} ACTIVE</div>
    </div>
    {'<div class="empty-state"><div class="emoji">🚀</div><div style="font-size:15px;margin-bottom:4px">No open positions yet</div><div style="font-size:13px">Buy signals will trigger at 3:30 PM</div></div>' if not enriched else f'''
    <table>
      <thead><tr>
        <th>Symbol</th><th>Entry</th><th>CMP</th><th>Return</th><th>P&L</th><th>Hold Progress</th><th>Stop Loss</th><th>Status</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>'''}
  </div>

  <!-- Closed Trades Table -->
  {'<div class="table-card"><div class="table-header"><div class="table-title">CLOSED TRADES</div><div class="badge">LAST ' + str(min(10,len(closed))) + '</div></div><table><thead><tr><th>Symbol</th><th>Entry Date</th><th>Exit Date</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Return</th><th>Reason</th></tr></thead><tbody>' + closed_rows + '</tbody></table></div>' if closed else ''}

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
Chart.defaults.color = '#64748B';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'DM Sans', sans-serif";

const sectorData = {sector_js};
const pnlHistory = {pnl_js};
const positions  = {json.dumps([{"symbol":t["symbol"],"pnl":round(t["pnl"]),"pct":round(t["pct"],1),"color":SECTOR_COLORS.get(t["sector"],"#6B7280")} for t in enriched])};

// Pie Chart — Sector Allocation
if (sectorData.length > 0 && document.getElementById('pieChart')) {{
  new Chart(document.getElementById('pieChart'), {{
    type: 'doughnut',
    data: {{
      labels: sectorData.map(d => d.label),
      datasets: [{{ data: sectorData.map(d => d.value), backgroundColor: sectorData.map(d => d.color), borderWidth: 2, borderColor: '#0D1424', hoverOffset: 8 }}]
    }},
    options: {{
      cutout: '65%', responsive: true,
      plugins: {{
        legend: {{ position:'bottom', labels:{{ color:'#94A3B8', padding:12, font:{{size:11}} }} }},
        tooltip: {{ callbacks: {{ label: ctx => ` Rs.${{ctx.raw.toLocaleString('en-IN')}}` }} }}
      }}
    }}
  }});
}}

// Bar Chart — Stock P&L
if (positions.length > 0 && document.getElementById('barChart')) {{
  new Chart(document.getElementById('barChart'), {{
    type: 'bar',
    data: {{
      labels: positions.map(p => p.symbol),
      datasets: [{{ label:'P&L (Rs.)', data: positions.map(p => p.pnl),
        backgroundColor: positions.map(p => p.pnl >= 0 ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)'),
        borderColor: positions.map(p => p.pnl >= 0 ? '#10B981' : '#EF4444'),
        borderWidth: 1, borderRadius: 4 }}]
    }},
    options: {{
      responsive: true, indexAxis: 'y',
      plugins: {{ legend: {{ display:false }}, tooltip: {{ callbacks: {{ label: ctx => ` Rs.${{ctx.raw.toLocaleString('en-IN')}}` }} }} }},
      scales: {{ x: {{ grid:{{ color:'rgba(255,255,255,0.05)' }}, ticks:{{ color:'#64748B' }} }}, y: {{ grid:{{ display:false }}, ticks:{{ color:'#F1F5F9', font:{{weight:'600'}} }} }} }}
    }}
  }});
}}

// Line Chart — Cumulative P&L
const lineCtx = document.getElementById('lineChart');
if (lineCtx) {{
  const labels = pnlHistory.map((_,i) => `Trade ${{i+1}}`);
  const isPositive = pnlHistory[pnlHistory.length-1] >= 0;
  new Chart(lineCtx, {{
    type: 'line',
    data: {{
      labels: labels.length > 0 ? labels : ['Start'],
      datasets: [{{ label:'Cumulative P&L', data: pnlHistory.length > 0 ? pnlHistory : [0],
        borderColor: isPositive ? '#10B981' : '#EF4444',
        backgroundColor: isPositive ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
        fill: true, tension: 0.4, pointRadius: 3, pointHoverRadius: 6,
        pointBackgroundColor: isPositive ? '#10B981' : '#EF4444', borderWidth: 2 }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend:{{display:false}}, tooltip:{{ callbacks:{{ label: ctx => ` Rs.${{ctx.raw.toLocaleString('en-IN')}}` }} }} }},
      scales: {{
        x: {{ grid:{{color:'rgba(255,255,255,0.05)'}}, ticks:{{color:'#64748B',maxTicksLimit:6}} }},
        y: {{ grid:{{color:'rgba(255,255,255,0.05)'}}, ticks:{{color:'#64748B', callback: v => 'Rs.'+v.toLocaleString('en-IN')}} }}
      }}
    }}
  }});
}}
</script>
</body>
</html>"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = build_dashboard().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-type","text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)
    def log_message(self, *args): pass

if __name__ == "__main__":
    port = 5000
    print(f"\n{'='*45}")
    print(f"  ⚡ Power 15 Pro Dashboard")
    print(f"  Open: http://localhost:{port}")
    print(f"  Auto-refreshes every 2 minutes")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*45}\n")
    HTTPServer(("", port), DashboardHandler).serve_forever()