"""
Power 15 — Cloud Dashboard (Render.com deployable)
Reads from Supabase, serves professional dashboard
"""
import os, json, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
IST = pytz.timezone("Asia/Kolkata")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

SECTOR_COLORS = {
    "Metals & Mining": "#F59E0B",
    "PSU Bank":        "#3B82F6",
    "Financials":      "#8B5CF6",
    "Private Bank":    "#10B981",
}
POWER_15_SECTORS = {
    "NATIONALUM":"Metals & Mining","VEDL":"Metals & Mining","HINDALCO":"Metals & Mining","HINDZINC":"Metals & Mining",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Financials","MANAPPURAM":"Financials","ABCAPITAL":"Financials","LTF":"Financials","BAJFINANCE":"Financials",
    "FEDERALBNK":"Private Bank","AUBANK":"Private Bank",
}

def fetch_supabase(table):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def get_cmp(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
        r   = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

def build_dashboard():
    now     = datetime.now(IST)
    trades  = fetch_supabase("p15_trades")
    cap_row = fetch_supabase("p15_capital")
    capital = cap_row[0] if cap_row else {
        "initial":500000,"available":500000,"invested":0,
        "total_pnl":0,"total_trades":0,"winning_trades":0
    }

    open_tr = [t for t in trades if t.get("status") == "OPEN"]
    closed  = [t for t in trades if t.get("status") == "CLOSED"]

    # Enrich with live prices
    enriched = []
    total_unrealised = 0
    for t in open_tr:
        cmp  = get_cmp(t["symbol"]) or t["entry_price"]
        pnl  = (cmp - t["entry_price"]) * t["quantity"]
        pct  = (cmp - t["entry_price"]) / t["entry_price"] * 100
        days = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
        left = max(0, 90 - days)
        total_unrealised += pnl
        enriched.append({**t, "cmp":cmp, "pnl":pnl, "pct":pct, "days":days, "left":left,
                         "sector": POWER_15_SECTORS.get(t["symbol"], "Other")})

    total_pnl    = capital["total_pnl"] + total_unrealised
    total_return = (total_pnl / capital["initial"] * 100) if capital["initial"] > 0 else 0
    win_rate     = (capital["winning_trades"] / capital["total_trades"] * 100) if capital["total_trades"] > 0 else 0

    # Sector allocation
    sector_data = {}
    for t in enriched:
        s = t["sector"]
        sector_data[s] = sector_data.get(s, 0) + t["entry_price"] * t["quantity"]

    # P&L history
    pnl_history = []
    running = 0
    for t in sorted(closed, key=lambda x: x.get("exit_date","0")):
        running += t.get("pnl", 0)
        pnl_history.append(round(running))

    # Build rows
    rows = ""
    for t in enriched:
        pnl_color = "#10B981" if t["pnl"] >= 0 else "#EF4444"
        row_bg    = "rgba(16,185,129,0.05)" if t["pnl"] >= 0 else "rgba(239,68,68,0.05)"
        status    = "EXIT" if t["days"] >= 90 or t["cmp"] <= t["sl_price"] else ("WATCH" if t["left"] <= 10 else "HOLD")
        s_color   = "#EF4444" if status == "EXIT" else "#F59E0B" if status == "WATCH" else "#10B981"
        progress  = min(100, (t["days"] / 90) * 100)
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
              <div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;min-width:80px">
                <div style="width:{progress:.0f}%;height:100%;background:{'#EF4444' if t['left']<=10 else '#F59E0B' if t['left']<=30 else '#10B981'};border-radius:2px"></div>
              </div>
              <span style="font-size:12px;color:#94A3B8;white-space:nowrap">{t["days"]}d / 90d</span>
            </div>
          </td>
          <td style="padding:14px 16px;color:#EF4444;font-size:12px">Rs.{t["sl_price"]:.2f}</td>
          <td style="padding:14px 16px"><span style="color:{s_color};font-weight:600;font-size:13px">{status}</span></td>
        </tr>"""

    closed_rows = ""
    for t in sorted(closed, key=lambda x: x.get("exit_date","0"), reverse=True)[:10]:
        pnl   = t.get("pnl", 0)
        pct   = t.get("pnl_pct", 0)
        color = "#10B981" if pnl >= 0 else "#EF4444"
        emoji = "+" if pnl >= 0 else "-"
        closed_rows += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
          <td style="padding:12px 16px;font-weight:600;color:#F1F5F9">{t["symbol"]}</td>
          <td style="padding:12px 16px;color:#94A3B8">{t.get("entry_date","")}</td>
          <td style="padding:12px 16px;color:#94A3B8">{t.get("exit_date","")}</td>
          <td style="padding:12px 16px;color:#94A3B8">Rs.{t["entry_price"]:.2f}</td>
          <td style="padding:12px 16px;color:#94A3B8">Rs.{t.get("exit_price",0):.2f}</td>
          <td style="padding:12px 16px;font-weight:700;color:{color}">Rs.{pnl:+.0f}</td>
          <td style="padding:12px 16px;font-weight:700;color:{color}">{pct:+.1f}%</td>
          <td style="padding:12px 16px;font-size:11px;color:#64748B">{t.get("exit_reason","")}</td>
        </tr>"""

    sector_js = json.dumps([{"label":k,"value":round(v),"color":SECTOR_COLORS.get(k,"#6B7280")} for k,v in sector_data.items()])
    pnl_js    = json.dumps(pnl_history if pnl_history else [0])
    pos_js    = json.dumps([{"symbol":t["symbol"],"pnl":round(t["pnl"]),"color":SECTOR_COLORS.get(t["sector"],"#6B7280")} for t in enriched])
    invested_pct = min(100, (capital["invested"] / capital["initial"] * 100)) if capital["initial"] > 0 else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="120">
<title>Power 15 — Live Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#070B14;--surf:#0D1424;--surf2:#111827;--bdr:rgba(255,255,255,0.06);--txt:#F1F5F9;--muted:#64748B;--green:#10B981;--red:#EF4444;--yellow:#F59E0B;--blue:#3B82F6;--purple:#8B5CF6}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;overflow-x:hidden}}
body::before{{content:'';position:fixed;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--yellow),var(--red),transparent);z-index:100}}
.header{{padding:20px 28px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--bdr);position:sticky;top:0;background:rgba(7,11,20,0.97);backdrop-filter:blur(12px);z-index:50}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:34px;height:34px;background:linear-gradient(135deg,#F59E0B,#EF4444);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:17px}}
.logo-text{{font-family:'Space Mono',monospace;font-size:17px;font-weight:700;letter-spacing:-0.5px}}
.logo-text span{{color:var(--yellow)}}
.live-badge{{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--green);font-family:'Space Mono',monospace;background:rgba(16,185,129,0.1);padding:5px 10px;border-radius:20px;border:1px solid rgba(16,185,129,0.2)}}
.live-dot{{width:6px;height:6px;background:var(--green);border-radius:50%;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:0.4;transform:scale(1.4)}}}}
.updated{{font-size:11px;color:var(--muted);font-family:'Space Mono',monospace}}
.main{{padding:24px 28px;max-width:1440px;margin:0 auto}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:20px}}
.card{{background:var(--surf);border:1px solid var(--bdr);border-radius:14px;padding:18px;position:relative;overflow:hidden;transition:transform 0.2s,box-shadow 0.2s}}
.card:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,0.3)}}
.card::after{{content:'';position:absolute;top:0;left:0;right:0;height:2px}}
.card.green::after{{background:linear-gradient(90deg,var(--green),transparent)}}
.card.red::after{{background:linear-gradient(90deg,var(--red),transparent)}}
.card.yellow::after{{background:linear-gradient(90deg,var(--yellow),transparent)}}
.card.blue::after{{background:linear-gradient(90deg,var(--blue),transparent)}}
.card.purple::after{{background:linear-gradient(90deg,var(--purple),transparent)}}
.card-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px;font-family:'Space Mono',monospace}}
.card-value{{font-size:24px;font-weight:700;font-family:'Space Mono',monospace;line-height:1}}
.card-sub{{font-size:11px;color:var(--muted);margin-top:5px}}
.capbar{{background:var(--surf);border:1px solid var(--bdr);border-radius:14px;padding:18px;margin-bottom:20px}}
.capbar-top{{display:flex;justify-content:space-between;margin-bottom:10px;font-size:12px}}
.bar-track{{height:6px;background:rgba(255,255,255,0.07);border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--green),var(--yellow));transition:width 1.2s ease}}
.bar-labels{{display:flex;justify-content:space-between;margin-top:6px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace}}
.charts{{display:grid;grid-template-columns:220px 1fr 2fr;gap:14px;margin-bottom:20px}}
.chart-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:14px;padding:18px}}
.chart-title{{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;font-family:'Space Mono',monospace}}
.tcard{{background:var(--surf);border:1px solid var(--bdr);border-radius:14px;margin-bottom:20px;overflow:hidden}}
.thead{{padding:16px 18px;border-bottom:1px solid var(--bdr);display:flex;justify-content:space-between;align-items:center}}
.ttitle{{font-size:12px;font-weight:700;font-family:'Space Mono',monospace;letter-spacing:0.5px}}
.badge{{background:rgba(245,158,11,0.12);color:var(--yellow);font-size:10px;padding:3px 10px;border-radius:20px;font-family:'Space Mono',monospace;border:1px solid rgba(245,158,11,0.2)}}
table{{width:100%;border-collapse:collapse}}
thead th{{padding:10px 16px;text-align:left;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;font-weight:500;border-bottom:1px solid var(--bdr);font-family:'Space Mono',monospace}}
.empty{{padding:48px;text-align:center;color:var(--muted)}}
.empty-emoji{{font-size:36px;margin-bottom:10px}}
@media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.charts{{grid-template-columns:1fr 1fr}}}}
@media(max-width:700px){{.cards{{grid-template-columns:1fr 1fr}}.charts{{grid-template-columns:1fr}}.main{{padding:14px}}.header{{padding:14px}}}}
</style>
</head>
<body>
<div class="header">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div class="logo-text">POWER<span>15</span></div>
  </div>
  <div style="display:flex;align-items:center;gap:14px">
    <div class="live-badge"><div class="live-dot"></div>LIVE</div>
    <div class="updated">{now.strftime('%d %b %Y %H:%M IST')}</div>
  </div>
</div>

<div class="main">
  <div class="cards">
    <div class="card blue">
      <div class="card-label">Available</div>
      <div class="card-value" style="color:var(--blue)">Rs.{capital['available']/1000:.1f}K</div>
      <div class="card-sub">of Rs.{capital['initial']/1000:.0f}K capital</div>
    </div>
    <div class="card {'green' if total_pnl>=0 else 'red'}">
      <div class="card-label">Total P&L</div>
      <div class="card-value" style="color:{'var(--green)' if total_pnl>=0 else 'var(--red)'}">Rs.{total_pnl:+,.0f}</div>
      <div class="card-sub">{total_return:+.2f}% return</div>
    </div>
    <div class="card yellow">
      <div class="card-label">Open Positions</div>
      <div class="card-value" style="color:var(--yellow)">{len(open_tr)}</div>
      <div class="card-sub">Rs.{capital['invested']/1000:.1f}K deployed</div>
    </div>
    <div class="card purple">
      <div class="card-label">Win Rate</div>
      <div class="card-value" style="color:var(--purple)">{win_rate:.0f}%</div>
      <div class="card-sub">{capital['winning_trades']}/{capital['total_trades']} trades</div>
    </div>
    <div class="card {'green' if total_unrealised>=0 else 'red'}">
      <div class="card-label">Unrealised P&L</div>
      <div class="card-value" style="color:{'var(--green)' if total_unrealised>=0 else 'var(--red)'}">Rs.{total_unrealised:+,.0f}</div>
      <div class="card-sub">{len(open_tr)} positions</div>
    </div>
  </div>

  <div class="capbar">
    <div class="capbar-top">
      <span style="font-family:'Space Mono',monospace;font-size:11px;font-weight:700">CAPITAL UTILISATION</span>
      <span style="font-family:'Space Mono',monospace;font-size:11px;color:var(--yellow)">{invested_pct:.1f}% DEPLOYED</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:{invested_pct:.1f}%"></div></div>
    <div class="bar-labels"><span>Rs.0</span><span>Invested: Rs.{capital['invested']:,.0f}</span><span>Rs.{capital['initial']:,.0f}</span></div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <div class="chart-title">Sector Allocation</div>
      {'<canvas id="pieChart"></canvas>' if sector_data else '<div class="empty"><div class="empty-emoji">🥧</div><div>No positions</div></div>'}
    </div>
    <div class="chart-card">
      <div class="chart-title">Stock P&L</div>
      {'<canvas id="barChart"></canvas>' if enriched else '<div class="empty"><div class="empty-emoji">📊</div><div>No open positions</div></div>'}
    </div>
    <div class="chart-card">
      <div class="chart-title">Cumulative P&L Curve</div>
      <canvas id="lineChart"></canvas>
    </div>
  </div>

  <div class="tcard">
    <div class="thead">
      <div class="ttitle">OPEN POSITIONS</div>
      <div class="badge">{len(open_tr)} ACTIVE</div>
    </div>
    {'<div class="empty"><div class="empty-emoji">🚀</div><div style="font-size:15px;margin-bottom:4px">No open positions yet</div><div style="font-size:13px;color:var(--muted)">Buy signals trigger at 3:30 PM weekdays</div></div>' if not enriched else f'<table><thead><tr><th>Symbol</th><th>Entry</th><th>CMP</th><th>Return</th><th>P&amp;L</th><th>Progress</th><th>Stop Loss</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>'}
  </div>

  {'<div class="tcard"><div class="thead"><div class="ttitle">CLOSED TRADES</div><div class="badge">LAST ' + str(min(10,len(closed))) + '</div></div><table><thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy</th><th>Sell</th><th>P&amp;L</th><th>Return</th><th>Reason</th></tr></thead><tbody>' + closed_rows + '</tbody></table></div>' if closed else ''}

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
Chart.defaults.color='#64748B';
Chart.defaults.borderColor='rgba(255,255,255,0.05)';
Chart.defaults.font.family="'DM Sans',sans-serif";

const SD={sector_js};
const PH={pnl_js};
const PS={pos_js};

if(SD.length&&document.getElementById('pieChart')){{
  new Chart(document.getElementById('pieChart'),{{
    type:'doughnut',
    data:{{labels:SD.map(d=>d.label),datasets:[{{data:SD.map(d=>d.value),backgroundColor:SD.map(d=>d.color),borderWidth:2,borderColor:'#0D1424',hoverOffset:6}}]}},
    options:{{cutout:'68%',responsive:true,plugins:{{legend:{{position:'bottom',labels:{{color:'#94A3B8',padding:10,font:{{size:10}}}}}},tooltip:{{callbacks:{{label:c=>` Rs.${{c.raw.toLocaleString('en-IN')}}`}}}}}}}}
  }});
}}

if(PS.length&&document.getElementById('barChart')){{
  new Chart(document.getElementById('barChart'),{{
    type:'bar',
    data:{{labels:PS.map(p=>p.symbol),datasets:[{{label:'P&L',data:PS.map(p=>p.pnl),backgroundColor:PS.map(p=>p.pnl>=0?'rgba(16,185,129,0.7)':'rgba(239,68,68,0.7)'),borderColor:PS.map(p=>p.pnl>=0?'#10B981':'#EF4444'),borderWidth:1,borderRadius:4}}]}},
    options:{{responsive:true,indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` Rs.${{c.raw.toLocaleString('en-IN')}}`}}}}}},scales:{{x:{{ticks:{{color:'#64748B'}}}},y:{{grid:{{display:false}},ticks:{{color:'#F1F5F9',font:{{weight:'600'}}}}}}}}}}
  }});
}}

const lc=document.getElementById('lineChart');
if(lc){{
  const isPos=PH[PH.length-1]>=0;
  new Chart(lc,{{
    type:'line',
    data:{{
      labels:PH.length>1?PH.map((_,i)=>`T${{i+1}}`):['{now.strftime("%d %b")}'],
      datasets:[{{label:'Cumulative P&L',data:PH.length>0?PH:[0],borderColor:isPos?'#10B981':'#EF4444',backgroundColor:isPos?'rgba(16,185,129,0.08)':'rgba(239,68,68,0.08)',fill:true,tension:0.4,pointRadius:3,pointHoverRadius:7,pointBackgroundColor:isPos?'#10B981':'#EF4444',borderWidth:2}}]
    }},
    options:{{responsive:true,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` Rs.${{c.raw.toLocaleString('en-IN')}}`}}}}}},scales:{{x:{{ticks:{{color:'#64748B',maxTicksLimit:8}}}},y:{{ticks:{{color:'#64748B',callback:v=>'Rs.'+v.toLocaleString('en-IN')}}}}}}}}
  }});
}}
</script>
</body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = build_dashboard().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)
    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Power 15 Cloud Dashboard running on port {port}\n")
    HTTPServer(("", port), Handler).serve_forever()