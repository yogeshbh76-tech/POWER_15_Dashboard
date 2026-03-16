"""
Power 15 — The Terminal v5.0
World-class trading dashboard inspired by Bloomberg + Robinhood + Kite
Live prices refresh every 15 seconds via client-side JS
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

def fi(v,s=False):
    sg="" 
    if s: sg="+" if v>=0 else "-"; v=abs(v)
    elif v<0: sg="-"; v=abs(v)
    if v>=1e7: r=f"₹{v/1e7:.2f}Cr"
    elif v>=1e5: r=f"₹{v/1e5:.1f}L"
    elif v>=1e3: r=f"₹{v/1e3:.1f}K"
    else: r=f"₹{v:.0f}"
    return sg+r

def ff(v):
    n=v<0; v=int(abs(v)); s=str(v)
    if len(s)>3:
        l=s[-3:]; r=s[:-3]; c=[]
        while len(r)>2: c.insert(0,r[-2:]); r=r[:-2]
        if r: c.insert(0,r)
        s=",".join(c)+","+l
    return ("-₹" if n else "₹")+s

def sup(t):
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{t}?select=*",headers=HDR,timeout=10)
        return r.json() if r.status_code==200 else []
    except: return []

def cmp(s):
    try:
        r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}.NS",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except: return None

def nifty():
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        d=r.json()["chart"]["result"][0]; cl=[c for c in d["indicators"]["quote"][0]["close"] if c]
        p=float(d["meta"]["regularMarketPrice"]); ch=(p-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        return p,ch
    except: return None,None

def build():
    now=datetime.now(IST)
    trades=sup("p15_trades"); cr=sup("p15_capital")
    cap=cr[0] if cr else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
    ot=[t for t in trades if t.get("status")=="OPEN"]
    cl=[t for t in trades if t.get("status")=="CLOSED"]
    en=[]; tu=0
    for t in ot:
        p=cmp(t["symbol"]) or t["entry_price"]
        pnl=(p-t["entry_price"])*t["quantity"]
        pct=(p-t["entry_price"])/t["entry_price"]*100
        d=(now.replace(tzinfo=None)-datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        lf=max(0,90-d); pk=t.get("peak_cmp",p)
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
    ms="OPEN" if mo else ("WEEKEND" if wk>=5 else "CLOSED")
    mscol="#10B981" if mo else "#EF4444"
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
    cr2=""
    for t in sorted(cl,key=lambda x:x.get("exit_date","0"),reverse=True)[:15]:
        pnl=t.get("pnl",0); pct2=t.get("pnl_pct",0); col="#10B981" if pnl>=0 else "#EF4444"
        r=t.get("exit_reason",""); rt="🛑" if "Stop" in r else "📉" if "Trail" in r else "🎯" if "target" in r.lower() else "⏰"
        cr2+=f'<tr class="cr"><td><span class="stag">{t["symbol"]}</span></td><td class="mc">{t.get("entry_date","")}</td><td class="mc">{t.get("exit_date","")}</td><td class="mc">₹{t["entry_price"]:.2f}</td><td class="mc">₹{t.get("exit_price",0):.2f}</td><td style="color:{col};font-weight:700">{fi(pnl,True)}</td><td style="color:{col};font-weight:700">{pct2:+.1f}%</td><td class="mc" style="font-size:11px">{rt} {r[:38]}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>⚡ Power 15 · The Terminal</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#020408;--s1:#080D18;--s2:#0C1220;--s3:#111928;--s4:#17243A;
  --bdr:rgba(255,255,255,0.06);--bdr2:rgba(255,255,255,0.12);
  --txt:#E8F0FF;--sub:#7C8FAD;--mut:#3D4F6A;
  --gold:#F5A623;--green:#00C896;--red:#FF4757;
  --blue:#4A9EFF;--purple:#9B6DFF;--cyan:#00D4FF;--pink:#FF6B9D;
  --r:14px;
}}
[data-theme="light"]{{
  --bg:#EEF2F9;--s1:#E4EAF5;--s2:#FFFFFF;--s3:#F5F7FC;--s4:#EBF0FA;
  --bdr:rgba(0,0,0,0.07);--bdr2:rgba(0,0,0,0.13);
  --txt:#0A1628;--sub:#4A5C78;--mut:#9AABC4;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);font-family:'DM Sans',sans-serif;color:var(--txt);min-height:100vh;overflow-x:hidden}}

/* scanlines overlay */
body::after{{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);
}}

/* ── HEADER ── */
.hdr{{
  position:sticky;top:0;z-index:200;height:56px;
  background:rgba(2,4,8,0.95);
  backdrop-filter:blur(20px);
  border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;padding:0 20px;gap:0;
}}
[data-theme="light"] .hdr{{background:rgba(238,242,249,0.95)}}
.hdr-brand{{display:flex;align-items:center;gap:10px;padding-right:20px;border-right:1px solid var(--bdr);margin-right:20px;flex-shrink:0}}
.hdr-bolt{{
  width:32px;height:32px;border-radius:9px;
  background:linear-gradient(135deg,#F5A623,#FF4757);
  display:flex;align-items:center;justify-content:center;font-size:15px;
  box-shadow:0 0 16px rgba(245,166,35,0.5);
  animation:bpulse 3s ease infinite;
}}
@keyframes bpulse{{0%,100%{{box-shadow:0 0 16px rgba(245,166,35,0.4)}}50%{{box-shadow:0 0 28px rgba(245,166,35,0.8)}}}}
.hdr-name{{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:2px;color:var(--txt)}}
.hdr-name span{{color:var(--gold)}}
.hdr-pills{{display:flex;align-items:center;gap:8px;flex:1}}
.pill{{
  display:flex;align-items:center;gap:6px;
  padding:4px 12px;border-radius:20px;
  font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;
  border:1px solid var(--bdr);background:var(--s2);
  white-space:nowrap;
}}
.pill-live{{background:rgba(0,200,150,0.08);border-color:rgba(0,200,150,0.25);color:var(--green)}}
.pill-live::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 1.2s ease infinite;flex-shrink:0}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:0.1}}}}
.pill-nifty{{color:var(--gold)}}
.pill-mkt{{color:{mscol}}}
.hdr-right{{display:flex;align-items:center;gap:8px;margin-left:auto}}
.hdr-clk{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--sub);background:var(--s2);border:1px solid var(--bdr);padding:4px 12px;border-radius:8px}}
.hdr-refresh{{
  display:flex;align-items:center;gap:6px;
  font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--sub);
  background:var(--s2);border:1px solid var(--bdr);padding:4px 10px;border-radius:8px;
  cursor:pointer;
}}
.hdr-refresh:hover{{border-color:var(--bdr2);color:var(--txt)}}
.spin{{animation:spin 1s linear infinite;display:none}}
@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
.tbtn{{width:32px;height:32px;border-radius:8px;border:1px solid var(--bdr2);background:var(--s2);color:var(--sub);cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;transition:all 0.2s}}
.tbtn:hover{{background:var(--s3);color:var(--txt)}}

/* ── TICKER ── */
.ticker{{
  height:34px;background:var(--s1);border-bottom:1px solid var(--bdr);
  overflow:hidden;display:flex;align-items:center;position:relative;z-index:1;
}}
.ticker::before,.ticker::after{{
  content:'';position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none;
}}
.ticker::before{{left:0;background:linear-gradient(90deg,var(--s1),transparent)}}
.ticker::after{{right:0;background:linear-gradient(-90deg,var(--s1),transparent)}}
.ticker-inner{{
  display:flex;gap:40px;width:max-content;
  animation:tick 50s linear infinite;
  font-family:'JetBrains Mono',monospace;font-size:11px;
}}
.ticker-inner:hover{{animation-play-state:paused}}
@keyframes tick{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.ti{{display:flex;align-items:center;gap:8px;white-space:nowrap}}
.ti-sym{{font-weight:700;color:var(--txt)}}
.ti-cmp{{color:var(--sub)}}
.ti-chg{{font-weight:600}}
.ti-sep{{color:var(--mut);margin:0 4px}}

/* ── LAYOUT ── */
.layout{{display:grid;grid-template-columns:240px 1fr;height:calc(100vh - 90px);overflow:hidden;position:relative;z-index:1}}

/* ── SIDEBAR ── */
.sidebar{{
  background:var(--s1);border-right:1px solid var(--bdr);
  display:flex;flex-direction:column;overflow-y:auto;
}}
.sidebar::-webkit-scrollbar{{width:3px}}.sidebar::-webkit-scrollbar-thumb{{background:var(--mut);border-radius:2px}}
.sb-section{{padding:16px 14px 8px;border-bottom:1px solid var(--bdr)}}
.sb-label{{font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;margin-bottom:12px}}
.sb-kpi{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.sb-kpi-lbl{{font-size:11px;color:var(--sub)}}
.sb-kpi-val{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.capbar{{margin:10px 0 4px}}
.capbar-track{{height:4px;background:var(--s4);border-radius:2px;overflow:hidden}}
.capbar-fill{{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--green),var(--gold));animation:cin 1.5s ease both}}
@keyframes cin{{from{{width:0!important}}}}
.capbar-lbl{{display:flex;justify-content:space-between;font-size:9px;color:var(--mut);font-family:'JetBrains Mono',monospace;margin-top:4px}}
.sb-stat-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:14px}}
.sb-stat{{background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:10px 12px}}
.sb-stat-lbl{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-family:'JetBrains Mono',monospace}}
.sb-stat-val{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700}}
.p15-list{{padding:0 0 8px}}
.p15-item{{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 14px;cursor:pointer;transition:background 0.15s;
  border-left:2px solid transparent;
}}
.p15-item:hover{{background:var(--s2);border-left-color:var(--gold)}}
.p15-item.active{{background:var(--s2);border-left-color:var(--gold)}}
.p15-sym{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.p15-right{{text-align:right}}
.p15-cmp{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600}}
.p15-chg{{font-size:10px;font-weight:600;font-family:'JetBrains Mono',monospace}}
.p15-tier{{font-size:9px;color:var(--mut)}}
.p15-held{{font-size:9px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(245,166,35,0.15);color:var(--gold)}}

/* ── MAIN PANEL ── */
.panel{{overflow-y:auto;background:var(--bg)}}
.panel::-webkit-scrollbar{{width:4px}}.panel::-webkit-scrollbar-thumb{{background:var(--mut);border-radius:2px}}
.panel-inner{{padding:20px;display:flex;flex-direction:column;gap:16px;min-height:100%}}

/* ── TOP ROW ── */
.top-row{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px}}

/* ── POSITIONS TABLE CARD ── */
.card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden}}
.card-hdr{{
  padding:12px 16px;border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;justify-content:space-between;
}}
.card-title{{font-size:11px;font-weight:700;color:var(--sub);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;display:flex;align-items:center;gap:8px}}
.card-title::before{{content:'';width:3px;height:12px;background:var(--gold);border-radius:2px}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;background:rgba(245,166,35,0.1);color:var(--gold);border:1px solid rgba(245,166,35,0.2)}}
.badge-green{{background:rgba(0,200,150,0.1);color:var(--green);border-color:rgba(0,200,150,0.2)}}
.badge-red{{background:rgba(255,71,87,0.1);color:var(--red);border-color:rgba(255,71,87,0.2)}}

/* ── POSITIONS TABLE ── */
table{{width:100%;border-collapse:collapse}}
.pos-table thead th{{
  padding:9px 12px;text-align:left;
  font-size:9px;font-weight:700;color:var(--mut);
  text-transform:uppercase;letter-spacing:1px;
  border-bottom:1px solid var(--bdr);
  font-family:'JetBrains Mono',monospace;
  background:var(--s2);white-space:nowrap;
}}
.pos-row td{{
  padding:11px 12px;font-size:12px;
  border-bottom:1px solid rgba(255,255,255,0.03);
  vertical-align:middle;white-space:nowrap;
  transition:background 0.12s;
}}
.pos-row:hover td{{background:rgba(255,255,255,0.025)}}
.pos-row:last-child td{{border-bottom:none}}
.pos-sym-cell{{display:flex;align-items:center;gap:8px}}
.pos-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.pos-sym-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.pos-sym-sec{{font-size:10px;color:var(--sub);margin-top:1px}}
.pos-cmp-cell{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.pos-cmp-cell.flash-g{{animation:flashg 0.6s ease}}
.pos-cmp-cell.flash-r{{animation:flashr 0.6s ease}}
@keyframes flashg{{0%,100%{{background:transparent}}50%{{background:rgba(0,200,150,0.2)}}}}
@keyframes flashr{{0%,100%{{background:transparent}}50%{{background:rgba(255,71,87,0.2)}}}}
.pos-pct{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;padding:3px 8px;border-radius:6px}}
.pos-pct.pos{{background:rgba(0,200,150,0.1);color:var(--green)}}
.pos-pct.neg{{background:rgba(255,71,87,0.1);color:var(--red)}}
.pos-pnl{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}
.minibar{{width:80px;height:5px;background:var(--s4);border-radius:3px;overflow:hidden}}
.minibar-fill{{height:100%;border-radius:3px;transition:width 0.8s ease}}
.trail-tag{{
  display:inline-flex;align-items:center;gap:4px;
  font-size:9px;font-weight:700;padding:2px 6px;border-radius:5px;
  background:rgba(0,212,255,0.1);color:var(--cyan);
  border:1px solid rgba(0,212,255,0.2);
  font-family:'JetBrains Mono',monospace;
  animation:tpulse 2s ease infinite;
}}
@keyframes tpulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
.sl-cell{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--red)}}
.days-cell{{display:flex;align-items:center;gap:6px}}
.days-num{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--sub)}}
.upd-dot{{width:5px;height:5px;border-radius:50%;background:var(--green);animation:blink 2s ease infinite;flex-shrink:0}}

/* ── MINI CHART CARD ── */
.mini-card{{display:flex;flex-direction:column}}
.mini-chart-wrap{{padding:12px;flex:1;min-height:180px}}

/* ── BOTTOM ROW ── */
.bottom-row{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}

/* ── CLOSED TABLE ── */
.ct-hdr th{{
  padding:8px 12px;text-align:left;
  font-size:9px;font-weight:700;color:var(--mut);
  text-transform:uppercase;letter-spacing:1px;
  border-bottom:1px solid var(--bdr);background:var(--s2);
  font-family:'JetBrains Mono',monospace;
}}
.cr td{{
  padding:10px 12px;font-size:12px;
  border-bottom:1px solid rgba(255,255,255,0.03);
  transition:background 0.12s;
}}
.cr:hover td{{background:rgba(255,255,255,0.025)}}
.cr:last-child td{{border-bottom:none}}
.mc{{color:var(--sub);font-family:'JetBrains Mono',monospace;font-size:11px}}
.stag{{background:var(--s3);border:1px solid var(--bdr2);padding:2px 8px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700}}

/* ── EMPTY ── */
.empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 20px;gap:12px;color:var(--sub);text-align:center}}
.empty-icon{{font-size:36px}}
.empty-title{{font-size:15px;font-weight:600;color:var(--txt)}}
.empty-sub{{font-size:12px}}

/* ── LAST UPDATE STRIP ── */
.update-strip{{
  display:flex;align-items:center;gap:8px;justify-content:flex-end;
  padding:8px 20px;
  font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--mut);
  border-top:1px solid var(--bdr);background:var(--s1);
  position:sticky;bottom:0;z-index:10;
}}
.update-strip span{{color:var(--green)}}

/* ── CONFETTI ── */
.cfp{{position:fixed;pointer-events:none;z-index:9999;width:7px;height:7px;border-radius:2px;animation:cf linear forwards}}
@keyframes cf{{0%{{transform:translateY(-20px) rotate(0deg);opacity:1}}100%{{transform:translateY(100vh) rotate(720deg);opacity:0}}}}

/* ── RESPONSIVE ── */
@media(max-width:900px){{
  .layout{{grid-template-columns:1fr;height:auto}}
  .sidebar{{display:none}}
  .top-row{{grid-template-columns:1fr}}
  .bottom-row{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<!-- HEADER -->
<header class="hdr">
  <div class="hdr-brand">
    <div class="hdr-bolt">⚡</div>
    <div class="hdr-name">POWER<span>15</span></div>
  </div>
  <div class="hdr-pills">
    <div class="pill pill-live">LIVE</div>
    <div class="pill pill-nifty">NIFTY {ns}</div>
    <div class="pill pill-mkt" style="color:{mscol}">● MKT {ms}</div>
    <div class="pill" id="last-upd">Prices loading...</div>
  </div>
  <div class="hdr-right">
    <div class="hdr-refresh" onclick="refreshPrices()" title="Refresh prices">
      <span id="spin-icon" class="spin">↻</span>
      <span id="refresh-txt">↻ Refresh</span>
    </div>
    <div class="hdr-clk" id="clk">{now.strftime('%H:%M:%S')}</div>
    <button class="tbtn" onclick="toggleTheme()">🌓</button>
  </div>
</header>

<!-- TICKER -->
<div class="ticker">
  <div class="ticker-inner" id="tickerEl">
    {''.join([f'<div class="ti"><span class="ti-sym">{t["symbol"]}</span><span class="ti-cmp" id="tcmp_{t["symbol"]}">₹{t["cmp"]:.2f}</span><span class="ti-chg {"pos" if t["pct"]>=0 else "neg"}" id="tchg_{t["symbol"]}" style="color:{"#00C896" if t["pct"]>=0 else "#FF4757"}">{t["pct"]:+.2f}%</span><span class="ti-sep">·</span></div>' for t in en]*6) if en else '<div class="ti"><span class="ti-sym">POWER 15</span><span class="ti-cmp" style="color:#F5A623">No open positions · Signals fire 3:25 PM weekdays</span></div>'}
  </div>
</div>

<!-- LAYOUT -->
<div class="layout">

  <!-- SIDEBAR -->
  <aside class="sidebar">
    <!-- Portfolio summary -->
    <div class="sb-section">
      <div class="sb-label">Portfolio</div>
      <div class="sb-kpi"><span class="sb-kpi-lbl">Total P&L</span><span class="sb-kpi-val" style="color:{'var(--green)' if tp>=0 else 'var(--red)'}">{fi(tp,True)}</span></div>
      <div class="sb-kpi"><span class="sb-kpi-lbl">Unrealised</span><span class="sb-kpi-val" style="color:{'var(--green)' if tu>=0 else 'var(--red)'}" id="sb-unreal">{fi(tu,True)}</span></div>
      <div class="sb-kpi"><span class="sb-kpi-lbl">Return</span><span class="sb-kpi-val" style="color:{'var(--green)' if tr>=0 else 'var(--red)'}">{tr:+.2f}%</span></div>
      <div class="capbar">
        <div class="capbar-track"><div class="capbar-fill" style="width:{ip:.0f}%"></div></div>
        <div class="capbar-lbl"><span>{ip:.0f}% deployed</span><span>{fi(cap['available'])} free</span></div>
      </div>
    </div>
    <!-- Stats grid -->
    <div class="sb-stat-grid">
      <div class="sb-stat"><div class="sb-stat-lbl">Available</div><div class="sb-stat-val" style="color:var(--blue)">{fi(cap['available'])}</div></div>
      <div class="sb-stat"><div class="sb-stat-lbl">Invested</div><div class="sb-stat-val" style="color:var(--gold)">{fi(cap['invested'])}</div></div>
      <div class="sb-stat"><div class="sb-stat-lbl">Win Rate</div><div class="sb-stat-val" style="color:var(--purple)">{wr:.0f}%</div></div>
      <div class="sb-stat"><div class="sb-stat-lbl">Trades</div><div class="sb-stat-val" style="color:var(--cyan)">{cap['total_trades']}</div></div>
    </div>
    <!-- Watchlist -->
    <div style="padding:12px 14px 4px"><div class="sb-label">Power 15 Watchlist</div></div>
    <div class="p15-list" id="p15list">
      {''.join([f'''<div class="p15-item" id="p15_{t["symbol"]}">
        <div><div class="p15-sym">{t["symbol"]}</div><div class="p15-tier">{SECTORS.get(t["symbol"],"")}</div></div>
        <div class="p15-right">
          <div class="p15-cmp" id="p15cmp_{t["symbol"]}">₹{t["cmp"]:.2f}</div>
          <div class="p15-chg" id="p15chg_{t["symbol"]}" style="color:{"#00C896" if t["pct"]>=0 else "#FF4757"}">{t["pct"]:+.2f}%</div>
          <div class="p15-held">HELD</div>
        </div>
      </div>''' for t in en])}
    </div>
  </aside>

  <!-- MAIN PANEL -->
  <main class="panel">
    <div class="panel-inner">

      <!-- OPEN POSITIONS TABLE -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">Live Positions</div>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="upd-dot"></div>
            <span id="pos-upd-time" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--sub)">Updating...</span>
            <div class="badge">{len(en)} OPEN</div>
          </div>
        </div>
        {f'''<div style="overflow-x:auto">
        <table class="pos-table">
          <thead><tr>
            <th>Symbol</th><th>Entry</th>
            <th>CMP <span style="color:var(--green);font-size:8px">● LIVE</span></th>
            <th>P&L</th><th>Return</th>
            <th>Peak</th><th>Stop Loss</th>
            <th>Progress</th><th>Days</th><th>Status</th>
          </tr></thead>
          <tbody id="posBody">
            {''.join([f"""<tr class="pos-row" id="row_{t['symbol']}">
              <td><div class="pos-sym-cell">
                <div class="pos-dot" style="background:{SCOL.get(t['sector'],'#6B7280')}"></div>
                <div><div class="pos-sym-name">{t['symbol']}</div><div class="pos-sym-sec">{t['sector']} · T{t['tier']}</div></div>
              </div></td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:12px">₹{t['entry_price']:.2f}</td>
              <td class="pos-cmp-cell" id="cmp_{t['symbol']}">₹{t['cmp']:.2f}</td>
              <td class="pos-pnl" id="pnl_{t['symbol']}" style="color:{'var(--green)' if t['pnl']>=0 else 'var(--red)'}">{fi(t['pnl'],True)}</td>
              <td><span class="pos-pct {'pos' if t['pct']>=0 else 'neg'}" id="pct_{t['symbol']}">{t['pct']:+.2f}%</span></td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gold)" id="pk_{t['symbol']}">₹{t['peak']:.2f}<br><span style="font-size:9px;color:var(--sub)">(+{t['pkp']:.1f}%)</span></td>
              <td class="sl-cell">₹{t['sl_price']:.2f}</td>
              <td><div class="minibar"><div class="minibar-fill" id="bar_{t['symbol']}" style="width:{min(100,t['days']/90*100):.0f}%;background:{'#FF4757' if t['left']<=10 else '#F5A623' if t['left']<=30 else '#00C896'}"></div></div></td>
              <td class="days-cell"><span class="days-num">{t['days']}d/{90-t['days']}d</span></td>
              <td id="st_{t['symbol']}">{f'<span class="trail-tag">🔄 TRAILING</span>' if t['ton'] else ('<span style="color:var(--red);font-size:11px;font-weight:700">EXIT NOW</span>' if t['days']>=90 or t['cmp']<=t['sl_price'] else ('<span style="color:var(--gold);font-size:11px">WATCH</span>' if t['left']<=10 else '<span style="color:var(--green);font-size:11px">HOLD</span>'))}</td>
            </tr>""" for t in en])}
          </tbody>
        </table></div>''' if en else '<div class="empty"><div class="empty-icon">🌙</div><div class="empty-title">No open positions</div><div class="empty-sub">Buy signals trigger at 3:25 PM on weekdays</div></div>'}
      </div>

      <!-- CHARTS ROW -->
      <div class="top-row">
        <div class="card mini-card">
          <div class="card-hdr"><div class="card-title">P&L Curve</div></div>
          <div class="mini-chart-wrap"><canvas id="lineChart"></canvas></div>
        </div>
        <div class="card mini-card">
          <div class="card-hdr"><div class="card-title">Sector Mix</div></div>
          <div class="mini-chart-wrap">{f'<canvas id="pieChart"></canvas>' if sd else '<div class="empty" style="padding:30px"><div style="font-size:28px">📊</div><div style="font-size:12px;color:var(--sub)">No positions</div></div>'}</div>
        </div>
        <div class="card mini-card">
          <div class="card-hdr"><div class="card-title">Stock Returns</div></div>
          <div class="mini-chart-wrap">{f'<canvas id="barChart"></canvas>' if en else '<div class="empty" style="padding:30px"><div style="font-size:28px">📈</div><div style="font-size:12px;color:var(--sub)">No positions</div></div>'}</div>
        </div>
      </div>

      <!-- CLOSED TRADES -->
      {f'''<div class="card">
        <div class="card-hdr">
          <div class="card-title">Trade History</div>
          <div class="badge">LAST {min(15,len(cl))}</div>
        </div>
        <div style="overflow-x:auto"><table>
          <thead class="ct-hdr"><tr>
            <th>Symbol</th><th>Entry Date</th><th>Exit Date</th>
            <th>Buy ₹</th><th>Sell ₹</th><th>P&L</th><th>Return</th><th>Reason</th>
          </tr></thead>
          <tbody>{cr2}</tbody>
        </table></div>
      </div>''' if cl else ''}

    </div>

    <!-- UPDATE STRIP -->
    <div class="update-strip">
      <div class="upd-dot"></div>
      <span>Prices refresh every 15s</span>
      <span>·</span>
      <span>Last updated: <span id="last-upd-time">—</span></span>
      <span>·</span>
      <span>⚡ POWER 15 Terminal v5.0</span>
    </div>
  </main>
</div>

<script>
// ── Data from server ─────────────────────────────────────────────────────────
const SYMS  = {syms};
const TD    = {td};
const SD    = {sj};
const PH    = {pj};
const WIN   = {round(wr,1)};
const INITIAL = {round(cap['initial'])};

// ── Indian number format ─────────────────────────────────────────────────────
function fi(v, signed=false) {{
  const neg=v<0, a=Math.abs(v); let s;
  if(a>=1e7) s='₹'+(a/1e7).toFixed(2)+'Cr';
  else if(a>=1e5) s='₹'+(a/1e5).toFixed(1)+'L';
  else if(a>=1e3) s='₹'+(a/1e3).toFixed(1)+'K';
  else s='₹'+a.toFixed(0);
  if(signed) return (neg?'-':'+')+s;
  return (neg?'-':'')+s;
}}

// ── Clock ────────────────────────────────────────────────────────────────────
setInterval(()=>{{
  const n=new Date(), ist=new Date(n.toLocaleString('en-US',{{timeZone:'Asia/Kolkata'}}));
  const pad=x=>String(x).padStart(2,'0');
  const el=document.getElementById('clk');
  if(el) el.textContent=pad(ist.getHours())+':'+pad(ist.getMinutes())+':'+pad(ist.getSeconds());
}},1000);

// ── Theme ────────────────────────────────────────────────────────────────────
function toggleTheme(){{
  const h=document.documentElement;
  h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';
  localStorage.setItem('p15t',h.dataset.theme);
}}
(()=>{{ const s=localStorage.getItem('p15t'); if(s) document.documentElement.dataset.theme=s; }})();

// ── Live price fetcher (client-side, every 15s) ──────────────────────────────
const prevPrices = {{}};

async function fetchPrice(sym) {{
  try {{
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${{sym}}.NS?interval=1d&range=2d`;
    const r   = await fetch(url, {{headers:{{'User-Agent':'Mozilla/5.0'}}}});
    const d   = await r.json();
    const res = d.chart.result[0];
    const cmp = parseFloat(res.meta.regularMarketPrice);
    const prev= parseFloat(res.meta.previousClose || res.meta.chartPreviousClose || cmp);
    const pct = (cmp-prev)/prev*100;
    return {{cmp, pct}};
  }} catch(e) {{ return null; }}
}}

async function refreshPrices() {{
  if(SYMS.length===0) return;
  
  // Show spinner
  document.getElementById('spin-icon').style.display='inline';
  document.getElementById('refresh-txt').textContent='Updating...';
  
  let totalUnreal = 0;
  const now = new Date();
  
  for(const t of TD) {{
    const sym = t.sym;
    const data = await fetchPrice(sym);
    if(!data) continue;
    
    const {{cmp, pct}} = data;
    const pnl  = (cmp - t.entry) * t.qty;
    const pnlPct = (cmp - t.entry) / t.entry * 100;
    const prev = prevPrices[sym] || cmp;
    totalUnreal += pnl;

    // Flash effect on CMP change
    const cmpEl = document.getElementById(`cmp_${{sym}}`);
    if(cmpEl) {{
      const isUp = cmp > prev;
      cmpEl.textContent = '₹'+cmp.toFixed(2);
      cmpEl.className = 'pos-cmp-cell ' + (cmp!==prev ? (isUp?'flash-g':'flash-r') : '');
      setTimeout(()=>{{ if(cmpEl) cmpEl.className='pos-cmp-cell'; }}, 700);
    }}

    // P&L cell
    const pnlEl = document.getElementById(`pnl_${{sym}}`);
    if(pnlEl) {{
      pnlEl.textContent = fi(pnl, true);
      pnlEl.style.color = pnl>=0 ? 'var(--green)' : 'var(--red)';
    }}

    // Pct badge
    const pctEl = document.getElementById(`pct_${{sym}}`);
    if(pctEl) {{
      pctEl.textContent = pnlPct.toFixed(2)+'%';
      pctEl.className   = 'pos-pct '+(pnlPct>=0?'pos':'neg');
    }}

    // Peak update
    const pkEl = document.getElementById(`pk_${{sym}}`);
    if(pkEl && cmp > t.peak) {{
      t.peak = cmp;
      const pkp = (cmp-t.entry)/t.entry*100;
      pkEl.innerHTML = '₹'+cmp.toFixed(2)+'<br><span style="font-size:9px;color:var(--sub)">(+'+pkp.toFixed(1)+'%)</span>';
    }}

    // Status update (trailing check)
    const stEl = document.getElementById(`st_${{sym}}`);
    if(stEl) {{
      const peakPct = (t.peak - t.entry) / t.entry * 100;
      if(t.ton && peakPct >= (t.t||80)) {{
        stEl.innerHTML = '<span class="trail-tag">🔄 TRAILING</span>';
      }} else if(pnlPct >= 80) {{
        stEl.innerHTML = '<span style="color:var(--gold);font-size:11px;font-weight:700">🎯 TARGET</span>';
      }} else if(cmp <= t.sl) {{
        stEl.innerHTML = '<span style="color:var(--red);font-size:11px;font-weight:700">🛑 SL HIT</span>';
      }} else if(t.left<=10) {{
        stEl.innerHTML = '<span style="color:var(--gold);font-size:11px">⚠ WATCH</span>';
      }} else {{
        stEl.innerHTML = '<span style="color:var(--green);font-size:11px">HOLD</span>';
      }}
    }}

    // Ticker update
    const tcmpEl = document.getElementById(`tcmp_${{sym}}`);
    const tchgEl = document.getElementById(`tchg_${{sym}}`);
    if(tcmpEl) tcmpEl.textContent = '₹'+cmp.toFixed(2);
    if(tchgEl) {{ tchgEl.textContent = pct.toFixed(2)+'%'; tchgEl.style.color = pct>=0?'#00C896':'#FF4757'; }}

    // Sidebar P15 list
    const p15cmp = document.getElementById(`p15cmp_${{sym}}`);
    const p15chg = document.getElementById(`p15chg_${{sym}}`);
    if(p15cmp) p15cmp.textContent = '₹'+cmp.toFixed(2);
    if(p15chg) {{ p15chg.textContent = pct.toFixed(2)+'%'; p15chg.style.color = pct>=0?'#00C896':'#FF4757'; }}

    prevPrices[sym] = cmp;
  }}

  // Update unrealised in sidebar
  const unrEl = document.getElementById('sb-unreal');
  if(unrEl) {{ unrEl.textContent = fi(totalUnreal, true); unrEl.style.color = totalUnreal>=0?'var(--green)':'var(--red)'; }}

  // Update last-refresh time
  const ist = new Date(now.toLocaleString('en-US',{{timeZone:'Asia/Kolkata'}}));
  const pad = x=>String(x).padStart(2,'0');
  const ts  = pad(ist.getHours())+':'+pad(ist.getMinutes())+':'+pad(ist.getSeconds())+' IST';
  const el1 = document.getElementById('last-upd'); if(el1) el1.textContent='Updated '+ts;
  const el2 = document.getElementById('last-upd-time'); if(el2) el2.textContent=ts;
  const el3 = document.getElementById('pos-upd-time'); if(el3) el3.textContent='Updated '+ts;

  // Hide spinner
  document.getElementById('spin-icon').style.display='none';
  document.getElementById('refresh-txt').textContent='↻ Refresh';
}}

// Start auto-refresh
refreshPrices();
setInterval(refreshPrices, 15000);

// ── Charts ───────────────────────────────────────────────────────────────────
Chart.defaults.color='#3D4F6A';
Chart.defaults.borderColor='rgba(255,255,255,0.05)';
Chart.defaults.font.family="'DM Sans',sans-serif";

// Line
const lc=document.getElementById('lineChart');
if(lc){{
  const isP=PH[PH.length-1]>=0;
  const g=lc.getContext('2d').createLinearGradient(0,0,0,160);
  isP?(g.addColorStop(0,'rgba(0,200,150,0.25)'),g.addColorStop(1,'rgba(0,200,150,0)')):
      (g.addColorStop(0,'rgba(255,71,87,0.25)'),g.addColorStop(1,'rgba(255,71,87,0)'));
  new Chart(lc,{{type:'line',data:{{
    labels:PH.length>1?PH.map((_,i)=>'T'+(i+1)):['{now.strftime("%d %b")}'],
    datasets:[{{data:PH.length?PH:[0],borderColor:isP?'#00C896':'#FF4757',backgroundColor:g,
      fill:true,tension:0.45,pointRadius:PH.length>20?0:3,pointHoverRadius:7,
      pointBackgroundColor:isP?'#00C896':'#FF4757',pointBorderColor:'#020408',pointBorderWidth:2,borderWidth:2}}]
  }},options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}},
      backgroundColor:'#080D18',borderColor:'rgba(245,166,35,0.3)',borderWidth:1,
      titleColor:'#F5A623',bodyColor:'#E8F0FF',padding:10,cornerRadius:8}}}},
    scales:{{x:{{ticks:{{color:'#3D4F6A',maxTicksLimit:6}},grid:{{color:'rgba(255,255,255,0.03)'}}}},
             y:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}}
  }}}});
}}

// Donut
if(SD.length&&document.getElementById('pieChart')){{
  new Chart(document.getElementById('pieChart'),{{type:'doughnut',data:{{
    labels:SD.map(d=>d.l),
    datasets:[{{data:SD.map(d=>d.v),backgroundColor:SD.map(d=>d.c),borderWidth:3,borderColor:'#080D18',hoverOffset:8}}]
  }},options:{{cutout:'70%',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'bottom',labels:{{color:'#7C8FAD',padding:8,font:{{size:9}},boxWidth:8}}}},
      tooltip:{{callbacks:{{label:c=>' '+fi(c.raw)}}}}}}}}}});
}}

// Bar
const td2=TD.map(t=>{{const pnl=(prevPrices[t.sym]||t.entry-t.entry)*t.qty; return {{sym:t.sym,pnl:pnl,c:t.sector}}}});
if(TD.length&&document.getElementById('barChart')){{
  new Chart(document.getElementById('barChart'),{{type:'bar',data:{{
    labels:TD.map(t=>t.sym),
    datasets:[{{data:TD.map(t=>{{const c=prevPrices[t.sym]||t.entry;return (c-t.entry)*t.qty}}),
      backgroundColor:TD.map(t=>{{const c=prevPrices[t.sym]||t.entry;return c>=t.entry?'rgba(0,200,150,0.65)':'rgba(255,71,87,0.65)'}}),
      borderColor:TD.map(t=>{{const c=prevPrices[t.sym]||t.entry;return c>=t.entry?'#00C896':'#FF4757'}}),
      borderWidth:1,borderRadius:5}}]
  }},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}}}}}},
    scales:{{x:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}},
             y:{{grid:{{display:false}},ticks:{{color:'#E8F0FF',font:{{weight:'700',size:10}}}}}}}}
  }}}});
}}

// ── Confetti if win rate ≥ 95 ─────────────────────────────────────────────────
if(WIN>=95){{
  const cols=['#F5A623','#00C896','#4A9EFF','#9B6DFF','#FF4757','#00D4FF'];
  for(let i=0;i<70;i++) setTimeout(()=>{{
    const el=document.createElement('div'); el.className='cfp';
    el.style.cssText=`left:${{Math.random()*100}}vw;top:-10px;background:${{cols[Math.floor(Math.random()*6)]}};animation-duration:${{1.5+Math.random()*2}}s;animation-delay:${{Math.random()*2}}s`;
    document.body.appendChild(el); setTimeout(()=>el.remove(),5000);
  }},i*40);
}}
</script>
</body></html>"""

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
    print(f"\n  ⚡ Power 15 Terminal v5.0 — port {port}\n")
    HTTPServer(("",port),Handler).serve_forever()
