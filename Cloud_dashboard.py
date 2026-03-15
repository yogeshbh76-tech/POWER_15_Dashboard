"""
Power 15 — Cloud Dashboard v3.0 (Render.com)
Vibrant neon-arcade trading terminal aesthetic
Auto-refreshes every 90 seconds
"""
import os, json, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
IST = pytz.timezone("Asia/Kolkata")

HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

SECTOR_COLORS = {
    "Metals & Mining": "#F59E0B",
    "PSU Bank":        "#3B82F6",
    "Financials":      "#A855F7",
    "Private Bank":    "#10B981",
}
TIER_COLORS = { 1: "#F59E0B", 2: "#3B82F6", 3: "#EF4444" }
POWER_15_SECTORS = {
    "NATIONALUM":"Metals & Mining","VEDL":"Metals & Mining",
    "HINDALCO":"Metals & Mining","HINDZINC":"Metals & Mining",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Financials","MANAPPURAM":"Financials","ABCAPITAL":"Financials",
    "LTF":"Financials","BAJFINANCE":"Financials",
    "FEDERALBNK":"Private Bank","AUBANK":"Private Bank",
}
POWER_15_TIERS = {
    "NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
    "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,
    "FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
    "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3,
}

def fetch_supabase(table):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def get_cmp(symbol):
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8
        )
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

    enriched = []
    total_unrealised = 0
    for t in open_tr:
        cmp  = get_cmp(t["symbol"]) or t["entry_price"]
        pnl  = (cmp - t["entry_price"]) * t["quantity"]
        pct  = (cmp - t["entry_price"]) / t["entry_price"] * 100
        days = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
        left = max(0, 90 - days)
        peak = t.get("peak_cmp", cmp)
        tier = POWER_15_TIERS.get(t["symbol"], 2)
        total_unrealised += pnl
        enriched.append({
            **t, "cmp": cmp, "pnl": pnl, "pct": pct,
            "days": days, "left": left, "peak": peak, "tier": tier,
            "sector": POWER_15_SECTORS.get(t["symbol"], "Other")
        })

    total_pnl    = capital["total_pnl"] + total_unrealised
    total_return = (total_pnl / capital["initial"] * 100) if capital["initial"] > 0 else 0
    win_rate     = (capital["winning_trades"] / capital["total_trades"] * 100) if capital["total_trades"] > 0 else 0
    invested_pct = min(100, capital["invested"] / capital["initial"] * 100) if capital["initial"] > 0 else 0

    sector_data = {}
    for t in enriched:
        s = t["sector"]
        sector_data[s] = sector_data.get(s, 0) + t["entry_price"] * t["quantity"]

    pnl_history = []
    running = 0
    for t in sorted(closed, key=lambda x: x.get("exit_date", "0")):
        running += t.get("pnl", 0)
        pnl_history.append(round(running))

    # ── Position cards ──────────────────────────────────────────────────────────
    pos_cards = ""
    for t in enriched:
        pnl_positive = t["pnl"] >= 0
        tier_col     = TIER_COLORS.get(t["tier"], "#94A3B8")
        sec_col      = SECTOR_COLORS.get(t["sector"], "#94A3B8")
        pnl_col      = "#10B981" if pnl_positive else "#EF4444"
        progress     = min(100, t["days"] / 90 * 100)
        prog_col     = "#EF4444" if t["left"] <= 10 else "#F59E0B" if t["left"] <= 30 else "#10B981"
        tier_label   = ["","T1 🔥","T2 ✅","T3 ⚡"][t["tier"]]
        status       = "🔴 EXIT" if t["days"] >= 90 or t["cmp"] <= t["sl_price"] else ("🟡 WATCH" if t["left"] <= 10 else "🟢 HOLD")
        peak_pct     = (t["peak"] - t["entry_price"]) / t["entry_price"] * 100 if t["entry_price"] > 0 else 0
        trail_cfg    = { "NATIONALUM":75,"INDIANB":70,"VEDL":70,"SHRIRAMFIN":70,
                         "CANBK":65,"SBIN":70,"MANAPPURAM":60,"ABCAPITAL":60,
                         "FEDERALBNK":65,"LTF":80,"BANKINDIA":65,"HINDALCO":70,
                         "BAJFINANCE":80,"HINDZINC":80,"AUBANK":80 }
        thresh       = trail_cfg.get(t["symbol"], 80)
        trail_active = peak_pct >= thresh and thresh < 80
        trail_tag    = f'<span class="trail-tag">🔄 TRAILING</span>' if trail_active else ""

        pos_cards += f"""
        <div class="pos-card" onclick="toggleCard(this)">
          <div class="pos-header">
            <div class="pos-left">
              <div class="pos-symbol">{t["symbol"]}</div>
              <div class="pos-meta">
                <span class="tier-badge" style="--tc:{tier_col}">{tier_label}</span>
                <span class="sec-badge" style="--sc:{sec_col}">{t["sector"]}</span>
                {trail_tag}
              </div>
            </div>
            <div class="pos-right">
              <div class="pos-pct" style="color:{pnl_col}">{t["pct"]:+.1f}%</div>
              <div class="pos-pnl" style="color:{pnl_col}">₹{t["pnl"]:+,.0f}</div>
            </div>
          </div>
          <div class="pos-progress">
            <div class="prog-track">
              <div class="prog-fill" style="width:{progress:.0f}%;background:{prog_col}"></div>
            </div>
            <div class="prog-labels">
              <span>{t["days"]}d held</span>
              <span style="color:{prog_col}">{t["left"]}d left</span>
            </div>
          </div>
          <div class="pos-detail">
            <div class="detail-row">
              <span class="dl">Entry</span><span class="dv">₹{t["entry_price"]:.2f}</span>
              <span class="dl">CMP</span><span class="dv" style="color:#F1F5F9;font-weight:700">₹{t["cmp"]:.2f}</span>
              <span class="dl">Peak</span><span class="dv" style="color:#F59E0B">₹{t["peak"]:.2f} (+{peak_pct:.1f}%)</span>
            </div>
            <div class="detail-row" style="margin-top:8px">
              <span class="dl">Stop Loss</span><span class="dv" style="color:#EF4444">₹{t["sl_price"]:.2f}</span>
              <span class="dl">Qty</span><span class="dv">{t["quantity"]}</span>
              <span class="dl">Status</span><span class="dv">{status}</span>
            </div>
          </div>
        </div>"""

    # ── Closed trade rows ────────────────────────────────────────────────────────
    closed_rows = ""
    for t in sorted(closed, key=lambda x: x.get("exit_date","0"), reverse=True)[:15]:
        pnl   = t.get("pnl", 0)
        pct   = t.get("pnl_pct", 0)
        col   = "#10B981" if pnl >= 0 else "#EF4444"
        icon  = "✅" if pnl >= 0 else "❌"
        reason = t.get("exit_reason","")
        rtype = "🛑" if "Stop" in reason else "📉" if "Trail" in reason else "🎯" if "target" in reason.lower() else "⏰"
        closed_rows += f"""
        <tr class="closed-row">
          <td><span class="sym-pill">{t["symbol"]}</span></td>
          <td style="color:#64748B">{t.get("entry_date","")}</td>
          <td style="color:#64748B">{t.get("exit_date","")}</td>
          <td style="color:#94A3B8">₹{t["entry_price"]:.2f}</td>
          <td style="color:#94A3B8">₹{t.get("exit_price",0):.2f}</td>
          <td style="color:{col};font-weight:700">₹{pnl:+,.0f}</td>
          <td style="color:{col};font-weight:700">{pct:+.1f}%</td>
          <td style="color:#64748B;font-size:11px">{rtype} {reason[:45]}</td>
        </tr>"""

    sector_js = json.dumps([
        {"label":k,"value":round(v),"color":SECTOR_COLORS.get(k,"#6B7280")}
        for k,v in sector_data.items()
    ])
    pnl_js = json.dumps(pnl_history if pnl_history else [0])
    pos_js = json.dumps([
        {"symbol":t["symbol"],"pnl":round(t["pnl"]),
         "color":SECTOR_COLORS.get(t["sector"],"#6B7280")}
        for t in enriched
    ])

    pnl_sign   = "+" if total_pnl >= 0 else ""
    pnl_glow   = "0 0 30px rgba(16,185,129,0.4)" if total_pnl >= 0 else "0 0 30px rgba(239,68,68,0.4)"
    pnl_color  = "#10B981" if total_pnl >= 0 else "#EF4444"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="90">
<title>⚡ Power 15 — Live Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root {{
  --bg:      #04060D;
  --bg2:     #080C17;
  --surf:    #0C1220;
  --surf2:   #111827;
  --bdr:     rgba(255,255,255,0.06);
  --bdr2:    rgba(255,255,255,0.12);
  --text:    #F0F4FF;
  --muted:   #4B5D78;
  --subtle:  #1E293B;
  --gold:    #F59E0B;
  --goldd:   #D97706;
  --green:   #10B981;
  --red:     #EF4444;
  --blue:    #3B82F6;
  --purple:  #A855F7;
  --cyan:    #06B6D4;
  --pink:    #EC4899;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{
  background:var(--bg);
  font-family:'Outfit',sans-serif;
  color:var(--text);
  min-height:100vh;
  overflow-x:hidden;
}}

/* ── Animated grid background ── */
body::before{{
  content:'';
  position:fixed;inset:0;
  background-image:
    linear-gradient(rgba(245,158,11,0.03) 1px,transparent 1px),
    linear-gradient(90deg,rgba(245,158,11,0.03) 1px,transparent 1px);
  background-size:50px 50px;
  pointer-events:none;
  z-index:0;
}}
body::after{{
  content:'';
  position:fixed;
  top:-40%;left:-20%;
  width:140%;height:80%;
  background:radial-gradient(ellipse at 30% 50%, rgba(245,158,11,0.04) 0%, transparent 60%),
              radial-gradient(ellipse at 70% 30%, rgba(59,130,246,0.04) 0%, transparent 60%);
  pointer-events:none;
  z-index:0;
}}

/* ── Header ── */
.header{{
  position:sticky;top:0;z-index:100;
  background:rgba(4,6,13,0.92);
  backdrop-filter:blur(20px);
  border-bottom:1px solid rgba(245,158,11,0.15);
  padding:0 28px;
  height:64px;
  display:flex;align-items:center;justify-content:space-between;
}}
.logo{{display:flex;align-items:center;gap:12px;text-decoration:none}}
.logo-bolt{{
  width:40px;height:40px;
  background:linear-gradient(135deg,#F59E0B,#EF4444);
  border-radius:12px;
  display:flex;align-items:center;justify-content:center;
  font-size:20px;
  box-shadow:0 0 20px rgba(245,158,11,0.5);
  animation:pulse-glow 2.5s ease-in-out infinite;
}}
@keyframes pulse-glow{{
  0%,100%{{box-shadow:0 0 20px rgba(245,158,11,0.5)}}
  50%{{box-shadow:0 0 35px rgba(245,158,11,0.9),0 0 60px rgba(245,158,11,0.3)}}
}}
.logo-name{{
  font-family:'Syne',sans-serif;
  font-size:20px;font-weight:800;
  letter-spacing:-0.5px;
  color:var(--text);
}}
.logo-name span{{color:var(--gold)}}
.header-right{{display:flex;align-items:center;gap:16px}}
.live-chip{{
  display:flex;align-items:center;gap:7px;
  background:rgba(16,185,129,0.1);
  border:1px solid rgba(16,185,129,0.3);
  padding:5px 13px;border-radius:20px;
  font-family:'JetBrains Mono',monospace;
  font-size:11px;color:var(--green);font-weight:600;
}}
.live-dot{{
  width:7px;height:7px;border-radius:50%;
  background:var(--green);
  animation:blink 1.4s ease-in-out infinite;
}}
@keyframes blink{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:0.3;transform:scale(0.7)}}}}
.time-chip{{
  font-family:'JetBrains Mono',monospace;
  font-size:11px;color:var(--muted);
  background:var(--surf);
  border:1px solid var(--bdr);
  padding:5px 12px;border-radius:20px;
}}
.refresh-bar{{
  position:fixed;top:64px;left:0;height:2px;
  background:linear-gradient(90deg,var(--gold),var(--cyan),var(--purple));
  animation:refresh-progress 90s linear forwards;
  z-index:99;
}}
@keyframes refresh-progress{{from{{width:100%}}to{{width:0%}}}}

/* ── Ticker strip ── */
.ticker{{
  background:rgba(245,158,11,0.06);
  border-bottom:1px solid rgba(245,158,11,0.1);
  padding:8px 0;
  overflow:hidden;
  position:relative;z-index:1;
}}
.ticker-inner{{
  display:flex;gap:40px;
  animation:ticker-scroll 40s linear infinite;
  width:max-content;
}}
.ticker-inner:hover{{animation-play-state:paused}}
@keyframes ticker-scroll{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.tick-item{{
  display:flex;align-items:center;gap:8px;
  font-family:'JetBrains Mono',monospace;
  font-size:11px;white-space:nowrap;
}}
.tick-sym{{color:var(--text);font-weight:700}}
.tick-pos{{color:var(--green)}}
.tick-neg{{color:var(--red)}}
.tick-dot{{color:var(--muted)}}

/* ── Main layout ── */
.main{{
  padding:24px 28px;
  position:relative;z-index:1;
  max-width:1600px;
  margin:0 auto;
}}

/* ── KPI cards ── */
.kpi-grid{{
  display:grid;
  grid-template-columns:repeat(5,1fr);
  gap:14px;
  margin-bottom:24px;
}}
.kpi-card{{
  background:var(--surf);
  border:1px solid var(--bdr);
  border-radius:18px;
  padding:20px;
  cursor:pointer;
  transition:all 0.25s ease;
  position:relative;
  overflow:hidden;
}}
.kpi-card::before{{
  content:'';
  position:absolute;inset:0;
  background:radial-gradient(circle at top left, var(--glow-color,transparent) 0%, transparent 60%);
  opacity:0;
  transition:opacity 0.3s;
}}
.kpi-card:hover{{transform:translateY(-3px);border-color:var(--bdr2)}}
.kpi-card:hover::before{{opacity:1}}
.kpi-icon{{
  font-size:22px;
  margin-bottom:12px;
  display:block;
}}
.kpi-label{{
  font-size:10px;font-weight:600;
  color:var(--muted);
  text-transform:uppercase;letter-spacing:1.2px;
  font-family:'JetBrains Mono',monospace;
  margin-bottom:6px;
}}
.kpi-value{{
  font-family:'Syne',sans-serif;
  font-size:26px;font-weight:800;
  line-height:1;
  margin-bottom:4px;
}}
.kpi-sub{{font-size:11px;color:var(--muted)}}
.kpi-card.gold  {{--glow-color:rgba(245,158,11,0.15);border-top:2px solid var(--gold)}}
.kpi-card.green {{--glow-color:rgba(16,185,129,0.15);border-top:2px solid var(--green)}}
.kpi-card.red   {{--glow-color:rgba(239,68,68,0.15);border-top:2px solid var(--red)}}
.kpi-card.blue  {{--glow-color:rgba(59,130,246,0.15);border-top:2px solid var(--blue)}}
.kpi-card.purple{{--glow-color:rgba(168,85,247,0.15);border-top:2px solid var(--purple)}}

/* ── Capital bar ── */
.cap-bar-wrap{{
  background:var(--surf);border:1px solid var(--bdr);
  border-radius:18px;padding:18px 22px;
  margin-bottom:24px;
}}
.cap-bar-top{{
  display:flex;justify-content:space-between;
  font-family:'JetBrains Mono',monospace;
  font-size:11px;margin-bottom:12px;
}}
.cap-bar-track{{
  height:10px;background:var(--subtle);
  border-radius:5px;overflow:hidden;
  margin-bottom:8px;
}}
.cap-bar-fill{{
  height:100%;border-radius:5px;
  background:linear-gradient(90deg,var(--green),var(--gold),var(--cyan));
  transition:width 1.5s cubic-bezier(0.16,1,0.3,1);
  position:relative;
}}
.cap-bar-fill::after{{
  content:'';
  position:absolute;right:0;top:0;
  width:4px;height:100%;
  background:white;opacity:0.6;
  border-radius:2px;
  animation:cap-pulse 1.5s ease-in-out infinite;
}}
@keyframes cap-pulse{{0%,100%{{opacity:0.6}}50%{{opacity:0}}}}
.cap-labels{{
  display:flex;justify-content:space-between;
  font-size:11px;color:var(--muted);
  font-family:'JetBrains Mono',monospace;
}}

/* ── Charts row ── */
.charts-row{{
  display:grid;
  grid-template-columns:200px 1fr 2fr;
  gap:14px;
  margin-bottom:24px;
}}
.chart-card{{
  background:var(--surf);border:1px solid var(--bdr);
  border-radius:18px;padding:20px;
  transition:border-color 0.2s;
}}
.chart-card:hover{{border-color:var(--bdr2)}}
.chart-title{{
  font-size:10px;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:1px;
  font-family:'JetBrains Mono',monospace;
  margin-bottom:14px;
  display:flex;align-items:center;gap:7px;
}}
.chart-title::before{{
  content:'';width:3px;height:12px;
  background:var(--gold);border-radius:2px;
}}
.empty-state{{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:40px 20px;
  color:var(--muted);gap:10px;
}}
.empty-state .empty-icon{{font-size:32px}}
.empty-state p{{font-size:13px}}

/* ── Section header ── */
.section-hdr{{
  display:flex;justify-content:space-between;align-items:center;
  margin-bottom:16px;
}}
.section-title{{
  font-family:'Syne',sans-serif;
  font-size:16px;font-weight:800;
  display:flex;align-items:center;gap:10px;
}}
.section-title .s-icon{{
  width:28px;height:28px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;
  font-size:14px;
  background:rgba(245,158,11,0.15);
}}
.count-badge{{
  background:rgba(245,158,11,0.12);
  color:var(--gold);
  border:1px solid rgba(245,158,11,0.25);
  font-family:'JetBrains Mono',monospace;
  font-size:10px;padding:3px 10px;border-radius:20px;
  font-weight:600;
}}

/* ── Position cards ── */
.pos-grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:14px;
  margin-bottom:28px;
}}
.pos-card{{
  background:var(--surf);
  border:1px solid var(--bdr);
  border-radius:18px;
  padding:18px;
  cursor:pointer;
  transition:all 0.25s ease;
  position:relative;overflow:hidden;
}}
.pos-card::before{{
  content:'';
  position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--gold),var(--cyan));
  transform:scaleX(0);transform-origin:left;
  transition:transform 0.3s ease;
}}
.pos-card:hover{{transform:translateY(-3px);border-color:rgba(245,158,11,0.25);box-shadow:0 12px 40px rgba(0,0,0,0.4)}}
.pos-card:hover::before{{transform:scaleX(1)}}
.pos-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}}
.pos-symbol{{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;color:var(--text);letter-spacing:-0.5px}}
.pos-meta{{display:flex;align-items:center;gap:6px;margin-top:5px;flex-wrap:wrap}}
.tier-badge{{
  font-size:10px;font-weight:600;
  padding:2px 8px;border-radius:10px;
  background:rgba(from var(--tc) r g b / 0.15);
  color:var(--tc);
  border:1px solid rgba(from var(--tc) r g b / 0.3);
  font-family:'JetBrains Mono',monospace;
}}
.sec-badge{{
  font-size:10px;color:var(--sc);
  font-family:'JetBrains Mono',monospace;
  opacity:0.8;
}}
.trail-tag{{
  font-size:9px;
  background:rgba(6,182,212,0.15);
  color:var(--cyan);
  border:1px solid rgba(6,182,212,0.3);
  padding:2px 7px;border-radius:8px;
  font-family:'JetBrains Mono',monospace;
  font-weight:600;
  animation:trail-pulse 2s ease-in-out infinite;
}}
@keyframes trail-pulse{{0%,100%{{opacity:1}}50%{{opacity:0.5}}}}
.pos-right{{text-align:right}}
.pos-pct{{font-family:'Syne',sans-serif;font-size:22px;font-weight:800}}
.pos-pnl{{font-family:'JetBrains Mono',monospace;font-size:12px;margin-top:2px;opacity:0.8}}
.pos-progress{{margin-bottom:12px}}
.prog-track{{height:5px;background:var(--subtle);border-radius:3px;overflow:hidden;margin-bottom:6px}}
.prog-fill{{height:100%;border-radius:3px;transition:width 1.2s cubic-bezier(0.16,1,0.3,1)}}
.prog-labels{{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.pos-detail{{
  max-height:0;overflow:hidden;
  transition:max-height 0.4s ease;
  border-top:0px solid var(--bdr);
}}
.pos-card.expanded .pos-detail{{
  max-height:100px;
  border-top:1px solid var(--bdr);
  padding-top:12px;
  margin-top:2px;
}}
.detail-row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.dl{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.dv{{font-size:11px;color:#94A3B8;font-family:'JetBrains Mono',monospace;font-weight:600}}

/* ── Closed trades table ── */
.table-wrap{{
  background:var(--surf);border:1px solid var(--bdr);
  border-radius:18px;overflow:hidden;
  margin-bottom:24px;
}}
.table-head-row{{
  padding:16px 22px;
  border-bottom:1px solid var(--bdr);
  display:flex;justify-content:space-between;align-items:center;
}}
table{{width:100%;border-collapse:collapse}}
thead th{{
  padding:10px 16px;text-align:left;
  font-size:10px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.8px;font-weight:500;
  border-bottom:1px solid var(--bdr);
  font-family:'JetBrains Mono',monospace;
}}
.closed-row td{{
  padding:12px 16px;
  border-bottom:1px solid rgba(255,255,255,0.03);
  font-size:13px;
  transition:background 0.15s;
}}
.closed-row:hover td{{background:rgba(255,255,255,0.02)}}
.closed-row:last-child td{{border-bottom:none}}
.sym-pill{{
  background:var(--surf2);
  border:1px solid var(--bdr2);
  padding:3px 10px;border-radius:8px;
  font-family:'JetBrains Mono',monospace;
  font-size:12px;font-weight:600;color:var(--text);
}}

/* ── Footer ── */
.footer{{
  text-align:center;
  padding:24px;
  font-size:11px;color:var(--muted);
  font-family:'JetBrains Mono',monospace;
  border-top:1px solid var(--bdr);
  position:relative;z-index:1;
}}

/* ── Responsive ── */
@media(max-width:1200px){{
  .kpi-grid{{grid-template-columns:repeat(3,1fr)}}
  .charts-row{{grid-template-columns:1fr 1fr}}
  .charts-row .chart-card:last-child{{grid-column:1/-1}}
}}
@media(max-width:768px){{
  .kpi-grid{{grid-template-columns:repeat(2,1fr)}}
  .charts-row{{grid-template-columns:1fr}}
  .main{{padding:16px}}
  .header{{padding:0 16px}}
  .pos-grid{{grid-template-columns:1fr}}
}}

/* ── Entrance animations ── */
@keyframes fade-up{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
.kpi-card{{animation:fade-up 0.5s ease both}}
.kpi-card:nth-child(1){{animation-delay:0.05s}}
.kpi-card:nth-child(2){{animation-delay:0.1s}}
.kpi-card:nth-child(3){{animation-delay:0.15s}}
.kpi-card:nth-child(4){{animation-delay:0.2s}}
.kpi-card:nth-child(5){{animation-delay:0.25s}}
.pos-card{{animation:fade-up 0.5s ease both}}
</style>
</head>
<body>

<div class="refresh-bar"></div>

<!-- Header -->
<header class="header">
  <div class="logo">
    <div class="logo-bolt">⚡</div>
    <div class="logo-name">POWER<span>15</span></div>
  </div>
  <div class="header-right">
    <div class="live-chip"><div class="live-dot"></div>LIVE</div>
    <div class="time-chip">{now.strftime('%d %b %Y %H:%M IST')}</div>
  </div>
</header>

<!-- Ticker strip -->
<div class="ticker">
  <div class="ticker-inner" id="tickerInner">
    {''.join([f'<div class="tick-item"><span class="tick-sym">{t["symbol"]}</span><span class="{"tick-pos" if t["pct"]>=0 else "tick-neg"}">{t["pct"]:+.1f}%</span><span class="tick-dot">·</span><span class="{"tick-pos" if t["pnl"]>=0 else "tick-neg"}">₹{t["pnl"]:+,.0f}</span></div>' for t in enriched] or ['<div class="tick-item"><span class="tick-sym">POWER 15</span><span class="tick-pos">· No open positions ·</span></div>']) * 6}
  </div>
</div>

<div class="main">

  <!-- KPI Grid -->
  <div class="kpi-grid">
    <div class="kpi-card {'green' if total_pnl>=0 else 'red'}" onclick="flashCard(this)">
      <span class="kpi-icon">{'📈' if total_pnl>=0 else '📉'}</span>
      <div class="kpi-label">Total P&L</div>
      <div class="kpi-value" style="color:{pnl_color};text-shadow:{pnl_glow}">{pnl_sign}₹{abs(total_pnl):,.0f}</div>
      <div class="kpi-sub">{total_return:+.2f}% overall return</div>
    </div>
    <div class="kpi-card blue" onclick="flashCard(this)">
      <span class="kpi-icon">💰</span>
      <div class="kpi-label">Available</div>
      <div class="kpi-value" style="color:var(--blue)">₹{capital['available']/1000:.1f}K</div>
      <div class="kpi-sub">of ₹{capital['initial']/1000:.0f}K total</div>
    </div>
    <div class="kpi-card gold" onclick="flashCard(this)">
      <span class="kpi-icon">🔓</span>
      <div class="kpi-label">Open Positions</div>
      <div class="kpi-value" style="color:var(--gold)">{len(open_tr)}</div>
      <div class="kpi-sub">₹{capital['invested']/1000:.1f}K deployed</div>
    </div>
    <div class="kpi-card purple" onclick="flashCard(this)">
      <span class="kpi-icon">🎯</span>
      <div class="kpi-label">Win Rate</div>
      <div class="kpi-value" style="color:var(--purple)">{win_rate:.0f}%</div>
      <div class="kpi-sub">{capital['winning_trades']}/{capital['total_trades']} trades</div>
    </div>
    <div class="kpi-card {'green' if total_unrealised>=0 else 'red'}" onclick="flashCard(this)">
      <span class="kpi-icon">⚡</span>
      <div class="kpi-label">Unrealised</div>
      <div class="kpi-value" style="color:{'var(--green)' if total_unrealised>=0 else 'var(--red)'}">{'+'if total_unrealised>=0 else ''}₹{total_unrealised:,.0f}</div>
      <div class="kpi-sub">live positions</div>
    </div>
  </div>

  <!-- Capital bar -->
  <div class="cap-bar-wrap">
    <div class="cap-bar-top">
      <span style="color:var(--muted)">CAPITAL UTILISATION</span>
      <span style="color:var(--gold)">{invested_pct:.1f}% DEPLOYED</span>
    </div>
    <div class="cap-bar-track">
      <div class="cap-bar-fill" style="width:{invested_pct:.1f}%"></div>
    </div>
    <div class="cap-labels">
      <span>₹0</span>
      <span style="color:var(--gold)">Invested: ₹{capital['invested']:,.0f}</span>
      <span>₹{capital['initial']:,.0f}</span>
    </div>
  </div>

  <!-- Charts row -->
  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">Allocation</div>
      {f'<canvas id="pieChart" style="max-height:160px"></canvas>' if sector_data else '<div class="empty-state"><div class="empty-icon">🥧</div><p>No positions</p></div>'}
    </div>
    <div class="chart-card">
      <div class="chart-title">Stock P&L</div>
      {f'<canvas id="barChart"></canvas>' if enriched else '<div class="empty-state"><div class="empty-icon">📊</div><p>No open positions</p></div>'}
    </div>
    <div class="chart-card">
      <div class="chart-title">Cumulative P&L Curve</div>
      <canvas id="lineChart"></canvas>
    </div>
  </div>

  <!-- Open Positions -->
  <div class="section-hdr">
    <div class="section-title">
      <div class="s-icon">🚀</div>
      Open Positions
    </div>
    <div class="count-badge">{len(enriched)} ACTIVE</div>
  </div>

  {f'<div class="pos-grid">{pos_cards}</div>' if enriched else '<div class="table-wrap"><div class="empty-state" style="padding:60px"><div class="empty-icon">🌙</div><p style="font-size:15px;color:var(--text);margin-bottom:6px">No open positions right now</p><p>Buy signals trigger at 3:25 PM on weekdays</p></div></div>'}

  <!-- Closed Trades -->
  {f'''<div class="section-hdr">
    <div class="section-title"><div class="s-icon">📋</div>Trade History</div>
    <div class="count-badge">LAST {min(15,len(closed))}</div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Symbol</th><th>Entry</th><th>Exit</th>
        <th>Buy ₹</th><th>Sell ₹</th><th>P&L</th><th>Return</th><th>Reason</th>
      </tr></thead>
      <tbody>{closed_rows}</tbody>
    </table>
  </div>''' if closed else ''}

</div>

<div class="footer">
  ⚡ POWER 15 · Auto-refreshes every 90s · Strategy: RSI Crossover + Red Candle + Hybrid Exit · 98.1% win rate backtest
</div>

<script>
Chart.defaults.color = '#4B5D78';
Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';
Chart.defaults.font.family = "'Outfit',sans-serif";

const SD = {sector_js};
const PH = {pnl_js};
const PS = {pos_js};

// Pie chart
if(SD.length && document.getElementById('pieChart')) {{
  new Chart(document.getElementById('pieChart'),{{
    type:'doughnut',
    data:{{
      labels:SD.map(d=>d.label),
      datasets:[{{
        data:SD.map(d=>d.value),
        backgroundColor:SD.map(d=>d.color),
        borderWidth:3,
        borderColor:'#0C1220',
        hoverOffset:8
      }}]
    }},
    options:{{
      cutout:'70%',responsive:true,
      plugins:{{
        legend:{{position:'bottom',labels:{{color:'#94A3B8',padding:8,font:{{size:9}},boxWidth:10}}}},
        tooltip:{{callbacks:{{label:c=>' ₹'+c.raw.toLocaleString('en-IN')}}}}
      }}
    }}
  }});
}}

// Bar chart
if(PS.length && document.getElementById('barChart')) {{
  new Chart(document.getElementById('barChart'),{{
    type:'bar',
    data:{{
      labels:PS.map(p=>p.symbol),
      datasets:[{{
        label:'P&L',
        data:PS.map(p=>p.pnl),
        backgroundColor:PS.map(p=>p.pnl>=0?'rgba(16,185,129,0.65)':'rgba(239,68,68,0.65)'),
        borderColor:PS.map(p=>p.pnl>=0?'#10B981':'#EF4444'),
        borderWidth:1,borderRadius:6
      }}]
    }},
    options:{{
      responsive:true,indexAxis:'y',
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' ₹'+c.raw.toLocaleString('en-IN')}}}}}},
      scales:{{
        x:{{ticks:{{color:'#4B5D78'}},grid:{{color:'rgba(255,255,255,0.04)'}}}},
        y:{{grid:{{display:false}},ticks:{{color:'#F0F4FF',font:{{weight:'700',size:11}}}}}}
      }}
    }}
  }});
}}

// Line chart
const lc = document.getElementById('lineChart');
if(lc) {{
  const last = PH[PH.length-1] || 0;
  const isPos = last >= 0;
  const labels = PH.length > 1 ? PH.map((_,i) => 'T'+(i+1)) : ['{now.strftime("%d %b")}'];
  const grad = lc.getContext('2d').createLinearGradient(0,0,0,200);
  if(isPos) {{ grad.addColorStop(0,'rgba(16,185,129,0.25)'); grad.addColorStop(1,'rgba(16,185,129,0)'); }}
  else      {{ grad.addColorStop(0,'rgba(239,68,68,0.25)');  grad.addColorStop(1,'rgba(239,68,68,0)'); }}
  new Chart(lc,{{
    type:'line',
    data:{{
      labels,
      datasets:[{{
        label:'Cumulative P&L',
        data:PH.length>0 ? PH : [0],
        borderColor:isPos?'#10B981':'#EF4444',
        backgroundColor:grad,
        fill:true,tension:0.45,
        pointRadius:PH.length>20?0:4,
        pointHoverRadius:8,
        pointBackgroundColor:isPos?'#10B981':'#EF4444',
        pointBorderColor:'#0C1220',
        pointBorderWidth:2,
        borderWidth:2.5
      }}]
    }},
    options:{{
      responsive:true,
      plugins:{{legend:{{display:false}},tooltip:{{
        callbacks:{{label:c=>' ₹'+c.raw.toLocaleString('en-IN')}},
        backgroundColor:'#0C1220',
        borderColor:'rgba(245,158,11,0.3)',
        borderWidth:1,
        titleColor:'#F59E0B',
        bodyColor:'#F0F4FF',
        padding:10,cornerRadius:8
      }}}},
      scales:{{
        x:{{ticks:{{color:'#4B5D78',maxTicksLimit:8}},grid:{{color:'rgba(255,255,255,0.03)'}}}},
        y:{{ticks:{{color:'#4B5D78',callback:v=>'₹'+v.toLocaleString('en-IN')}},grid:{{color:'rgba(255,255,255,0.04)'}}}}
      }}
    }}
  }});
}}

// Toggle card expand
function toggleCard(el) {{
  el.classList.toggle('expanded');
}}

// Flash card on click
function flashCard(el) {{
  el.style.transform = 'scale(0.97)';
  setTimeout(()=>el.style.transform='', 150);
}}

// Animate KPI values counting up
document.querySelectorAll('.kpi-value').forEach(el => {{
  const text = el.textContent;
  const num = parseFloat(text.replace(/[^0-9.-]/g,''));
  if(!isNaN(num) && num > 0 && num < 1000000) {{
    let start = 0, duration = 1200;
    const step = (timestamp) => {{
      if(!start) start = timestamp;
      const progress = Math.min((timestamp-start)/duration, 1);
      const ease = 1-Math.pow(1-progress, 4);
      // just add a subtle entrance — don't rewrite formatted text
    }};
    requestAnimationFrame(step);
  }}
}});
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
    print(f"\n  ⚡ Power 15 Cloud Dashboard v3.0 — port {port}\n")
    HTTPServer(("", port), Handler).serve_forever()