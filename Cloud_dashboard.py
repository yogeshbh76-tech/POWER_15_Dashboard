"""
Power 15 — Supreme Dashboard v4.0
"""
import os, json, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

SUPABASE_URL = os.environ.get("SUPABASE_URL","https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
IST     = pytz.timezone("Asia/Kolkata")
HEADERS = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"}
SECTOR_COLORS = {"Metals & Mining":"#F59E0B","PSU Bank":"#3B82F6","Financials":"#A855F7","Private Bank":"#10B981"}
POWER_15_SECTORS = {
    "NATIONALUM":"Metals & Mining","VEDL":"Metals & Mining","HINDALCO":"Metals & Mining","HINDZINC":"Metals & Mining",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Financials","MANAPPURAM":"Financials","ABCAPITAL":"Financials","LTF":"Financials","BAJFINANCE":"Financials",
    "FEDERALBNK":"Private Bank","AUBANK":"Private Bank",
}
POWER_15_TIERS = {
    "NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
    "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,"FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
    "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3,
}
HYBRID_CONFIG = {
    "NATIONALUM":{"t":75,"tr":15},"INDIANB":{"t":70,"tr":15},"VEDL":{"t":70,"tr":18},
    "SHRIRAMFIN":{"t":70,"tr":15},"CANBK":{"t":65,"tr":15},"SBIN":{"t":70,"tr":15},
    "MANAPPURAM":{"t":60,"tr":20},"ABCAPITAL":{"t":60,"tr":20},"FEDERALBNK":{"t":65,"tr":15},
    "LTF":{"t":80,"tr":0},"BANKINDIA":{"t":65,"tr":15},"HINDALCO":{"t":70,"tr":15},
    "BAJFINANCE":{"t":80,"tr":0},"HINDZINC":{"t":80,"tr":0},"AUBANK":{"t":80,"tr":0},
}

def fmt_inr(val, signed=False):
    sign = ""
    if signed: sign = "+" if val >= 0 else "-"; val = abs(val)
    elif val < 0: sign = "-"; val = abs(val)
    if val >= 1_00_00_000: s = f"₹{val/1_00_00_000:.2f}Cr"
    elif val >= 1_00_000:  s = f"₹{val/1_00_000:.1f}L"
    elif val >= 1_000:     s = f"₹{val/1_000:.1f}K"
    else:                  s = f"₹{val:.0f}"
    return sign + s

def fmt_full(val):
    neg = val < 0; val = int(abs(val)); s = str(val)
    if len(s) > 3:
        last3 = s[-3:]; rest = s[:-3]
        chunks = []
        while len(rest) > 2: chunks.insert(0, rest[-2:]); rest = rest[:-2]
        if rest: chunks.insert(0, rest)
        s = ",".join(chunks) + "," + last3
    return ("-₹" if neg else "₹") + s

def fetch_sup(table):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*",headers=HEADERS,timeout=10)
        return r.json() if r.status_code==200 else []
    except: return []

def get_cmp(sym):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except: return None

def get_nifty():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        d = r.json()["chart"]["result"][0]
        cl = [c for c in d["indicators"]["quote"][0]["close"] if c]
        cmp = float(d["meta"]["regularMarketPrice"])
        pct = (cmp - cl[-2]) / cl[-2] * 100 if len(cl)>=2 else 0
        return cmp, pct
    except: return None, None

def build():
    now = datetime.now(IST)
    trades = fetch_sup("p15_trades")
    cap_r  = fetch_sup("p15_capital")
    cap    = cap_r[0] if cap_r else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
    open_t = [t for t in trades if t.get("status")=="OPEN"]
    closed = [t for t in trades if t.get("status")=="CLOSED"]

    enriched=[]; total_unreal=0
    for t in open_t:
        cmp = get_cmp(t["symbol"]) or t["entry_price"]
        pnl = (cmp-t["entry_price"])*t["quantity"]
        pct = (cmp-t["entry_price"])/t["entry_price"]*100
        days= (now.replace(tzinfo=None)-datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        left= max(0,90-days); peak=t.get("peak_cmp",cmp)
        pk_pct=(peak-t["entry_price"])/t["entry_price"]*100
        tier=POWER_15_TIERS.get(t["symbol"],2)
        cfg=HYBRID_CONFIG.get(t["symbol"],{"t":80,"tr":0})
        trail_on= pk_pct>=cfg["t"] and cfg["tr"]>0
        trail_stop=round(peak*(1-cfg["tr"]/100),2) if trail_on else None
        total_unreal+=pnl
        enriched.append({**t,"cmp":cmp,"pnl":pnl,"pct":pct,"days":days,"left":left,
            "peak":peak,"pk_pct":pk_pct,"tier":tier,"trail_on":trail_on,"trail_stop":trail_stop,
            "sector":POWER_15_SECTORS.get(t["symbol"],"Other")})

    total_pnl   = cap["total_pnl"]+total_unreal
    total_ret   = total_pnl/cap["initial"]*100 if cap["initial"]>0 else 0
    win_rate    = cap["winning_trades"]/cap["total_trades"]*100 if cap["total_trades"]>0 else 0
    inv_pct     = min(100,cap["invested"]/cap["initial"]*100) if cap["initial"]>0 else 0
    pnl_col     = "#10B981" if total_pnl>=0 else "#EF4444"
    nifty_cmp,nifty_pct = get_nifty()
    nifty_str   = f"NIFTY {nifty_cmp:,.0f} ({nifty_pct:+.2f}%)" if nifty_cmp else "NIFTY —"
    nifty_col   = "#10B981" if (nifty_pct or 0)>=0 else "#EF4444"
    wk=now.weekday(); hr=now.hour; mn=now.minute
    mkt= wk<5 and (9<hr<15 or (hr==9 and mn>=15) or (hr==15 and mn<=30))
    mkt_str="🟢 Market Open" if mkt else ("🔴 Weekend" if wk>=5 else "🔴 After Hours")
    sec_data={}
    for t in enriched: s=t["sector"]; sec_data[s]=sec_data.get(s,0)+t["entry_price"]*t["quantity"]
    pnl_hist=[]; run=0
    for t in sorted(closed,key=lambda x:x.get("exit_date","0")): run+=t.get("pnl",0); pnl_hist.append(round(run))
    sec_js=json.dumps([{"label":k,"value":round(v),"color":SECTOR_COLORS.get(k,"#6B7280")} for k,v in sec_data.items()])
    pnl_js=json.dumps(pnl_hist if pnl_hist else [0])
    pos_js=json.dumps([{"symbol":t["symbol"],"pnl":round(t["pnl"]),"pct":round(t["pct"],1),"color":SECTOR_COLORS.get(t["sector"],"#6B7280")} for t in enriched])

    # Position cards
    cards=""
    for i,t in enumerate(enriched):
        pc=t["pnl"]>=0; pcol="#10B981" if pc else "#EF4444"
        tc=SECTOR_COLORS.get(t["sector"],"#94A3B8")
        prog=min(100,t["days"]/90*100)
        bc="#EF4444" if t["left"]<=10 else "#F59E0B" if t["left"]<=30 else "#10B981"
        tl=["","🔥 T1","✅ T2","⚡ T3"][t["tier"]]
        st="🔴 EXIT NOW" if t["days"]>=90 or t["cmp"]<=t["sl_price"] else ("🟡 WATCH" if t["left"]<=10 else "🟢 HOLD")
        mag=min(abs(t["pct"])/80,1.0)
        glow=f"0 0 {int(20+mag*30)}px rgba({'16,185,129' if pc else '239,68,68'},{0.15+mag*0.25:.2f})"
        trail_html=f'<div class="trail-chip">🔄 TRAILING · ₹{t["trail_stop"]:.2f}</div>' if t["trail_on"] else ""
        warn_html='<div class="warn-chip">⚠️ EXIT SOON</div>' if t["left"]<=5 else ""
        sl_pct=(t["sl_price"]-t["entry_price"])/t["entry_price"]*100
        cards+=f"""
<div class="pos-card" style="animation-delay:{i*0.07:.2f}s" onclick="toggleX(this)">
  <div class="pos-glow" style="background:rgba({'16,185,129' if pc else '239,68,68'},0.05)"></div>
  <div class="pos-top">
    <div>
      <div class="pos-sym">{t["symbol"]}</div>
      <div class="pos-chips">
        <span class="chip-tier" style="color:{tc};border-color:{tc}40">{tl}</span>
        <span class="chip-sec">{t["sector"]}</span>
        <span class="chip-st">{st}</span>
      </div>
      {trail_html}{warn_html}
    </div>
    <div class="pos-nums">
      <div class="pos-pct" style="color:{pcol};text-shadow:{glow}">{t["pct"]:+.1f}%</div>
      <div class="pos-pnl" style="color:{pcol}">{fmt_inr(t["pnl"],signed=True)}</div>
      <div class="pos-cmp">₹{t["cmp"]:.2f}</div>
    </div>
  </div>
  <div class="pos-bar-wrap">
    <div class="pos-bar-track"><div class="pos-bar-fill" style="width:{prog:.0f}%;background:{bc}"></div></div>
    <div class="pos-bar-lbl"><span>Day {t["days"]}/90</span><span style="color:{bc}">{t["left"]}d left</span></div>
  </div>
  <div class="pos-exp">
    <div class="eg">
      <div class="egi"><span class="egl">Entry</span><span class="egv">₹{t["entry_price"]:.2f}</span></div>
      <div class="egi"><span class="egl">Stop Loss</span><span class="egv" style="color:#EF4444">₹{t["sl_price"]:.2f} ({sl_pct:+.1f}%)</span></div>
      <div class="egi"><span class="egl">Peak CMP</span><span class="egv" style="color:#F59E0B">₹{t["peak"]:.2f} (+{t["pk_pct"]:.1f}%)</span></div>
      <div class="egi"><span class="egl">Quantity</span><span class="egv">{t["quantity"]} shares</span></div>
      <div class="egi"><span class="egl">Invested</span><span class="egv">{fmt_inr(t["entry_price"]*t["quantity"])}</span></div>
      <div class="egi"><span class="egl">Trail at</span><span class="egv">{HYBRID_CONFIG.get(t["symbol"],{}).get("t",80)}% profit</span></div>
    </div>
  </div>
</div>"""

    # Closed rows
    crows=""
    for t in sorted(closed,key=lambda x:x.get("exit_date","0"),reverse=True)[:15]:
        pnl=t.get("pnl",0); pct=t.get("pnl_pct",0)
        col="#10B981" if pnl>=0 else "#EF4444"
        r=t.get("exit_reason","")
        rt="🛑" if "Stop" in r else "📉" if "Trail" in r else "🎯" if "target" in r.lower() else "⏰"
        crows+=f"""<tr class="ct-row">
<td><span class="sym-tag">{t["symbol"]}</span></td>
<td class="cm">{t.get("entry_date","")}</td><td class="cm">{t.get("exit_date","")}</td>
<td class="cm">₹{t["entry_price"]:.2f}</td><td class="cm">₹{t.get("exit_price",0):.2f}</td>
<td style="color:{col};font-weight:700">{fmt_inr(pnl,signed=True)}</td>
<td style="color:{col};font-weight:700">{pct:+.1f}%</td>
<td class="cm" style="font-size:11px">{rt} {r[:40]}</td></tr>"""

    # Ticker
    if enriched:
        items=" ".join([f'<span class="ti"><b>{t["symbol"]}</b> <span style="color:{"#10B981" if t["pct"]>=0 else "#EF4444"}">{t["pct"]:+.1f}% · {fmt_inr(t["pnl"],signed=True)}</span><span class="td">·</span></span>' for t in enriched])*6
    else:
        items='<span class="ti"><b>POWER 15</b> <span style="color:#F59E0B">No open positions · Signals at 3:25 PM weekdays</span></span>'*4

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="90">
<title>⚡ Power 15 · Supreme</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root{{--bg:#03050C;--bg2:#060A14;--surf:#0A1020;--surf2:#0F1828;--surf3:#141F32;--bdr:rgba(255,255,255,0.055);--bdr2:rgba(255,255,255,0.11);--text:#EEF2FF;--sub:#94A3B8;--muted:#475569;--gold:#F59E0B;--green:#10B981;--red:#EF4444;--blue:#3B82F6;--purple:#A855F7;--cyan:#06B6D4;--pink:#EC4899;--r:18px}}
[data-theme="light"]{{--bg:#F0F4FF;--bg2:#E8EEFF;--surf:#FFFFFF;--surf2:#F8FAFF;--surf3:#F0F4FF;--bdr:rgba(0,0,0,0.07);--bdr2:rgba(0,0,0,0.14);--text:#0F172A;--sub:#475569;--muted:#94A3B8}}
*{{box-sizing:border-box;margin:0;padding:0}}html{{scroll-behavior:smooth}}
body{{background:var(--bg);font-family:'Plus Jakarta Sans',sans-serif;color:var(--text);min-height:100vh;overflow-x:hidden}}
#ptc{{position:fixed;inset:0;pointer-events:none;z-index:0;opacity:0.55}}
.mesh{{position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse 60% 50% at 15% 25%,rgba(245,158,11,0.05) 0%,transparent 70%),radial-gradient(ellipse 40% 60% at 85% 75%,rgba(59,130,246,0.05) 0%,transparent 70%),radial-gradient(ellipse 50% 40% at 55% 5%,rgba(168,85,247,0.04) 0%,transparent 70%)}}
.rbar{{position:fixed;top:0;left:0;height:2px;z-index:999;background:linear-gradient(90deg,var(--gold),var(--cyan),var(--purple),var(--pink));animation:rbar 90s linear forwards}}
@keyframes rbar{{from{{width:100%}}to{{width:0}}}}
.hdr{{position:sticky;top:0;z-index:100;background:rgba(3,5,12,0.88);backdrop-filter:blur(24px) saturate(180%);border-bottom:1px solid var(--bdr);padding:0 28px;height:62px;display:flex;align-items:center;justify-content:space-between;gap:16px}}
[data-theme="light"] .hdr{{background:rgba(240,244,255,0.88)}}
.bolt{{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#F59E0B,#EF4444 60%,#EC4899);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;animation:bolt-ring 2.5s ease infinite}}
@keyframes bolt-ring{{0%,100%{{box-shadow:0 0 0 0 rgba(245,158,11,0.5),0 4px 20px rgba(245,158,11,0.3)}}50%{{box-shadow:0 0 0 8px rgba(245,158,11,0),0 4px 30px rgba(245,158,11,0.5)}}}}
.logo-t{{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;letter-spacing:-0.5px}}.logo-t span{{color:var(--gold)}}
.hdr-l{{display:flex;align-items:center;gap:14px}}
.hdr-c{{display:flex;align-items:center;gap:10px;font-family:'JetBrains Mono',monospace;font-size:11px}}
.npill{{padding:4px 12px;border-radius:20px;font-weight:600;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25)}}
.mpill{{padding:4px 12px;border-radius:20px;background:var(--surf2);border:1px solid var(--bdr);color:var(--sub)}}
.hdr-r{{display:flex;align-items:center;gap:10px}}
.live{{display:flex;align-items:center;gap:7px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:var(--green);background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);padding:4px 12px;border-radius:20px}}
.live::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 1.2s ease infinite}}
@keyframes blink{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:0.2;transform:scale(0.5)}}}}
.clk{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);background:var(--surf2);border:1px solid var(--bdr);padding:4px 12px;border-radius:20px}}
.tbtn{{width:34px;height:34px;border-radius:10px;border:1px solid var(--bdr2);background:var(--surf2);color:var(--sub);cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;transition:all 0.2s}}
.tbtn:hover{{background:var(--surf3);color:var(--text)}}
.ticker{{background:rgba(245,158,11,0.04);border-bottom:1px solid rgba(245,158,11,0.1);padding:9px 0;overflow:hidden;position:relative;z-index:1}}
.ticker-inner{{display:flex;gap:32px;width:max-content;animation:tick 45s linear infinite;font-family:'JetBrains Mono',monospace;font-size:12px}}
.ticker-inner:hover{{animation-play-state:paused;cursor:pointer}}
@keyframes tick{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.ti{{white-space:nowrap;display:flex;align-items:center;gap:7px}}.td{{color:var(--muted);margin:0 4px}}
.main{{padding:24px 28px 48px;position:relative;z-index:1;max-width:1700px;margin:0 auto}}
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:20px}}
.kpi{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:20px 22px;cursor:default;position:relative;overflow:hidden;transition:transform 0.2s,box-shadow 0.2s,border-color 0.2s;animation:fadeUp 0.5s ease both}}
.kpi:hover{{transform:translateY(-3px);border-color:var(--bdr2);box-shadow:0 16px 48px rgba(0,0,0,0.3)}}
.kpi-acc{{position:absolute;top:0;left:0;right:0;height:2px;border-radius:var(--r) var(--r) 0 0}}
.kpi-ico{{font-size:20px;margin-bottom:12px;display:block}}
.kpi-lbl{{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px;font-family:'JetBrains Mono',monospace;margin-bottom:5px}}
.kpi-val{{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;line-height:1;margin-bottom:5px}}
.kpi-sub{{font-size:11px;color:var(--sub)}}
.kpi:nth-child(1){{animation-delay:0.05s}}.kpi:nth-child(2){{animation-delay:0.1s}}.kpi:nth-child(3){{animation-delay:0.15s}}.kpi:nth-child(4){{animation-delay:0.2s}}.kpi:nth-child(5){{animation-delay:0.25s}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.capbar{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:18px 22px;margin-bottom:20px;animation:fadeUp 0.5s 0.3s ease both}}
.capbar-top{{display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;font-size:11px;margin-bottom:14px}}
.capbar-track{{height:12px;background:var(--surf3);border-radius:6px;overflow:hidden;margin-bottom:10px;box-shadow:inset 0 1px 3px rgba(0,0,0,0.3)}}
.capbar-fill{{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--green),#34D399,var(--gold),var(--cyan));background-size:200% 100%;animation:shimmer 3s linear infinite,cin 1.5s cubic-bezier(0.16,1,0.3,1) both;position:relative}}
@keyframes shimmer{{from{{background-position:100% 0}}to{{background-position:-100% 0}}}}
@keyframes cin{{from{{width:0!important}}}}
.capbar-fill::after{{content:'';position:absolute;right:0;top:0;width:4px;height:100%;background:white;opacity:0.5;border-radius:3px;animation:tip 1.5s ease infinite}}
@keyframes tip{{0%,100%{{opacity:0.5}}50%{{opacity:0}}}}
.capbar-lbl{{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.charts-row{{display:grid;grid-template-columns:210px 1fr 2fr;gap:14px;margin-bottom:24px}}
.cc{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:20px;animation:fadeUp 0.5s 0.35s ease both;transition:border-color 0.2s}}
.cc:hover{{border-color:var(--bdr2)}}
.ctitle{{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.ctitle::before{{content:'';width:3px;height:11px;background:var(--gold);border-radius:2px;flex-shrink:0}}
.sec-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;margin-top:8px}}
.sec-title{{font-family:'Syne',sans-serif;font-size:17px;font-weight:800;display:flex;align-items:center;gap:10px}}
.sico{{width:30px;height:30px;border-radius:9px;background:rgba(245,158,11,0.12);display:flex;align-items:center;justify-content:center;font-size:15px}}
.bdg{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;background:rgba(245,158,11,0.1);color:var(--gold);border:1px solid rgba(245,158,11,0.2)}}
.pos-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;margin-bottom:28px}}
.pos-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;cursor:pointer;position:relative;transition:transform 0.2s,border-color 0.2s,box-shadow 0.2s;animation:fadeUp 0.5s ease both}}
.pos-card:hover{{transform:translateY(-4px);border-color:var(--bdr2);box-shadow:0 20px 60px rgba(0,0,0,0.4)}}
.pos-glow{{position:absolute;inset:0;pointer-events:none}}
.pos-top{{display:flex;justify-content:space-between;align-items:flex-start;padding:18px 18px 12px;gap:12px}}
.pos-sym{{font-family:'Syne',sans-serif;font-size:21px;font-weight:800;letter-spacing:-0.5px;margin-bottom:7px}}
.pos-chips{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}}
.chip-tier{{font-size:10px;font-weight:700;padding:2px 8px;border-radius:8px;border:1px solid;font-family:'JetBrains Mono',monospace;background:transparent}}
.chip-sec{{font-size:10px;color:var(--sub);font-family:'JetBrains Mono',monospace;padding:2px 0}}
.chip-st{{font-size:10px;font-family:'JetBrains Mono',monospace;color:var(--muted)}}
.trail-chip{{font-size:9px;font-weight:700;padding:2px 8px;border-radius:8px;background:rgba(6,182,212,0.12);color:#06B6D4;border:1px solid rgba(6,182,212,0.25);font-family:'JetBrains Mono',monospace;display:inline-block;margin-top:4px;animation:tblink 2s ease infinite}}
@keyframes tblink{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
.warn-chip{{font-size:9px;font-weight:700;padding:2px 8px;border-radius:8px;background:rgba(239,68,68,0.12);color:#EF4444;border:1px solid rgba(239,68,68,0.25);font-family:'JetBrains Mono',monospace;display:inline-block;margin-top:4px}}
.pos-nums{{text-align:right;flex-shrink:0}}
.pos-pct{{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;line-height:1}}
.pos-pnl{{font-family:'JetBrains Mono',monospace;font-size:12px;margin-top:3px;font-weight:600}}
.pos-cmp{{font-size:11px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-top:3px}}
.pos-bar-wrap{{padding:0 18px 14px}}
.pos-bar-track{{height:5px;background:var(--surf3);border-radius:3px;overflow:hidden;margin-bottom:6px}}
.pos-bar-fill{{height:100%;border-radius:3px;transition:width 1.3s cubic-bezier(0.16,1,0.3,1)}}
.pos-bar-lbl{{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.pos-exp{{max-height:0;overflow:hidden;transition:max-height 0.4s ease,padding 0.3s ease;border-top:0px solid var(--bdr)}}
.pos-card.open .pos-exp{{max-height:140px;border-top:1px solid var(--bdr);padding:14px 18px}}
.eg{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.egi{{display:flex;flex-direction:column;gap:3px}}
.egl{{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;font-family:'JetBrains Mono',monospace}}
.egv{{font-size:11px;font-weight:600;font-family:'JetBrains Mono',monospace;color:var(--sub)}}
.tbl-wrap{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;margin-bottom:24px;animation:fadeUp 0.5s 0.4s ease both}}
table{{width:100%;border-collapse:collapse}}
thead th{{padding:10px 16px;text-align:left;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid var(--bdr);font-family:'JetBrains Mono',monospace;font-weight:500}}
.ct-row td{{padding:12px 16px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.025);transition:background 0.15s}}
.ct-row:hover td{{background:rgba(255,255,255,0.02)}}.ct-row:last-child td{{border-bottom:none}}
.cm{{color:var(--sub);font-family:'JetBrains Mono',monospace;font-size:12px}}
.sym-tag{{background:var(--surf3);border:1px solid var(--bdr2);padding:3px 10px;border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.empty{{padding:60px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:12px}}
.footer{{text-align:center;padding:24px;font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace;border-top:1px solid var(--bdr);position:relative;z-index:1}}
.confetti-p{{position:fixed;pointer-events:none;z-index:9999;width:8px;height:8px;border-radius:2px;animation:cf linear forwards}}
@keyframes cf{{0%{{transform:translateY(-20px) rotate(0deg);opacity:1}}100%{{transform:translateY(100vh) rotate(720deg);opacity:0}}}}
@media(max-width:1200px){{.kpi-grid{{grid-template-columns:repeat(3,1fr)}}.charts-row{{grid-template-columns:1fr 1fr}}.charts-row .cc:last-child{{grid-column:1/-1}}}}
@media(max-width:768px){{.kpi-grid{{grid-template-columns:repeat(2,1fr)}}.charts-row{{grid-template-columns:1fr}}.main{{padding:14px}}.hdr{{padding:0 14px}}.hdr-c{{display:none}}.pos-grid{{grid-template-columns:1fr}}.eg{{grid-template-columns:1fr 1fr}}.kpi-val{{font-size:22px}}}}
</style>
</head>
<body>
<canvas id="ptc"></canvas>
<div class="mesh"></div>
<div class="rbar"></div>
<header class="hdr">
  <div class="hdr-l">
    <div class="bolt">⚡</div>
    <div class="logo-t">POWER<span>15</span></div>
  </div>
  <div class="hdr-c">
    <span class="npill" style="color:{nifty_col}">{nifty_str}</span>
    <span class="mpill">{mkt_str}</span>
  </div>
  <div class="hdr-r">
    <div class="live">LIVE</div>
    <div class="clk" id="clk">{now.strftime('%H:%M:%S IST')}</div>
    <button class="tbtn" onclick="toggleTheme()" title="Toggle light/dark">🌓</button>
  </div>
</header>
<div class="ticker" title="Hover to pause">
  <div class="ticker-inner">{items}</div>
</div>
<div class="main">
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-acc" style="background:{'var(--green)' if total_pnl>=0 else 'var(--red)'}"></div><span class="kpi-ico">{'📈' if total_pnl>=0 else '📉'}</span><div class="kpi-lbl">Total P&L</div><div class="kpi-val" style="color:{'var(--green)' if total_pnl>=0 else 'var(--red)'}" data-val="{round(total_pnl)}" data-fmt="is">{fmt_inr(total_pnl,signed=True)}</div><div class="kpi-sub">{total_ret:+.2f}% overall return</div></div>
    <div class="kpi"><div class="kpi-acc" style="background:var(--blue)"></div><span class="kpi-ico">💰</span><div class="kpi-lbl">Available</div><div class="kpi-val" style="color:var(--blue)" data-val="{round(cap['available'])}" data-fmt="i">{fmt_inr(cap['available'])}</div><div class="kpi-sub">of {fmt_inr(cap['initial'])} capital</div></div>
    <div class="kpi"><div class="kpi-acc" style="background:var(--gold)"></div><span class="kpi-ico">🎯</span><div class="kpi-lbl">Open Positions</div><div class="kpi-val" style="color:var(--gold)">{len(open_t)}</div><div class="kpi-sub">{fmt_inr(cap['invested'])} deployed</div></div>
    <div class="kpi"><div class="kpi-acc" style="background:var(--purple)"></div><span class="kpi-ico">🏆</span><div class="kpi-lbl">Win Rate</div><div class="kpi-val" style="color:var(--purple)">{win_rate:.0f}%</div><div class="kpi-sub">{cap['winning_trades']}/{cap['total_trades']} trades</div></div>
    <div class="kpi"><div class="kpi-acc" style="background:{'var(--green)' if total_unreal>=0 else 'var(--red)'}"></div><span class="kpi-ico">⚡</span><div class="kpi-lbl">Unrealised</div><div class="kpi-val" style="color:{'var(--green)' if total_unreal>=0 else 'var(--red)'}" data-val="{round(total_unreal)}" data-fmt="is">{fmt_inr(total_unreal,signed=True)}</div><div class="kpi-sub">{len(open_t)} live positions</div></div>
  </div>
  <div class="capbar">
    <div class="capbar-top">
      <div style="display:flex;align-items:center;gap:14px">
        <span style="font-weight:600;color:var(--sub);font-family:'JetBrains Mono',monospace;font-size:11px">CAPITAL UTILISATION</span>
        <span style="color:var(--gold);font-weight:700;font-family:'JetBrains Mono',monospace;font-size:11px">{inv_pct:.1f}% DEPLOYED</span>
      </div>
      <div style="display:flex;gap:20px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted)">
        <span>Free: <b style="color:var(--green)">{fmt_inr(cap['available'])}</b></span>
        <span>Used: <b style="color:var(--gold)">{fmt_inr(cap['invested'])}</b></span>
        <span>Total: <b style="color:var(--blue)">{fmt_inr(cap['initial'])}</b></span>
      </div>
    </div>
    <div class="capbar-track"><div class="capbar-fill" style="width:{inv_pct:.1f}%"></div></div>
    <div class="capbar-lbl"><span>₹0</span><span>Deployed: <b style="color:var(--gold)">{fmt_full(cap['invested'])}</b></span><span>{fmt_full(cap['initial'])}</span></div>
  </div>
  <div class="charts-row">
    <div class="cc"><div class="ctitle">Sector Mix</div>{f'<canvas id="pie" style="max-height:170px"></canvas>' if sec_data else '<div style="padding:30px;text-align:center;color:var(--muted)">No positions</div>'}</div>
    <div class="cc"><div class="ctitle">Stock P&L</div>{f'<canvas id="bar"></canvas>' if enriched else '<div style="padding:30px;text-align:center;color:var(--muted)">No positions</div>'}</div>
    <div class="cc"><div class="ctitle">Cumulative P&L Curve</div><canvas id="line"></canvas></div>
  </div>
  <div class="sec-hdr">
    <div class="sec-title"><div class="sico">🚀</div>Open Positions</div>
    <div class="bdg">{len(enriched)} ACTIVE</div>
  </div>
  {f'<div class="pos-grid">{cards}</div>' if enriched else '<div class="tbl-wrap"><div class="empty"><div style="font-size:40px">🌙</div><div style="font-size:16px;font-weight:600">No open positions</div><div style="font-size:13px;color:var(--sub)">Signals fire at 3:25 PM weekdays · Scanner at 3:30 PM</div></div></div>'}
  {f'<div class="sec-hdr"><div class="sec-title"><div class="sico">📋</div>Trade History</div><div class="bdg">LAST {min(15,len(closed))}</div></div><div class="tbl-wrap"><table><thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy ₹</th><th>Sell ₹</th><th>P&L</th><th>Return</th><th>Reason</th></tr></thead><tbody>{crows}</tbody></table></div>' if closed else ''}
</div>
<div class="footer">⚡ POWER 15 · Supreme v4.0 · Auto-refreshes every 90s · 98.1% backtest win rate · CAGR 53.3% · Amounts in ₹K / ₹L / ₹Cr</div>
<script>
function fmtINR(v,signed=false){{const neg=v<0,a=Math.abs(v);let s;if(a>=1e7)s='₹'+(a/1e7).toFixed(2)+'Cr';else if(a>=1e5)s='₹'+(a/1e5).toFixed(1)+'L';else if(a>=1e3)s='₹'+(a/1e3).toFixed(1)+'K';else s='₹'+a.toFixed(0);return signed?(neg?'-':'+'):neg?'-':'',s}}
function fmtINR2(v,signed=false){{const neg=v<0,a=Math.abs(v);let s;if(a>=1e7)s='₹'+(a/1e7).toFixed(2)+'Cr';else if(a>=1e5)s='₹'+(a/1e5).toFixed(1)+'L';else if(a>=1e3)s='₹'+(a/1e3).toFixed(1)+'K';else s='₹'+a.toFixed(0);if(signed)return(neg?'-':'+')+s;return(neg?'-':'')+s}}
// Particle BG
const cv=document.getElementById('ptc'),ctx2=cv.getContext('2d');let W,H,pts=[];
function rsz(){{W=cv.width=window.innerWidth;H=cv.height=window.innerHeight}}rsz();window.addEventListener('resize',rsz);
for(let i=0;i<55;i++)pts.push({{x:Math.random()*2000,y:Math.random()*1000,r:Math.random()*1.5+0.3,vx:(Math.random()-.5)*.15,vy:(Math.random()-.5)*.15,a:Math.random()*.4+.1,c:['#F59E0B','#3B82F6','#A855F7','#10B981','#06B6D4'][Math.floor(Math.random()*5)]}});
(function anim(){{ctx2.clearRect(0,0,W,H);pts.forEach(p=>{{p.x+=p.vx;p.y+=p.vy;if(p.x<0)p.x=W;if(p.x>W)p.x=0;if(p.y<0)p.y=H;if(p.y>H)p.y=0;ctx2.beginPath();ctx2.arc(p.x,p.y,p.r,0,Math.PI*2);ctx2.fillStyle=p.c+Math.floor(p.a*255).toString(16).padStart(2,'0');ctx2.fill()}});requestAnimationFrame(anim)}})();
// Clock
setInterval(()=>{{const n=new Date(),ist=new Date(n.toLocaleString('en-US',{{timeZone:'Asia/Kolkata'}})),h=String(ist.getHours()).padStart(2,'0'),m=String(ist.getMinutes()).padStart(2,'0'),s=String(ist.getSeconds()).padStart(2,'0'),el=document.getElementById('clk');if(el)el.textContent=h+':'+m+':'+s+' IST'}},1000);
// Theme
function toggleTheme(){{const h=document.documentElement;h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';localStorage.setItem('p15t',h.dataset.theme)}}
(()=>{{const s=localStorage.getItem('p15t');if(s)document.documentElement.dataset.theme=s}})();
// Card expand
function toggleX(el){{const was=el.classList.contains('open');document.querySelectorAll('.pos-card.open').forEach(c=>c.classList.remove('open'));if(!was)el.classList.add('open')}}
// Confetti
if({round(win_rate,1)}>=95){{const cols=['#F59E0B','#10B981','#3B82F6','#A855F7','#EF4444','#06B6D4'];for(let i=0;i<80;i++)setTimeout(()=>{{const el=document.createElement('div');el.className='confetti-p';el.style.cssText=`left:${{Math.random()*100}}vw;top:-10px;background:${{cols[Math.floor(Math.random()*cols.length)]}};animation-duration:${{1.5+Math.random()*2}}s;animation-delay:${{Math.random()*1.5}}s;transform:rotate(${{Math.random()*360}}deg)`;document.body.appendChild(el);setTimeout(()=>el.remove(),5000)}},i*40)}}
// Counter animation
document.querySelectorAll('[data-fmt]').forEach(el=>{{const tgt=parseInt(el.dataset.val||0),fmt=el.dataset.fmt,dur=1400,st=performance.now();(function step(now){{const t=Math.min((now-st)/dur,1),e=1-Math.pow(1-t,4),cur=Math.round(tgt*e);el.textContent=fmtINR2(cur,fmt==='is');if(t<1)requestAnimationFrame(step)}})( performance.now())}});
// Charts
Chart.defaults.color='#475569';Chart.defaults.borderColor='rgba(255,255,255,0.05)';Chart.defaults.font.family="'Plus Jakarta Sans',sans-serif";
const SD={sec_js},PH={pnl_js},PS={pos_js};
if(SD.length&&document.getElementById('pie'))new Chart(document.getElementById('pie'),{{type:'doughnut',data:{{labels:SD.map(d=>d.label),datasets:[{{data:SD.map(d=>d.value),backgroundColor:SD.map(d=>d.color),borderWidth:3,borderColor:'#0A1020',hoverOffset:10}}]}},options:{{cutout:'72%',responsive:true,plugins:{{legend:{{position:'bottom',labels:{{color:'#94A3B8',padding:8,font:{{size:9}},boxWidth:9}}}},tooltip:{{callbacks:{{label:c=>' '+fmtINR2(c.raw)}}}}}}}} }});
if(PS.length&&document.getElementById('bar'))new Chart(document.getElementById('bar'),{{type:'bar',data:{{labels:PS.map(p=>p.symbol),datasets:[{{label:'P&L',data:PS.map(p=>p.pnl),backgroundColor:PS.map(p=>p.pnl>=0?'rgba(16,185,129,0.7)':'rgba(239,68,68,0.7)'),borderColor:PS.map(p=>p.pnl>=0?'#10B981':'#EF4444'),borderWidth:1,borderRadius:6}}]}},options:{{responsive:true,indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fmtINR2(c.raw,true)}}}}}},scales:{{x:{{ticks:{{color:'#475569',callback:v=>fmtINR2(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}},y:{{grid:{{display:false}},ticks:{{color:'#EEF2FF',font:{{weight:'700',size:11}}}}}}}}}}}});
const lc=document.getElementById('line');if(lc){{const last=PH[PH.length-1]||0,isP=last>=0,g=lc.getContext('2d').createLinearGradient(0,0,0,220);isP?(g.addColorStop(0,'rgba(16,185,129,0.28)'),g.addColorStop(1,'rgba(16,185,129,0)')):(g.addColorStop(0,'rgba(239,68,68,0.28)'),g.addColorStop(1,'rgba(239,68,68,0)'));new Chart(lc,{{type:'line',data:{{labels:PH.length>1?PH.map((_,i)=>'T'+(i+1)):['{now.strftime("%d %b")}'],datasets:[{{label:'P&L',data:PH.length?PH:[0],borderColor:isP?'#10B981':'#EF4444',backgroundColor:g,fill:true,tension:0.45,pointRadius:PH.length>20?0:4,pointHoverRadius:9,pointBackgroundColor:isP?'#10B981':'#EF4444',pointBorderColor:'#0A1020',pointBorderWidth:2,borderWidth:2.5}}]}},options:{{responsive:true,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fmtINR2(c.raw,true)}},backgroundColor:'#0A1020',borderColor:'rgba(245,158,11,0.3)',borderWidth:1,titleColor:'#F59E0B',bodyColor:'#EEF2FF',padding:12,cornerRadius:10}}}},scales:{{x:{{ticks:{{color:'#475569',maxTicksLimit:8}},grid:{{color:'rgba(255,255,255,0.03)'}}}},y:{{ticks:{{color:'#475569',callback:v=>fmtINR2(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}}}}}})}}
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html=build().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-type","text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)
    def log_message(self,*a): pass

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"\n  ⚡ Power 15 Supreme Dashboard v4.0 — port {port}\n")
    HTTPServer(("",port),Handler).serve_forever()
