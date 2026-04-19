"""
Power 15 — The Terminal v5.2
Mobile-First + PWA-Ready + Full Responsive
+ Macro Intelligence Tab (live Nifty, signals, RBI-based entry guide)
"""
import os, json, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

SUPABASE_URL = os.environ.get("SUPABASE_URL","https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
IST = pytz.timezone("Asia/Kolkata")
HDR = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"}
SECTORS = {"NATIONALUM":"Metals","VEDL":"Metals","HINDALCO":"Metals","HINDZINC":"Metals",
           "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
           "SHRIRAMFIN":"Finance","MANAPPURAM":"Finance","ABCAPITAL":"Finance","LTF":"Finance","BAJFINANCE":"Finance",
           "FEDERALBNK":"Pvt Bank","AUBANK":"Pvt Bank"}
TIERS = {"NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
         "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,"FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
         "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3}
SCOL  = {"Metals":"#F59E0B","PSU Bank":"#3B82F6","Finance":"#A855F7","Pvt Bank":"#10B981"}
HYBRID= {"NATIONALUM":{"t":75,"tr":15},"INDIANB":{"t":70,"tr":15},"VEDL":{"t":70,"tr":18},
         "SHRIRAMFIN":{"t":70,"tr":15},"CANBK":{"t":65,"tr":15},"SBIN":{"t":70,"tr":15},
         "MANAPPURAM":{"t":60,"tr":20},"ABCAPITAL":{"t":60,"tr":20},"FEDERALBNK":{"t":65,"tr":15},
         "LTF":{"t":80,"tr":0},"BANKINDIA":{"t":65,"tr":15},"HINDALCO":{"t":70,"tr":15},
         "BAJFINANCE":{"t":80,"tr":0},"HINDZINC":{"t":80,"tr":0},"AUBANK":{"t":80,"tr":0}}

# ── Macro Intelligence config ─────────────────────────────────────────────────
# Entry signals based on RBI Annual Report 2024-25 + FSR June 2025
# Update SIGNAL/NOTE manually after each RBI report or quarterly earnings
MACRO = {
    "NATIONALUM": {"signal":"ACCUMULATE","note":"PSU aluminium; govt capex +5.2%; LME uptick","color":"#00C896","src":"RBI AR + LME"},
    "VEDL":        {"signal":"WAIT",     "note":"Wait for Q4 results clarity; critical mineral bids active","color":"#F5A623","src":"Earnings"},
    "HINDALCO":    {"signal":"BUY NOW",  "note":"HSBC top pick; LME aluminium $2,800/t; China cap","color":"#00C896","src":"RBI AR + LME"},
    "HINDZINC":    {"signal":"BUY NOW",  "note":"Net profit +46% Q3; zinc+silver at highs","color":"#00C896","src":"FSR + Earnings"},
    "INDIANB":     {"signal":"ACCUMULATE","note":"Improving ROA; dividend yield; GNPA at all-time low","color":"#00C896","src":"FSR Jun 2025"},
    "CANBK":       {"signal":"WAIT",     "note":"Near ATH resistance ₹164; wait for pullback to ₹140–145","color":"#F5A623","src":"Technical"},
    "SBIN":        {"signal":"BUY DIPS", "note":"Anchor holding; 100bps rate cut = NIM expansion","color":"#4A9EFF","src":"RBI AR + FSR"},
    "BANKINDIA":   {"signal":"WAIT",     "note":"Lowest conviction in PSU pack; watch Q4 NPA first","color":"#F5A623","src":"Earnings"},
    "SHRIRAMFIN":  {"signal":"BUY DIPS", "note":"Secured CV book; Q3 profit +9.3% QoQ; rate cut tailwind","color":"#4A9EFF","src":"FSR + Earnings"},
    "MANAPPURAM":  {"signal":"BUY NOW",  "note":"RBI raised gold LTV 75%→85%; direct volume catalyst","color":"#00C896","src":"RBI MPC Jun 2025"},
    "ABCAPITAL":   {"signal":"WAIT",     "note":"NBFC stress rose 3.9→5.9%; watch Q4 NPA data","color":"#F5A623","src":"FSR Jun 2025"},
    "LTF":         {"signal":"AVOID",    "note":"MFI/rural book under stress; avoid until NBFC stress reverses","color":"#FF4757","src":"FSR Jun 2025"},
    "BAJFINANCE":  {"signal":"WAIT",     "note":"Up 50% in 2025; 34x trailing; wait for Q4 growth guidance","color":"#F5A623","src":"Valuation"},
    "FEDERALBNK":  {"signal":"BUY NOW",  "note":"Earnings +16.9%/yr forecast; NRI deposit moat; ₹272 fair","color":"#00C896","src":"Analyst + FSR"},
    "AUBANK":      {"signal":"AVOID",    "note":"Haryana govt controversy; internal review ongoing","color":"#FF4757","src":"News Apr 2026"},
}

MACRO_UPDATED = "Apr 2026 · RBI FSR Jun 2025 · RBI AR 2024-25"

SCOL_SIG = {"BUY NOW":"#00C896","BUY DIPS":"#4A9EFF","ACCUMULATE":"#00C896",
            "WAIT":"#F5A623","AVOID":"#FF4757"}

def fi(v,s=False):
    sg=""
    if s: sg="+" if v>=0 else "-"; v=abs(v)
    elif v<0: sg="-"; v=abs(v)
    if v>=1e7: r=f"₹{v/1e7:.2f}Cr"
    elif v>=1e5: r=f"₹{v/1e5:.1f}L"
    elif v>=1e3: r=f"₹{v/1e3:.1f}K"
    else: r=f"₹{v:.0f}"
    return sg+r

def sup(t):
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{t}?select=*",headers=HDR,timeout=10)
        return r.json() if r.status_code==200 else []
    except: return []

def gcmp(s):
    try:
        r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}.NS",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        m=r.json()["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]),float(m.get("regularMarketDayLow",0))
    except: return None,None

def nifty():
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        d=r.json()["chart"]["result"][0]; cl=[c for c in d["indicators"]["quote"][0]["close"] if c]
        p=float(d["meta"]["regularMarketPrice"]); ch=(p-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        return p,ch
    except: return None,None


def fetch_ma_trades():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/ma_trades?trade_date=eq.{today}&select=*&order=created_at.desc",
            headers=HDR, timeout=10)
        return r.json() if r.status_code == 200 else []
    except: return []

def get_ma_cmp(symbol):
    try:
        r = requests.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=15m&range=1d",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except: return None

def build():
    now=datetime.now(IST)
    trades=sup("p15_trades"); cr=sup("p15_capital")
    cap=cr[0] if cr else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
    ot=[t for t in trades if t.get("status")=="OPEN"]
    cl=[t for t in trades if t.get("status")=="CLOSED"]
    en=[]; tu=0
    for t in ot:
        p,dl=gcmp(t["symbol"])
        p=p or t["entry_price"]
        pnl=(p-t["entry_price"])*t["quantity"]
        pct=(p-t["entry_price"])/t["entry_price"]*100
        d=(now.replace(tzinfo=None)-datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        lf=max(0,90-d); pk=t.get("peak_cmp") or p
        pkp=(pk-t["entry_price"])/t["entry_price"]*100
        tier=TIERS.get(t["symbol"],2); cfg=HYBRID.get(t["symbol"],{"t":80,"tr":0})
        ton=pkp>=cfg["t"] and cfg["tr"]>0
        ts=round(pk*(1-cfg["tr"]/100),2) if ton else None
        tu+=pnl
        en.append({**t,"cmp":p,"pnl":pnl,"pct":pct,"days":d,"left":lf,"peak":pk,"pkp":pkp,
                   "tier":tier,"ton":ton,"ts":ts,"sector":SECTORS.get(t["symbol"],"Other")})
    tp=cap["total_pnl"]+tu; tr=tp/cap["initial"]*100 if cap["initial"]>0 else 0
    wr=cap["winning_trades"]/cap["total_trades"]*100 if cap["total_trades"]>0 else 0
    ip=min(100,cap["invested"]/cap["initial"]*100) if cap["initial"]>0 else 0
    nc,np=nifty(); ns=f"{nc:,.0f} ({np:+.2f}%)" if nc else "—"; ncol="#10B981" if (np or 0)>=0 else "#EF4444"
    wk=now.weekday(); hr=now.hour; mn=now.minute
    mo=wk<5 and (9<hr<15 or (hr==9 and mn>=15) or (hr==15 and mn<=30))
    ms="OPEN" if mo else ("WEEKEND" if wk>=5 else "CLOSED"); mscol="#10B981" if mo else "#EF4444"
    sd={}
    for t in en: s=t["sector"]; sd[s]=sd.get(s,0)+t["entry_price"]*t["quantity"]
    ph=[]; run=0
    for t in sorted(cl,key=lambda x:x.get("exit_date","0")): run+=t.get("pnl",0); ph.append(round(run))
    sj=json.dumps([{"l":k,"v":round(v),"c":SCOL.get(k,"#6B7280")} for k,v in sd.items()])
    pj=json.dumps(ph if ph else [0])
    syms=json.dumps([t["symbol"] for t in en])
    td=json.dumps([{"sym":t["symbol"],"entry":t["entry_price"],"qty":t["quantity"],
                    "sl":t["sl_price"],"peak":t["peak"],"days":t["days"],"left":t["left"],
                    "pkp":round(t["pkp"],1),"ton":t["ton"],"ts":t["ts"],
                    "tier":t["tier"],"sector":t["sector"]} for t in en])
    # closed rows
    cr2=""
    for t in sorted(cl,key=lambda x:x.get("exit_date","0"),reverse=True)[:15]:
        pnl=t.get("pnl",0); pct2=t.get("pnl_pct",0); col="#10B981" if pnl>=0 else "#EF4444"
        r2=t.get("exit_reason",""); rt="🛑" if "Stop" in r2 else "📉" if "Trail" in r2 else "🎯" if "target" in r2.lower() else "⏰"
        cr2+=f'<tr class="cr"><td><span class="stag">{t["symbol"]}</span></td><td class="mc">{t.get("entry_date","")}</td><td class="mc">{t.get("exit_date","")}</td><td class="mc">₹{t["entry_price"]:.2f}</td><td class="mc">₹{t.get("exit_price",0):.2f}</td><td style="color:{col};font-weight:700">{fi(pnl,True)}</td><td style="color:{col};font-weight:700">{pct2:+.1f}%</td><td class="mc" style="font-size:11px">{rt} {r2[:35]}</td></tr>'
    # mobile position cards
    mob_cards=""
    for t in en:
        pc=t["pnl"]>=0; pcol="#10B981" if pc else "#EF4444"
        tc=SCOL.get(t["sector"],"#94A3B8")
        prog=min(100,t["days"]/90*100)
        bc="#EF4444" if t["left"]<=10 else "#F59E0B" if t["left"]<=30 else "#10B981"
        tl=["","🔥","✅","⚡"][t["tier"]]
        trail_html=f'<span class="m-trail">🔄 TRAIL</span>' if t["ton"] else ""
        sl_pct=(t["sl_price"]-t["entry_price"])/t["entry_price"]*100
        mob_cards+=f"""<div class="mcard" onclick="toggleMCard(this)">
  <div class="mcard-top">
    <div class="mcard-left">
      <div class="mcard-sym">{tl} {t["symbol"]}</div>
      <div class="mcard-sec" style="color:{tc}">{t["sector"]}</div>
      {trail_html}
    </div>
    <div class="mcard-right">
      <div class="mcard-pct" style="color:{pcol}">{t["pct"]:+.1f}%</div>
      <div class="mcard-pnl" style="color:{pcol}">{fi(t["pnl"],True)}</div>
      <div class="mcard-cmp" id="mcmp_{t['symbol']}">₹{t['cmp']:.2f}</div>
    </div>
  </div>
  <div class="mcard-bar">
    <div class="mbar-fill" style="width:{prog:.0f}%;background:{bc}"></div>
  </div>
  <div class="mcard-meta">{t["days"]}d / 90d &nbsp;·&nbsp; <span style="color:{bc}">{t["left"]}d left</span></div>
  <div class="mcard-detail">
    <div class="mdet"><span>Entry</span><b>₹{t["entry_price"]:.2f}</b></div>
    <div class="mdet"><span>CMP</span><b id="mdcmp_{t['symbol']}">₹{t['cmp']:.2f}</b></div>
    <div class="mdet"><span>SL</span><b style="color:#EF4444">₹{t["sl_price"]:.2f}</b></div>
    <div class="mdet"><span>Peak</span><b style="color:#F59E0B">₹{t["peak"]:.2f}</b></div>
    <div class="mdet"><span>Invested</span><b>{fi(t["entry_price"]*t["quantity"])}</b></div>
    <div class="mdet"><span>Trail at</span><b>{HYBRID.get(t["symbol"],{}).get("t",80)}%</b></div>
  </div>
</div>"""
    # ticker
    if en:
        tick_items=" ".join([f'<span class="ti"><span class="ti-s">{t["symbol"]}</span><span id="tc_{t["symbol"]}" style="color:{"#10B981" if t["pct"]>=0 else "#EF4444"}">{t["pct"]:+.2f}%</span><span id="tp_{t["symbol"]}" style="color:{"#10B981" if t["pnl"]>=0 else "#EF4444"}">{fi(t["pnl"],True)}</span><span class="td">·</span></span>' for t in en]*6)
    else:
        tick_items='<span class="ti"><span class="ti-s">POWER 15</span><span style="color:#F59E0B">Paper Trading Active · No Open Positions</span></span>'*4


    # MA Strategy
    ma_all    = fetch_ma_trades()
    ma_open   = [t for t in ma_all if t.get("status")=="OPEN"]
    ma_closed = [t for t in ma_all if t.get("status")=="CLOSED"]
    ma_enriched=[]; ma_total_unreal=0
    for t in ma_open:
        cmp2=get_ma_cmp(t["symbol"]) or t["entry_price"]
        pnl2=(cmp2-t["entry_price"])*t["quantity"]
        pct2=(cmp2-t["entry_price"])/t["entry_price"]*100
        ma_total_unreal+=pnl2
        ma_enriched.append({**t,"cmp2":cmp2,"pnl2":pnl2,"pct2":pct2})
    ma_wins=sum(1 for t in ma_closed if (t.get("exit_price",t["entry_price"])-t["entry_price"])>0)
    ma_total_tr=len(ma_closed)
    ma_wr=ma_wins/ma_total_tr*100 if ma_total_tr>0 else 0
    ma_realised=sum((t.get("exit_price",t["entry_price"])-t["entry_price"])*t["quantity"] for t in ma_closed)
    ma_total_pnl=ma_realised+ma_total_unreal
    run2=0; ma_equity=[]
    for t in sorted(ma_closed,key=lambda x:x.get("exit_time","00:00")):
        run2+=(t.get("exit_price",t["entry_price"])-t["entry_price"])*t["quantity"]
        ma_equity.append(round(run2,2))
    ma_eq_js=json.dumps(ma_equity if ma_equity else [0])
    ma_td_js=json.dumps([{"sym":t["symbol"],"entry":t["entry_price"],"qty":t["quantity"],
        "cmp":t.get("cmp2",t["entry_price"]),"pnl":round(t.get("pnl2",0),2),
        "pct":round(t.get("pct2",0),2)} for t in ma_enriched])

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<meta name="theme-color" content="#020408">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Power 15">
<link rel="manifest" href="/manifest.json">
<title>⚡ Power 15</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#020408;--s1:#080D18;--s2:#0C1220;--s3:#111928;--s4:#17243A;
  --bdr:rgba(255,255,255,0.07);--bdr2:rgba(255,255,255,0.13);
  --txt:#E8F0FF;--sub:#7C8FAD;--mut:#3D4F6A;
  --gold:#F5A623;--green:#00C896;--red:#FF4757;
  --blue:#4A9EFF;--purple:#9B6DFF;--cyan:#00D4FF;
  --r:14px;
}}
[data-theme="light"]{{
  --bg:#EEF2F9;--s1:#E4EAF5;--s2:#FFFFFF;--s3:#F5F7FC;--s4:#EBF0FA;
  --bdr:rgba(0,0,0,0.07);--bdr2:rgba(0,0,0,0.13);
  --txt:#0A1628;--sub:#4A5C78;--mut:#9AABC4;
}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
body{{background:var(--bg);font-family:'DM Sans',sans-serif;color:var(--txt);min-height:100vh;overflow-x:hidden}}
body::after{{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.02) 2px,rgba(0,0,0,0.02) 4px)}}

/* ── HEADER ── */
.hdr{{
  position:sticky;top:0;z-index:200;height:56px;
  background:rgba(2,4,8,0.95);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;padding:0 16px;gap:10px;
  safe-area-inset-top:env(safe-area-inset-top);
}}
[data-theme="light"] .hdr{{background:rgba(238,242,249,0.95)}}
.hdr-brand{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
.bolt{{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#F5A623,#FF4757);display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 0 16px rgba(245,166,35,0.5);animation:bpulse 3s ease infinite;flex-shrink:0}}
@keyframes bpulse{{0%,100%{{box-shadow:0 0 16px rgba(245,166,35,0.4)}}50%{{box-shadow:0 0 28px rgba(245,166,35,0.8)}}}}
.hdr-name{{font-family:'Bebas Neue',sans-serif;font-size:18px;letter-spacing:2px}}
.hdr-name span{{color:var(--gold)}}
.hdr-pills{{display:flex;align-items:center;gap:6px;overflow-x:auto;flex:1;scrollbar-width:none}}
.hdr-pills::-webkit-scrollbar{{display:none}}
.pill{{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;border:1px solid var(--bdr);background:var(--s2);white-space:nowrap;flex-shrink:0}}
.pill-live{{background:rgba(0,200,150,0.08);border-color:rgba(0,200,150,0.25);color:var(--green)}}
.pill-live::before{{content:'';width:5px;height:5px;border-radius:50%;background:var(--green);animation:blink 1.2s ease infinite;flex-shrink:0}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:0.1}}}}
.hdr-right{{display:flex;align-items:center;gap:6px;margin-left:auto;flex-shrink:0}}
.hdr-clk{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--sub);background:var(--s2);border:1px solid var(--bdr);padding:4px 10px;border-radius:8px;white-space:nowrap}}
.tbtn{{width:32px;height:32px;border-radius:8px;border:1px solid var(--bdr2);background:var(--s2);color:var(--sub);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}

/* ── TICKER ── */
.ticker{{height:32px;background:var(--s1);border-bottom:1px solid var(--bdr);overflow:hidden;display:flex;align-items:center;position:relative;z-index:1}}
.ticker::before,.ticker::after{{content:'';position:absolute;top:0;bottom:0;width:40px;z-index:2;pointer-events:none}}
.ticker::before{{left:0;background:linear-gradient(90deg,var(--s1),transparent)}}
.ticker::after{{right:0;background:linear-gradient(-90deg,var(--s1),transparent)}}
.ticker-inner{{display:flex;gap:32px;width:max-content;animation:tick 50s linear infinite;font-family:'JetBrains Mono',monospace;font-size:11px}}
.ticker-inner:hover{{animation-play-state:paused}}
@keyframes tick{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.ti{{display:flex;align-items:center;gap:6px;white-space:nowrap}}
.ti-s{{font-weight:700;color:var(--txt)}}
.td{{color:var(--mut);margin:0 3px}}

/* ── MOBILE NAV TABS ── */
.mob-nav{{
  display:none;
  position:sticky;top:88px;z-index:100;
  background:var(--s1);border-bottom:1px solid var(--bdr);
  padding:8px 12px;gap:6px;overflow-x:auto;scrollbar-width:none;
}}
.mob-nav::-webkit-scrollbar{{display:none}}
.mnav-btn{{
  padding:7px 16px;border-radius:20px;border:1px solid var(--bdr);
  background:var(--s2);color:var(--sub);cursor:pointer;
  font-size:12px;font-weight:600;white-space:nowrap;flex-shrink:0;
  font-family:'JetBrains Mono',monospace;transition:all 0.2s;
}}
.mnav-btn.active{{background:rgba(245,166,35,0.12);border-color:var(--gold);color:var(--gold)}}

/* ── MAIN LAYOUT ── */
.layout{{display:grid;grid-template-columns:220px 1fr;min-height:calc(100vh - 90px);position:relative;z-index:1}}

/* ── SIDEBAR ── */
.sidebar{{background:var(--s1);border-right:1px solid var(--bdr);overflow-y:auto;position:sticky;top:88px;max-height:calc(100vh - 88px)}}
.sidebar::-webkit-scrollbar{{width:3px}}.sidebar::-webkit-scrollbar-thumb{{background:var(--mut)}}
.sb-sec{{padding:14px 12px 8px;border-bottom:1px solid var(--bdr)}}
.sb-lbl{{font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;margin-bottom:10px}}
.sb-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.sb-rl{{font-size:11px;color:var(--sub)}}
.sb-rv{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.capbar{{margin:8px 0 4px}}
.cbt{{height:4px;background:var(--s4);border-radius:2px;overflow:hidden}}
.cbf{{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--green),var(--gold));animation:cin 1.5s ease both}}
@keyframes cin{{from{{width:0!important}}}}
.cbl{{display:flex;justify-content:space-between;font-size:9px;color:var(--mut);font-family:'JetBrains Mono',monospace;margin-top:4px}}
.sb-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px}}
.sb-stat{{background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:8px 10px}}
.sb-sl{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;font-family:'JetBrains Mono',monospace}}
.sb-sv{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700}}
.p15l{{padding:0 0 8px}}
.p15i{{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;cursor:pointer;transition:background 0.15s;border-left:2px solid transparent}}
.p15i:hover{{background:var(--s2);border-left-color:var(--gold)}}
.p15-name{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.p15-sect{{font-size:10px;color:var(--mut)}}
.p15r{{text-align:right}}
.p15-price{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600}}
.p15-chg{{font-size:10px;font-weight:600;font-family:'JetBrains Mono',monospace}}
.p15-held{{font-size:9px;font-weight:600;padding:1px 5px;border-radius:4px;background:rgba(245,166,35,0.15);color:var(--gold)}}

/* ── PANEL ── */
.panel{{overflow-y:auto;background:var(--bg);min-height:100%}}
.panel::-webkit-scrollbar{{width:4px}}.panel::-webkit-scrollbar-thumb{{background:var(--mut)}}
.pi{{padding:16px;display:flex;flex-direction:column;gap:14px}}

/* ── CARD ── */
.card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden}}
.card-hdr{{padding:12px 14px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;justify-content:space-between}}
.card-title{{font-size:10px;font-weight:700;color:var(--sub);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;display:flex;align-items:center;gap:7px}}
.card-title::before{{content:'';width:3px;height:11px;background:var(--gold);border-radius:2px;flex-shrink:0}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;background:rgba(245,166,35,0.1);color:var(--gold);border:1px solid rgba(245,166,35,0.2)}}
.upd-dot{{width:5px;height:5px;border-radius:50%;background:var(--green);animation:blink 2s ease infinite}}

/* ── DESKTOP TABLE ── */
.desk-table{{display:block;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:700px}}
.pos-table thead th{{padding:8px 10px;text-align:left;font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--bdr);background:var(--s2);font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.pos-row td{{padding:10px 10px;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;white-space:nowrap;transition:background 0.12s}}
.pos-row:hover td{{background:rgba(255,255,255,0.025)}}
.pos-row:last-child td{{border-bottom:none}}
.psym{{display:flex;align-items:center;gap:7px}}
.pdot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.psn{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.pss{{font-size:9px;color:var(--sub);margin-top:1px}}
.pcmp{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;border-radius:4px;padding:2px 4px;transition:background 0.3s}}
.flash-g{{animation:fg 0.6s ease}}
.flash-r{{animation:fr 0.6s ease}}
@keyframes fg{{0%,100%{{background:transparent}}50%{{background:rgba(0,200,150,0.2)}}}}
@keyframes fr{{0%,100%{{background:transparent}}50%{{background:rgba(255,71,87,0.2)}}}}
.ppct{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;padding:3px 7px;border-radius:6px}}
.ppct.pos{{background:rgba(0,200,150,0.1);color:var(--green)}}
.ppct.neg{{background:rgba(255,71,87,0.1);color:var(--red)}}
.ppnl{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.pmini{{width:70px;height:4px;background:var(--s4);border-radius:2px;overflow:hidden}}
.pmini-f{{height:100%;border-radius:2px}}
.trail-t{{display:inline-flex;align-items:center;gap:3px;font-size:9px;font-weight:700;padding:2px 5px;border-radius:4px;background:rgba(0,212,255,0.1);color:var(--cyan);border:1px solid rgba(0,212,255,0.2);font-family:'JetBrains Mono',monospace;animation:tp 2s ease infinite}}
@keyframes tp{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}

/* ── MOBILE CARDS ── */
.mob-cards{{display:none;padding:12px;gap:10px;flex-direction:column}}
.mcard{{background:var(--s1);border:1px solid var(--bdr);border-radius:12px;overflow:hidden;cursor:pointer;transition:all 0.2s}}
.mcard:hover,.mcard:active{{border-color:var(--bdr2);transform:translateY(-1px)}}
.mcard-top{{display:flex;justify-content:space-between;align-items:flex-start;padding:14px 14px 10px}}
.mcard-left{{flex:1}}
.mcard-sym{{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:1px;margin-bottom:3px}}
.mcard-sec{{font-size:10px;font-family:'JetBrains Mono',monospace;margin-bottom:4px}}
.m-trail{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:6px;background:rgba(0,212,255,0.1);color:var(--cyan);border:1px solid rgba(0,212,255,0.2);font-family:'JetBrains Mono',monospace;display:inline-block;animation:tp 2s ease infinite}}
.mcard-right{{text-align:right;flex-shrink:0;padding-left:10px}}
.mcard-pct{{font-family:'Bebas Neue',sans-serif;font-size:26px;letter-spacing:1px;line-height:1}}
.mcard-pnl{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;margin-top:2px}}
.mcard-cmp{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--sub);margin-top:2px}}
.mcard-bar{{height:4px;background:var(--s4);margin:0 14px 6px}}
.mbar-fill{{height:100%;border-radius:2px;transition:width 1s ease}}
.mcard-meta{{padding:0 14px 10px;font-size:10px;color:var(--sub);font-family:'JetBrains Mono',monospace}}
.mcard-detail{{max-height:0;overflow:hidden;transition:max-height 0.4s ease;border-top:0 solid var(--bdr)}}
.mcard.open .mcard-detail{{max-height:120px;border-top-width:1px;padding:12px 14px}}
.mdet-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.mdet{{display:flex;flex-direction:column;gap:2px}}
.mdet span{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:0.8px}}
.mdet b{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--sub)}}

/* ── CHARTS ── */
.charts-row{{display:grid;grid-template-columns:180px 1fr 2fr;gap:12px}}
.cc{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:14px;transition:border-color 0.2s}}
.cc:hover{{border-color:var(--bdr2)}}
.ctitle{{font-size:10px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:12px;display:flex;align-items:center;gap:7px}}
.ctitle::before{{content:'';width:3px;height:10px;background:var(--gold);border-radius:2px;flex-shrink:0}}
.cw{{min-height:160px}}

/* ── KPI ROW (mobile top) ── */
.kpi-strip{{display:none;overflow-x:auto;gap:10px;padding:0 12px 4px;scrollbar-width:none}}
.kpi-strip::-webkit-scrollbar{{display:none}}
.kpi-chip{{background:var(--s1);border:1px solid var(--bdr);border-radius:12px;padding:12px 14px;flex-shrink:0;min-width:130px}}
.kpi-chip-lbl{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:4px}}
.kpi-chip-val{{font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:0.5px}}
.kpi-chip-sub{{font-size:10px;color:var(--sub);margin-top:2px}}

/* ── CLOSED TABLE ── */
.ct thead th{{padding:8px 10px;text-align:left;font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--bdr);background:var(--s2);font-family:'JetBrains Mono',monospace}}
.cr td{{padding:10px 10px;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.03);transition:background 0.12s}}
.cr:hover td{{background:rgba(255,255,255,0.025)}}.cr:last-child td{{border-bottom:none}}
.mc{{color:var(--sub);font-family:'JetBrains Mono',monospace;font-size:11px}}
.stag{{background:var(--s3);border:1px solid var(--bdr2);padding:2px 7px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700}}

/* ── BOTTOM BAR ── */
.update-bar{{display:flex;align-items:center;gap:8px;justify-content:flex-end;padding:8px 16px;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--mut);border-top:1px solid var(--bdr);background:var(--s1)}}
.update-bar span{{color:var(--green)}}

/* ── EMPTY ── */
.empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 20px;gap:10px;color:var(--sub);text-align:center}}

/* ── CONFETTI ── */
.cfp{{position:fixed;pointer-events:none;z-index:9999;width:7px;height:7px;border-radius:2px;animation:cf linear forwards}}
@keyframes cf{{0%{{transform:translateY(-20px) rotate(0deg);opacity:1}}100%{{transform:translateY(100vh) rotate(720deg);opacity:0}}}}

/* ══ RESPONSIVE BREAKPOINTS ══════════════════════════════════════════════════ */

/* TABLET (≤ 1024px) — collapse sidebar */
@media(max-width:1024px){{
  .layout{{grid-template-columns:1fr}}
  .sidebar{{display:none}}
  .charts-row{{grid-template-columns:1fr 1fr}}
  .charts-row .cc:last-child{{grid-column:1/-1}}
}}

/* MOBILE (≤ 768px) — full mobile layout */
@media(max-width:768px){{
  body{{font-size:14px}}
  .hdr{{height:52px;padding:0 12px}}
  .hdr-name{{font-size:16px}}
  .bolt{{width:28px;height:28px;font-size:14px}}
  .pill-nifty,.pill-mkt{{display:none}}
  .mob-nav{{display:flex}}
  .layout{{grid-template-columns:1fr;height:auto}}
  .sidebar{{display:none!important}}
  .panel{{overflow-y:visible}}
  .pi{{padding:10px;gap:10px}}
  .kpi-strip{{display:flex}}
  .desk-table{{display:none}}
  .mob-cards{{display:flex}}
  .charts-row{{grid-template-columns:1fr}}
  .update-bar{{padding:8px 12px;font-size:9px}}
  .ticker{{height:30px}}
  .ticker-inner{{font-size:10px}}
}}

/* SMALL MOBILE (≤ 390px) */
@media(max-width:390px){{
  .hdr-clk{{display:none}}
  .kpi-chip{{min-width:110px;padding:10px 12px}}
  .kpi-chip-val{{font-size:18px}}
}}

/* PWA standalone mode */
@media(display-mode:standalone){{
  .hdr{{padding-top:env(safe-area-inset-top)}}
  body{{padding-bottom:env(safe-area-inset-bottom)}}
}}
/* ── MACRO TAB ── */
.macro-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.macro-kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:12px}}
.mkpi{{background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:10px 12px}}
.mkpi-lbl{{font-size:9px;color:var(--sub);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:4px}}
.mkpi-val{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700}}
.mkpi-note{{font-size:9px;color:var(--mut);margin-top:3px}}
.msig-row{{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.04)}}
.msig-row:last-child{{border-bottom:none}}
.msig-left{{display:flex;align-items:center;gap:10px;flex:1}}
.msig-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.msig-sym{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;min-width:90px}}
.msig-note{{font-size:10px;color:var(--sub);flex:1}}
.msig-src{{font-size:9px;color:var(--mut);font-family:'JetBrains Mono',monospace;margin-right:8px;display:none}}
.msig-pill{{font-size:9px;font-weight:700;padding:3px 8px;border-radius:5px;white-space:nowrap;font-family:'JetBrains Mono',monospace}}
.trigger-col{{display:flex;flex-direction:column;gap:8px}}
.trig-item{{display:flex;align-items:flex-start;gap:8px;font-size:11px;color:var(--sub);padding:7px 10px;background:var(--s2);border-radius:8px;border:1px solid var(--bdr)}}
.trig-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:3px}}
.cal-row{{display:flex;gap:14px;padding:11px 0;border-bottom:1px solid rgba(255,255,255,0.04)}}
.cal-row:last-child{{border-bottom:none}}
.cal-when{{min-width:90px;font-size:10px;font-weight:700;color:var(--sub);font-family:'JetBrains Mono',monospace;padding-top:2px;flex-shrink:0}}
.cal-title{{font-size:12px;font-weight:700;color:var(--txt);margin-bottom:3px}}
.cal-desc{{font-size:11px;color:var(--sub);line-height:1.5}}
.cal-badge{{display:inline-block;font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;margin-left:6px;vertical-align:middle}}
.cb-act{{background:rgba(0,200,150,0.12);color:#00C896}}
.cb-watch{{background:rgba(245,166,35,0.1);color:#F5A623}}
.cb-info{{background:rgba(74,158,255,0.1);color:#4A9EFF}}
@media(max-width:768px){{.msig-src{{display:none}}}}
</style>
</head>
<body>

<!-- HEADER -->
<header class="hdr">
  <div class="hdr-brand">
    <div class="bolt">⚡</div>
    <div class="hdr-name">POWER<span>15</span></div>
  </div>
  <div class="hdr-pills">
    <div class="pill pill-live">LIVE</div>
    <div class="pill pill-nifty" style="color:{ncol}">NIFTY {ns}</div>
    <div class="pill pill-mkt" style="color:{mscol}">● {ms}</div>
    <div class="pill" id="last-upd" style="color:var(--sub)">Loading...</div>
  </div>
  <div class="hdr-right">
    <div class="hdr-clk" id="clk">{now.strftime('%H:%M:%S')}</div>
    <button class="tbtn" onclick="refreshPrices()" title="Refresh">↻</button>
    <button class="tbtn" onclick="toggleTheme()">🌓</button>
  </div>
</header>

<!-- MOBILE NAV TABS -->
<nav class="mob-nav" id="mobNav">
  <button class="mnav-btn active" onclick="showTab('portfolio',this)">💼 Portfolio</button>
  <button class="mnav-btn" onclick="showTab('positions',this)">📊 Positions</button>
  <button class="mnav-btn" onclick="showTab('charts',this)">📈 Charts</button>
  <button class="mnav-btn" onclick="showTab('history',this)">📋 History</button>
  <button class="mnav-btn" onclick="showTab('ma',this)">⚡ MA</button>
  <button class="mnav-btn" onclick="showTab('macro',this)">📡 Macro</button>
</nav>

<!-- TICKER -->
<div class="ticker"><div class="ticker-inner">{tick_items}</div></div>

<!-- LAYOUT -->
<div class="layout">

  <!-- SIDEBAR (desktop only) -->
  <aside class="sidebar">
    <div class="sb-sec">
      <div class="sb-lbl">Portfolio</div>
      <div class="sb-row"><span class="sb-rl">Total P&L</span><span class="sb-rv" style="color:{'var(--green)' if tp>=0 else 'var(--red)'}">{fi(tp,True)}</span></div>
      <div class="sb-row"><span class="sb-rl">Unrealised</span><span class="sb-rv" style="color:{'var(--green)' if tu>=0 else 'var(--red)'}" id="sb-unreal">{fi(tu,True)}</span></div>
      <div class="sb-row"><span class="sb-rl">Return</span><span class="sb-rv" style="color:{'var(--green)' if tr>=0 else 'var(--red)'}">{tr:+.2f}%</span></div>
      <div class="capbar"><div class="cbt"><div class="cbf" style="width:{ip:.0f}%"></div></div>
      <div class="cbl"><span>{ip:.0f}% deployed</span><span>{fi(cap['available'])} free</span></div></div>
    </div>
    <div class="sb-grid">
      <div class="sb-stat"><div class="sb-sl">Available</div><div class="sb-sv" style="color:var(--blue)">{fi(cap['available'])}</div></div>
      <div class="sb-stat"><div class="sb-sl">Invested</div><div class="sb-sv" style="color:var(--gold)">{fi(cap['invested'])}</div></div>
      <div class="sb-stat"><div class="sb-sl">Win Rate</div><div class="sb-sv" style="color:var(--purple)">{wr:.0f}%</div></div>
      <div class="sb-stat"><div class="sb-sl">Trades</div><div class="sb-sv" style="color:var(--cyan)">{cap['total_trades']}</div></div>
    </div>
    <div style="padding:10px 12px 4px"><div class="sb-lbl">P15 Watchlist</div></div>
    <div class="p15l">
      {''.join([f"""<div class="p15i"><div><div class="p15-name">{t["symbol"]}</div><div class="p15-sect">{SECTORS.get(t["symbol"],"")}</div></div><div class="p15r"><div class="p15-price" id="p15c_{t["symbol"]}">₹{t["cmp"]:.2f}</div><div class="p15-chg" id="p15g_{t["symbol"]}" style="color:{"#00C896" if t["pct"]>=0 else "#FF4757"}">{t["pct"]:+.2f}%</div><div class="p15-held">HELD</div></div></div>""" for t in en])}
    </div>
  </aside>

  <!-- MAIN PANEL -->
  <main class="panel">
    <div class="pi">

      <!-- MOBILE KPI STRIP -->
      <div class="kpi-strip" id="tab-portfolio">
        <div class="kpi-chip">
          <div class="kpi-chip-lbl">Total P&L</div>
          <div class="kpi-chip-val" style="color:{'var(--green)' if tp>=0 else 'var(--red)'}">{fi(tp,True)}</div>
          <div class="kpi-chip-sub">{tr:+.2f}% return</div>
        </div>
        <div class="kpi-chip">
          <div class="kpi-chip-lbl">Available</div>
          <div class="kpi-chip-val" style="color:var(--blue)">{fi(cap['available'])}</div>
          <div class="kpi-chip-sub">of {fi(cap['initial'])}</div>
        </div>
        <div class="kpi-chip">
          <div class="kpi-chip-lbl">Positions</div>
          <div class="kpi-chip-val" style="color:var(--gold)">{len(en)}</div>
          <div class="kpi-chip-sub">{fi(cap['invested'])} deployed</div>
        </div>
        <div class="kpi-chip">
          <div class="kpi-chip-lbl">Win Rate</div>
          <div class="kpi-chip-val" style="color:var(--purple)">{wr:.0f}%</div>
          <div class="kpi-chip-sub">{cap['winning_trades']}/{cap['total_trades']} trades</div>
        </div>
        <div class="kpi-chip">
          <div class="kpi-chip-lbl">Unrealised</div>
          <div class="kpi-chip-val" style="color:{'var(--green)' if tu>=0 else 'var(--red)'}" id="mob-unreal">{fi(tu,True)}</div>
          <div class="kpi-chip-sub">live</div>
        </div>
      </div>

      <!-- POSITIONS TABLE (desktop) + CARDS (mobile) -->
      <div id="tab-positions">
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">Live Positions</div>
            <div style="display:flex;align-items:center;gap:8px">
              <div class="upd-dot"></div>
              <span id="upd-time" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--sub)">...</span>
              <div class="badge">{len(en)} OPEN</div>
            </div>
          </div>
          {f'''<div class="desk-table"><table class="pos-table">
            <thead><tr>
              <th>Symbol</th><th>Entry</th>
              <th>CMP <span style="color:var(--green);font-size:8px">● LIVE</span></th>
              <th>P&L ₹</th><th>Return</th><th>Peak</th>
              <th>Stop Loss</th><th>Days</th><th>Status</th>
            </tr></thead>
            <tbody id="posBody">
              {''.join([f"""<tr class="pos-row" id="row_{t['symbol']}">
                <td><div class="psym"><div class="pdot" style="background:{SCOL.get(t['sector'],'#6B7280')}"></div><div><div class="psn">{t['symbol']}</div><div class="pss">{t['sector']} · T{t['tier']}</div></div></div></td>
                <td style="font-family:'JetBrains Mono',monospace;font-size:12px">₹{t['entry_price']:.2f}</td>
                <td class="pcmp" id="cmp_{t['symbol']}">₹{t['cmp']:.2f}</td>
                <td class="ppnl" id="pnl_{t['symbol']}" style="color:{'var(--green)' if t['pnl']>=0 else 'var(--red)'}">{fi(t['pnl'],True)}</td>
                <td><span class="ppct {'pos' if t['pct']>=0 else 'neg'}" id="pct_{t['symbol']}">{t['pct']:+.2f}%</span></td>
                <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gold)" id="pk_{t['symbol']}">₹{t['peak']:.2f} <span style="font-size:9px;color:var(--sub)">(+{t['pkp']:.1f}%)</span></td>
                <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--red)">₹{t['sl_price']:.2f}</td>
                <td><div class="pmini"><div class="pmini-f" style="width:{min(100,t['days']/90*100):.0f}%;background:{'#FF4757' if t['left']<=10 else '#F5A623' if t['left']<=30 else '#00C896'}"></div></div><div style="font-size:9px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-top:3px">{t['days']}d left {t['left']}d</div></td>
                <td id="st_{t['symbol']}">{f'<span class="trail-t">🔄 TRAIL</span>' if t['ton'] else ('<span style="color:var(--red);font-size:11px;font-weight:700">EXIT</span>' if t['days']>=90 or t['cmp']<=t['sl_price'] else ('<span style="color:var(--gold);font-size:11px">WATCH</span>' if t['left']<=10 else '<span style="color:var(--green);font-size:11px">HOLD</span>'))}</td>
              </tr>""" for t in en])}
            </tbody>
          </table></div>''' if en else '<div class="empty"><div style="font-size:36px">🌙</div><div style="font-size:15px;font-weight:600">No open positions</div><div style="font-size:12px;color:var(--sub)">Signals fire at 3:25 PM weekdays</div></div>'}
        </div>
        <!-- Mobile cards -->
        <div class="mob-cards" id="mobCards">
          {mob_cards if en else '<div class="empty"><div style="font-size:36px">🌙</div><div style="font-size:15px;font-weight:600;color:var(--txt)">No open positions</div><div style="font-size:12px">Signals fire at 3:25 PM weekdays</div></div>'}
        </div>
      </div>

      <!-- CHARTS -->
      <div class="charts-row" id="tab-charts">
        <div class="cc"><div class="ctitle">P&L Curve</div><div class="cw"><canvas id="lineChart"></canvas></div></div>
        <div class="cc"><div class="ctitle">Sector Mix</div><div class="cw">{f'<canvas id="pieChart"></canvas>' if sd else '<div class="empty" style="padding:20px"><div style="font-size:24px">📊</div><p style="font-size:11px;color:var(--sub)">No positions</p></div>'}</div></div>
        <div class="cc"><div class="ctitle">Stock Returns</div><div class="cw">{f'<canvas id="barChart"></canvas>' if en else '<div class="empty" style="padding:20px"><div style="font-size:24px">📈</div></div>'}</div></div>
      </div>

      <!-- HISTORY -->
      {f'''<div class="card" id="tab-history">
        <div class="card-hdr"><div class="card-title">Trade History</div><div class="badge">LAST {min(15,len(cl))}</div></div>
        <div style="overflow-x:auto"><table class="ct">
          <thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy</th><th>Sell</th><th>P&L</th><th>Ret%</th><th>Reason</th></tr></thead>
          <tbody>{cr2}</tbody>
        </table></div>
      </div>''' if cl else ''}

    <!-- MA_TAB_INJECT -->

    <!-- MACRO INTELLIGENCE TAB -->
    <div id="tab-macro" class="pi" style="padding:0">
      <div style="padding:14px 16px 0">

        <!-- Header -->
        <div class="card-hdr" style="margin-bottom:12px;padding:0 0 10px;border-bottom:1px solid var(--bdr)">
          <div class="card-title">📡 Macro Intelligence</div>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="upd-dot"></div>
            <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--sub)">{MACRO_UPDATED}</span>
            <span class="badge">LIVE NIFTY</span>
          </div>
        </div>

        <!-- Live macro KPIs -->
        <div class="macro-kpi">
          <div class="mkpi">
            <div class="mkpi-lbl">Nifty 50</div>
            <div class="mkpi-val" id="mac-nifty" style="color:{'var(--green)' if (np or 0)>=0 else 'var(--red)'}">{'%,.0f' % nc if nc else '—'}</div>
            <div class="mkpi-note" id="mac-nifty-ch">{'%+.2f%%' % np if np else '—'} today</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">Repo Rate</div>
            <div class="mkpi-val" style="color:var(--green)">5.25%</div>
            <div class="mkpi-note">100 bps cut in 2025</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">Bank GNPA</div>
            <div class="mkpi-val" style="color:var(--green)">2.3%</div>
            <div class="mkpi-note">Multi-decade low · Mar 2025</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">GDP Growth</div>
            <div class="mkpi-val">6.5%</div>
            <div class="mkpi-note">FY25 actual · FY26 projected</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">CPI Inflation</div>
            <div class="mkpi-val">4.6%</div>
            <div class="mkpi-note">Easing toward 4% target</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">Unsecured NPA</div>
            <div class="mkpi-val" style="color:var(--red)">53%</div>
            <div class="mkpi-note">Of retail slippages · caution</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">Gold LTV</div>
            <div class="mkpi-val" style="color:var(--green)">85%</div>
            <div class="mkpi-note">Raised from 75% · Jun 2025</div>
          </div>
          <div class="mkpi">
            <div class="mkpi-lbl">Govt Capex</div>
            <div class="mkpi-val" style="color:var(--green)">+5.2%</div>
            <div class="mkpi-note">FY25 · metals demand driver</div>
          </div>
        </div>

        <!-- Signal grid -->
        <div class="macro-grid">

          <!-- Metals signals -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">🔩 Metals</div><div class="badge" style="color:#F59E0B">Strongest Macro Fit</div></div>
            {''.join([f"""<div class="msig-row">
              <div class="msig-left">
                <div class="msig-dot" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}"></div>
                <div class="msig-sym">{s}</div>
                <div class="msig-note">{MACRO[s]['note']}</div>
              </div>
              <span class="msig-src">{MACRO[s]['src']}</span>
              <span class="msig-pill" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}22;color:{SCOL_SIG.get(MACRO[s]['signal'],'#888')};border:1px solid {SCOL_SIG.get(MACRO[s]['signal'],'#888')}44">{MACRO[s]['signal']}</span>
            </div>""" for s in ["NATIONALUM","VEDL","HINDALCO","HINDZINC"]])}
          </div>

          <!-- PSU Bank signals -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">🏦 PSU Banks</div><div class="badge" style="color:#3B82F6">Rate Cut Tailwind</div></div>
            {''.join([f"""<div class="msig-row">
              <div class="msig-left">
                <div class="msig-dot" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}"></div>
                <div class="msig-sym">{s}</div>
                <div class="msig-note">{MACRO[s]['note']}</div>
              </div>
              <span class="msig-src">{MACRO[s]['src']}</span>
              <span class="msig-pill" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}22;color:{SCOL_SIG.get(MACRO[s]['signal'],'#888')};border:1px solid {SCOL_SIG.get(MACRO[s]['signal'],'#888')}44">{MACRO[s]['signal']}</span>
            </div>""" for s in ["INDIANB","CANBK","SBIN","BANKINDIA"]])}
          </div>

          <!-- Finance signals -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">💰 Finance / NBFC</div><div class="badge" style="color:#A855F7">Mixed — Selective</div></div>
            {''.join([f"""<div class="msig-row">
              <div class="msig-left">
                <div class="msig-dot" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}"></div>
                <div class="msig-sym">{s}</div>
                <div class="msig-note">{MACRO[s]['note']}</div>
              </div>
              <span class="msig-src">{MACRO[s]['src']}</span>
              <span class="msig-pill" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}22;color:{SCOL_SIG.get(MACRO[s]['signal'],'#888')};border:1px solid {SCOL_SIG.get(MACRO[s]['signal'],'#888')}44">{MACRO[s]['signal']}</span>
            </div>""" for s in ["SHRIRAMFIN","MANAPPURAM","ABCAPITAL","LTF","BAJFINANCE"]])}
          </div>

          <!-- Private Bank signals -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">🏧 Private Banks</div><div class="badge" style="color:#10B981">Selective Hold</div></div>
            {''.join([f"""<div class="msig-row">
              <div class="msig-left">
                <div class="msig-dot" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}"></div>
                <div class="msig-sym">{s}</div>
                <div class="msig-note">{MACRO[s]['note']}</div>
              </div>
              <span class="msig-src">{MACRO[s]['src']}</span>
              <span class="msig-pill" style="background:{SCOL_SIG.get(MACRO[s]['signal'],'#888')}22;color:{SCOL_SIG.get(MACRO[s]['signal'],'#888')};border:1px solid {SCOL_SIG.get(MACRO[s]['signal'],'#888')}44">{MACRO[s]['signal']}</span>
            </div>""" for s in ["FEDERALBNK","AUBANK"]])}
          </div>

          <!-- Green triggers -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">✅ Green Light Triggers</div><div class="badge" style="color:var(--green)">Deploy more</div></div>
            <div class="trigger-col">
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>Q4 FY26 earnings beats — SBIN, SHRIRAMFIN, HINDALCO (Apr–May 2026)</div>
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>RBI MPC rate cut announcement — one more expected FY26</div>
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>FII outflows pause or reverse — currently −₹40,289 Cr MTD Apr</div>
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>Nifty breaks + holds above 24,400–24,800 with volume</div>
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>LME aluminium / zinc hold above current levels</div>
              <div class="trig-item"><div class="trig-dot" style="background:#00C896"></div>US–Iran tensions cool — crude drops below $90/bbl</div>
            </div>
          </div>

          <!-- Red triggers -->
          <div class="card">
            <div class="card-hdr"><div class="card-title">🛑 Red Flag Triggers</div><div class="badge" style="color:var(--red)">Hold / reduce</div></div>
            <div class="trigger-col">
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>AUBANK / ABCAPITAL / LTF — Q4 NPA worsens in unsecured book</div>
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>AUBANK Haryana review reveals deeper governance issue</div>
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>Crude oil surges above $100/bbl — inflation risk, rate cuts pause</div>
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>Nifty breaks below 23,120 support — defer new buying</div>
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>RBI FSR Dec 2026 — GNPA rising above 3%</div>
              <div class="trig-item"><div class="trig-dot" style="background:#FF4757"></div>LME aluminium drops below $2,400/t — metals thesis weakens</div>
            </div>
          </div>

        </div>

        <!-- Investment Calendar -->
        <div class="card" style="margin-top:12px">
          <div class="card-hdr"><div class="card-title">📅 Investment Calendar</div><div class="badge">Apr–Dec 2026</div></div>
          <div class="cal-row">
            <div class="cal-when">Now – Apr 30</div>
            <div><div class="cal-title">Deploy Tranche 1 (30% of capital) <span class="cal-badge cb-act">Act now</span></div>
            <div class="cal-desc">HINDZINC · HINDALCO · MANAPPURAM · FEDERALBNK · NATIONALUM · SBIN. Market 8% off ATH. Do NOT deploy in AUBANK or LTF yet.</div></div>
          </div>
          <div class="cal-row">
            <div class="cal-when">Apr 20 – May 15</div>
            <div><div class="cal-title">Q4 FY26 earnings season <span class="cal-badge cb-watch">Watch &amp; decide</span></div>
            <div class="cal-desc">Read SBIN · CANBK · SHRIRAMFIN · BAJFINANCE · VEDL results. Earnings beat + NPA improves → deploy Tranche 2 (30%). Miss / worsens → hold cash.</div></div>
          </div>
          <div class="cal-row">
            <div class="cal-when">May 2026</div>
            <div><div class="cal-title">RBI Annual Report release <span class="cal-badge cb-info">Monitor</span></div>
            <div class="cal-desc">Fresh macro guidance on growth, inflation, banking stability. Reassess NBFC allocation. Deploy Tranche 3 if outlook positive.</div></div>
          </div>
          <div class="cal-row">
            <div class="cal-when">Jun – Jul 2026</div>
            <div><div class="cal-title">Final tranche + AUBANK resolution <span class="cal-badge cb-watch">Conditional</span></div>
            <div class="cal-desc">If AUBANK review closes clean: re-evaluate entry. If CANBK pulls back to ₹140–145: add PSU bank. Deploy remaining 10% to strongest performers.</div></div>
          </div>
          <div class="cal-row">
            <div class="cal-when">Dec 2026</div>
            <div><div class="cal-title">RBI FSR December 2026 — full review <span class="cal-badge cb-info">Annual reset</span></div>
            <div class="cal-desc">New Financial Stability Report. Re-map all macro signals to Power 15. Trim or add based on NPA, rate cycle, commodities.</div></div>
          </div>
        </div>

        <!-- Allocation guide -->
        <div class="card" style="margin-top:12px;margin-bottom:16px">
          <div class="card-hdr"><div class="card-title">💼 Suggested Allocation</div><div class="badge">RBI-backed</div></div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;padding:10px 0">
            <div class="mkpi"><div class="mkpi-lbl">Metals</div><div class="mkpi-val" style="color:#F59E0B">40%</div><div class="mkpi-note">HINDZINC · HINDALCO · NATIONALUM · VEDL</div></div>
            <div class="mkpi"><div class="mkpi-lbl">Banks</div><div class="mkpi-val" style="color:#3B82F6">30%</div><div class="mkpi-note">SBIN · INDIANB · CANBK · FEDERALBNK</div></div>
            <div class="mkpi"><div class="mkpi-lbl">Finance</div><div class="mkpi-val" style="color:#A855F7">20%</div><div class="mkpi-note">MANAPPURAM · SHRIRAMFIN</div></div>
            <div class="mkpi"><div class="mkpi-lbl">Opportunistic</div><div class="mkpi-val" style="color:#7C8FAD">10%</div><div class="mkpi-note">BAJFINANCE · BANKINDIA · post-results</div></div>
          </div>
          <div style="font-size:10px;color:var(--mut);padding:8px 0 4px">⚠ Not SEBI-registered advice. Based on RBI Annual Report 2024-25 and FSR June 2025. Review after each earnings season and RBI report.</div>
        </div>

      </div>
    </div>
    </div>
    <div class="update-bar">
      <div class="upd-dot"></div>
      <span>Prices refresh every 15s</span> ·
      <span>Last: <span id="last-upd-t">—</span></span> ·
      <span>⚡ Power 15 v5.2 · Macro Intelligence</span>
    </div>
  </main>
</div>

<script>
const SYMS={syms}, TD={td}, SD={sj}, PH={pj}, WR={round(wr,1)};
const prev={{}};

function fi(v,s=false){{
  const neg=v<0,a=Math.abs(v);let r;
  if(a>=1e7)r='₹'+(a/1e7).toFixed(2)+'Cr';
  else if(a>=1e5)r='₹'+(a/1e5).toFixed(1)+'L';
  else if(a>=1e3)r='₹'+(a/1e3).toFixed(1)+'K';
  else r='₹'+a.toFixed(0);
  return s?(neg?'-':'+')+r:(neg?'-':'')+r;
}}

// Clock
setInterval(()=>{{
  const n=new Date(),ist=new Date(n.toLocaleString('en-US',{{timeZone:'Asia/Kolkata'}}));
  const p=x=>String(x).padStart(2,'0'),el=document.getElementById('clk');
  if(el)el.textContent=p(ist.getHours())+':'+p(ist.getMinutes())+':'+p(ist.getSeconds());
}},1000);

// Theme
function toggleTheme(){{
  const h=document.documentElement;
  h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';
  localStorage.setItem('p15t',h.dataset.theme);
}}
(()=>{{const s=localStorage.getItem('p15t');if(s)document.documentElement.dataset.theme=s;}})();

// Mobile card expand
function toggleMCard(el){{
  const was=el.classList.contains('open');
  document.querySelectorAll('.mcard.open').forEach(c=>c.classList.remove('open'));
  if(!was)el.classList.add('open');
}}

// Live price refresh
async function refreshPrices(){{
  if(SYMS.length===0)return;
  const now=new Date(),ist=new Date(now.toLocaleString('en-US',{{timeZone:'Asia/Kolkata'}}));
  const p=x=>String(x).padStart(2,'0');
  const ts=p(ist.getHours())+':'+p(ist.getMinutes())+':'+p(ist.getSeconds())+' IST';
  
  let totalUnreal=0;
  
  for(const t of TD){{
    try{{
      const r=await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${{t.sym}}.NS`,{{headers:{{'User-Agent':'Mozilla/5.0'}}}});
      const d=await r.json();
      const m=d.chart.result[0].meta;
      const cmp=parseFloat(m.regularMarketPrice);
      const pnl=(cmp-t.entry)*t.qty;
      const pnlPct=(cmp-t.entry)/t.entry*100;
      const dayChg=(cmp-(m.previousClose||m.chartPreviousClose||cmp))/(m.previousClose||cmp)*100;
      const old=prev[t.sym]||cmp;
      totalUnreal+=pnl;

      // Desktop table
      const ce=document.getElementById(`cmp_${{t.sym}}`);
      if(ce){{
        ce.textContent='₹'+cmp.toFixed(2);
        ce.className='pcmp '+(cmp!==old?(cmp>old?'flash-g':'flash-r'):'');
        setTimeout(()=>{{if(ce)ce.className='pcmp'}},700);
      }}
      const pe=document.getElementById(`pnl_${{t.sym}}`);
      if(pe){{pe.textContent=fi(pnl,true);pe.style.color=pnl>=0?'var(--green)':'var(--red)';}}
      const pce=document.getElementById(`pct_${{t.sym}}`);
      if(pce){{pce.textContent=pnlPct.toFixed(2)+'%';pce.className='ppct '+(pnlPct>=0?'pos':'neg');}}

      // Mobile card
      const mce=document.getElementById(`mcmp_${{t.sym}}`);
      if(mce)mce.textContent='₹'+cmp.toFixed(2);
      const mdce=document.getElementById(`mdcmp_${{t.sym}}`);
      if(mdce)mdce.textContent='₹'+cmp.toFixed(2);

      // Sidebar + ticker
      const p5c=document.getElementById(`p15c_${{t.sym}}`);
      const p5g=document.getElementById(`p15g_${{t.sym}}`);
      const tc=document.getElementById(`tc_${{t.sym}}`);
      const tp2=document.getElementById(`tp_${{t.sym}}`);
      if(p5c)p5c.textContent='₹'+cmp.toFixed(2);
      if(p5g){{p5g.textContent=dayChg.toFixed(2)+'%';p5g.style.color=dayChg>=0?'#00C896':'#FF4757';}}
      if(tc){{tc.textContent=dayChg.toFixed(2)+'%';tc.style.color=dayChg>=0?'#00C896':'#FF4757';}}
      if(tp2){{tp2.textContent=fi(pnl,true);tp2.style.color=pnl>=0?'#00C896':'#FF4757';}}

      // Status
      const st=document.getElementById(`st_${{t.sym}}`);
      if(st){{
        const pp=(t.peak-t.entry)/t.entry*100;
        if(t.ton&&pp>=(t.t||80))st.innerHTML='<span class="trail-t">🔄 TRAIL</span>';
        else if(pnlPct>=80)st.innerHTML='<span style="color:var(--gold);font-size:11px;font-weight:700">🎯 TARGET</span>';
        else if(cmp<=t.sl)st.innerHTML='<span style="color:var(--red);font-size:11px;font-weight:700">🛑 SL</span>';
        else if(t.left<=10)st.innerHTML='<span style="color:var(--gold);font-size:11px">⚠ WATCH</span>';
        else st.innerHTML='<span style="color:var(--green);font-size:11px">HOLD</span>';
      }}
      prev[t.sym]=cmp;
    }}catch(e){{console.warn('Price fetch failed:',t.sym,e.message);}}
  }}

  // Update unrealised
  ['sb-unreal','mob-unreal'].forEach(id=>{{
    const el=document.getElementById(id);
    if(el){{el.textContent=fi(totalUnreal,true);el.style.color=totalUnreal>=0?'var(--green)':'var(--red)';}}
  }});

  // Timestamps
  ['last-upd','upd-time','last-upd-t'].forEach(id=>{{
    const el=document.getElementById(id);
    if(el)el.textContent=(id==='last-upd'?'Updated ':'')+ts;
  }});

  // Update macro tab Nifty live
  try{{
    const nr=await fetch('https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=2d',{{headers:{{'User-Agent':'Mozilla/5.0'}}}});
    const nd=await nr.json();
    const nm=nd.chart.result[0];
    const np2=parseFloat(nm.meta.regularMarketPrice);
    const cl2=nm.indicators.quote[0].close.filter(x=>x);
    const nch=cl2.length>=2?(np2-cl2[cl2.length-2])/cl2[cl2.length-2]*100:0;
    const mnEl=document.getElementById('mac-nifty');
    const mnCh=document.getElementById('mac-nifty-ch');
    if(mnEl){{mnEl.textContent=np2.toLocaleString('en-IN',{{maximumFractionDigits:0}});mnEl.style.color=nch>=0?'var(--green)':'var(--red)';}}
    if(mnCh)mnCh.textContent=(nch>=0?'+':'')+nch.toFixed(2)+'% today';
  }}catch(e){{}}
}}

refreshPrices();
setInterval(refreshPrices,15000);

// Charts
Chart.defaults.color='#3D4F6A';
Chart.defaults.borderColor='rgba(255,255,255,0.05)';
Chart.defaults.font.family="'DM Sans',sans-serif";

const lc=document.getElementById('lineChart');
if(lc){{
  const isP=PH[PH.length-1]>=0,g=lc.getContext('2d').createLinearGradient(0,0,0,150);
  isP?(g.addColorStop(0,'rgba(0,200,150,0.25)'),g.addColorStop(1,'rgba(0,200,150,0)')):(g.addColorStop(0,'rgba(255,71,87,0.25)'),g.addColorStop(1,'rgba(255,71,87,0)'));
  new Chart(lc,{{type:'line',data:{{labels:PH.length>1?PH.map((_,i)=>'T'+(i+1)):['{now.strftime("%d %b")}'],datasets:[{{data:PH.length?PH:[0],borderColor:isP?'#00C896':'#FF4757',backgroundColor:g,fill:true,tension:0.45,pointRadius:PH.length>20?0:3,pointHoverRadius:7,pointBackgroundColor:isP?'#00C896':'#FF4757',pointBorderColor:'#020408',pointBorderWidth:2,borderWidth:2}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}},backgroundColor:'#080D18',borderColor:'rgba(245,166,35,0.3)',borderWidth:1,titleColor:'#F5A623',bodyColor:'#E8F0FF',padding:10,cornerRadius:8}}}},scales:{{x:{{ticks:{{color:'#3D4F6A',maxTicksLimit:6}},grid:{{color:'rgba(255,255,255,0.03)'}}}},y:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}} }}}});
}}
if(SD.length&&document.getElementById('pieChart')){{
  new Chart(document.getElementById('pieChart'),{{type:'doughnut',data:{{labels:SD.map(d=>d.l),datasets:[{{data:SD.map(d=>d.v),backgroundColor:SD.map(d=>d.c),borderWidth:3,borderColor:'#080D18',hoverOffset:8}}]}},options:{{cutout:'70%',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#7C8FAD',padding:6,font:{{size:9}},boxWidth:8}}}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw)}}}}}}}} }});
}}
if(TD.length&&document.getElementById('barChart')){{
  new Chart(document.getElementById('barChart'),{{type:'bar',data:{{labels:TD.map(t=>t.sym),datasets:[{{data:TD.map(t=>{{const c=prev[t.sym]||t.entry;return(c-t.entry)*t.qty}}),backgroundColor:TD.map(t=>{{const c=prev[t.sym]||t.entry;return c>=t.entry?'rgba(0,200,150,0.65)':'rgba(255,71,87,0.65)'}}),borderColor:TD.map(t=>{{const c=prev[t.sym]||t.entry;return c>=t.entry?'#00C896':'#FF4757'}}),borderWidth:1,borderRadius:5}}]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}}}}}},scales:{{x:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}},y:{{grid:{{display:false}},ticks:{{color:'#E8F0FF',font:{{weight:'700',size:10}}}}}}}}}} }});
}}

// Confetti
if(WR>=95){{
  const cols=['#F5A623','#00C896','#4A9EFF','#9B6DFF','#FF4757','#00D4FF'];
  for(let i=0;i<60;i++)setTimeout(()=>{{
    const el=document.createElement('div');el.className='cfp';
    el.style.cssText=`left:${{Math.random()*100}}vw;top:-10px;background:${{cols[Math.floor(Math.random()*6)]}};animation-duration:${{1.5+Math.random()*2}}s;animation-delay:${{Math.random()*1.5}}s`;
    document.body.appendChild(el);setTimeout(()=>el.remove(),5000);
  }},i*40);
}}

// PWA install prompt
let deferredPrompt;
window.addEventListener('beforeinstallprompt',e=>{{deferredPrompt=e}});

// MA Strategy
const MA_EQ={ma_eq_js};
const MA_TD={ma_td_js};
const malc=document.getElementById('maLineChart');
if(malc){{
  const isP=MA_EQ[MA_EQ.length-1]>=0;
  const g=malc.getContext('2d').createLinearGradient(0,0,0,150);
  isP?(g.addColorStop(0,'rgba(0,200,150,0.25)'),g.addColorStop(1,'rgba(0,200,150,0)'))
     :(g.addColorStop(0,'rgba(255,71,87,0.25)'),g.addColorStop(1,'rgba(255,71,87,0)'));
  new Chart(malc,{{type:'line',data:{{
    labels:MA_EQ.map((_,i)=>'T'+(i+1)),
    datasets:[{{data:MA_EQ,borderColor:isP?'#00C896':'#FF4757',backgroundColor:g,
      fill:true,tension:0.4,pointRadius:4,pointHoverRadius:8,
      pointBackgroundColor:isP?'#00C896':'#FF4757',
      pointBorderColor:'#020408',pointBorderWidth:2,borderWidth:2}}]
  }},options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fmtINR2(c.raw,true)}},
      backgroundColor:'#080D18',borderColor:'rgba(245,166,35,0.3)',borderWidth:1,
      titleColor:'#F5A623',bodyColor:'#E8F0FF',padding:10,cornerRadius:8}}}},
    scales:{{x:{{ticks:{{color:'#3D4F6A',maxTicksLimit:8}},grid:{{color:'rgba(255,255,255,0.03)'}}}},
             y:{{ticks:{{color:'#3D4F6A',callback:v=>fmtINR2(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}}
  }}}});
}}
async function refreshMA(){{
  for(const t of MA_TD){{
    try{{
      const r=await fetch('https://query2.finance.yahoo.com/v8/finance/chart/'+t.sym+'.NS?interval=15m&range=1d',{{headers:{{'User-Agent':'Mozilla/5.0'}}}});
      const d=await r.json();
      const cmp=parseFloat(d.chart.result[0].meta.regularMarketPrice);
      const pnl=(cmp-t.entry)*t.qty; const pct=(cmp-t.entry)/t.entry*100;
      const ce=document.getElementById('ma_cmp_'+t.sym);
      const pe=document.getElementById('ma_pnl_'+t.sym);
      const pce=document.getElementById('ma_pct_'+t.sym);
      if(ce)ce.textContent='Rs'+cmp.toFixed(2);
      if(pe){{pe.textContent=fmtINR2(pnl,true);pe.style.color=pnl>=0?'var(--green)':'var(--red)';}}
      if(pce){{pce.textContent=pct.toFixed(2)+'%';pce.className='ppct '+(pct>=0?'pos':'neg');}}
    }}catch(e){{}}
  }}
}}
if(MA_TD.length>0){{refreshMA();setInterval(refreshMA,15000);}}

// Unified showTab — handles all 6 tabs including macro
function showTab(tab,btn){{
  document.querySelectorAll('.mnav-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  const tabs=['portfolio','positions','charts','history','ma','macro'];
  if(window.innerWidth>768)return;
  tabs.forEach(id=>{{const el=document.getElementById('tab-'+id);if(el)el.style.display='none';}});
  if(tab==='portfolio'){{
    const p=document.getElementById('tab-portfolio');if(p)p.style.display='flex';
    const pos=document.getElementById('tab-positions');if(pos)pos.style.display='block';
  }}else{{
    const el=document.getElementById('tab-'+tab);
    if(el)el.style.display=tab==='charts'?'grid':'block';
  }}
}}

</script>
</body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/manifest.json':
            manifest=json.dumps({{
                "name":"Power 15 Terminal","short_name":"Power15",
                "description":"Live NSE Trading Dashboard","start_url":"/",
                "display":"standalone","background_color":"#020408",
                "theme_color":"#F5A623","orientation":"any",
                "icons":[
                    {{"src":"https://img.icons8.com/emoji/96/lightning-emoji.png","sizes":"96x96","type":"image/png"}},
                    {{"src":"https://img.icons8.com/emoji/192/lightning-emoji.png","sizes":"192x192","type":"image/png"}}
                ]
            }})
            data=manifest.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type","application/manifest+json")
            self.end_headers()
            self.wfile.write(data)
        else:
            html=build().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type","text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)
    def log_message(self,*a): pass

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"\n  ⚡ Power 15 Terminal v5.2 Macro Intelligence — port {port}\n")
    HTTPServer(("",port),Handler).serve_forever()
