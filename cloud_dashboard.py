"""
Power 15 — The Terminal v6.0
Three-Module Dashboard:
  ① Power 15 (collapsible)        — Swing trading bot
  ② VCP Strategy (collapsible)    — Equity + Commodity VCP signals
  ③ Macro Intelligence (collapsible) — India macro + FII/DII + global signals
"""
import os, json, requests
from datetime import datetime, date
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytz

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL","https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
IST  = pytz.timezone("Asia/Kolkata")
HDR  = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"}

# ── P15 Meta ──────────────────────────────────────────────────────────────────
SECTORS = {"NATIONALUM":"Metals","VEDL":"Metals","HINDALCO":"Metals","HINDZINC":"Metals",
           "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
           "SHRIRAMFIN":"Finance","MANAPPURAM":"Finance","ABCAPITAL":"Finance","LTF":"Finance","BAJFINANCE":"Finance",
           "FEDERALBNK":"Pvt Bank","AUBANK":"Pvt Bank"}
TIERS  = {"NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
          "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,"FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
          "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3}
SCOL   = {"Metals":"#F59E0B","PSU Bank":"#3B82F6","Finance":"#A855F7","Pvt Bank":"#10B981"}
HYBRID = {"NATIONALUM":{"t":75,"tr":15},"INDIANB":{"t":70,"tr":15},"VEDL":{"t":70,"tr":18},
          "SHRIRAMFIN":{"t":70,"tr":15},"CANBK":{"t":65,"tr":15},"SBIN":{"t":70,"tr":15},
          "MANAPPURAM":{"t":60,"tr":20},"ABCAPITAL":{"t":60,"tr":20},"FEDERALBNK":{"t":65,"tr":15},
          "LTF":{"t":80,"tr":0},"BANKINDIA":{"t":65,"tr":15},"HINDALCO":{"t":70,"tr":15},
          "BAJFINANCE":{"t":80,"tr":0},"HINDZINC":{"t":80,"tr":0},"AUBANK":{"t":80,"tr":0}}

# ── VCP Universe ──────────────────────────────────────────────────────────────
VCP_EQ_STOCKS = {
    "HDFCBANK":"Banking","ICICIBANK":"Banking","KOTAKBANK":"Banking","BAJFINANCE":"Finance",
    "BSE":"Capital Mkts","ANGELONE":"Capital Mkts","MUTHOOTFIN":"Finance",
    "BEL":"Defence","HAL":"Defence","SIEMENS":"Capital Goods",
    "INFY":"IT","LTIM":"IT","COFORGE":"IT",
    "SUNPHARMA":"Pharma","DIVISLAB":"Pharma","APOLLOHOSP":"Healthcare",
    "TATASTEEL":"Metals","JSWSTEEL":"Metals","HINDALCO":"Metals","RELIANCE":"Energy"
}
VCP_COM_STOCKS = {"GOLD":"Bullion","SILVER":"Bullion","CRUDEOIL":"Energy"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def fi(v, s=False):
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
        r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}.NS",
                       headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        m=r.json()["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]),float(m.get("regularMarketDayLow",0))
    except: return None,None

def nifty():
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",
                       headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        d=r.json()["chart"]["result"][0]; cl=[c for c in d["indicators"]["quote"][0]["close"] if c]
        p=float(d["meta"]["regularMarketPrice"]); ch=(p-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        return p,ch
    except: return None,None

def get_yahoo(sym, suffix=".NS", interval="1d", range_="5d"):
    try:
        r=requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}{suffix}?interval={interval}&range={range_}",
            headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        return r.json()["chart"]["result"][0]
    except: return None


# ── Macro Data ────────────────────────────────────────────────────────────────
def fetch_macro():
    macro = {}

    # India VIX
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EINDIAVIX?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        vix = float(d["meta"]["regularMarketPrice"])
        cl  = [c for c in d["indicators"]["quote"][0]["close"] if c]
        vix_chg = (vix - cl[-2]) if len(cl)>=2 else 0
        macro["india_vix"] = {"val": round(vix,2), "chg": round(vix_chg,2),
                               "signal": "FEAR" if vix>20 else ("CAUTION" if vix>15 else "CALM")}
    except: macro["india_vix"] = {"val":"—","chg":0,"signal":"—"}

    # DXY (US Dollar Index)
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        dxy = float(d["meta"]["regularMarketPrice"])
        cl  = [c for c in d["indicators"]["quote"][0]["close"] if c]
        dxy_chg = (dxy-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        macro["dxy"] = {"val": round(dxy,2), "chg": round(dxy_chg,2),
                         "signal": "STRONG$" if dxy>105 else ("NEUTRAL" if dxy>100 else "WEAK$")}
    except: macro["dxy"] = {"val":"—","chg":0,"signal":"—"}

    # USD/INR
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        inr = float(d["meta"]["regularMarketPrice"])
        cl  = [c for c in d["indicators"]["quote"][0]["close"] if c]
        inr_chg = (inr-cl[-2]) if len(cl)>=2 else 0
        macro["usdinr"] = {"val": round(inr,2), "chg": round(inr_chg,4),
                            "signal": "WEAK₹" if inr>86 else ("STABLE" if inr>83 else "STRONG₹")}
    except: macro["usdinr"] = {"val":"—","chg":0,"signal":"—"}

    # Gold (international)
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        gold = float(d["meta"]["regularMarketPrice"])
        cl   = [c for c in d["indicators"]["quote"][0]["close"] if c]
        gold_chg = (gold-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        macro["gold"] = {"val": round(gold,1), "chg": round(gold_chg,2),
                          "signal": "BULLISH" if gold_chg>0.5 else ("BEARISH" if gold_chg<-0.5 else "FLAT")}
    except: macro["gold"] = {"val":"—","chg":0,"signal":"—"}

    # Crude Oil
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        crude = float(d["meta"]["regularMarketPrice"])
        cl    = [c for c in d["indicators"]["quote"][0]["close"] if c]
        crude_chg = (crude-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        macro["crude"] = {"val": round(crude,2), "chg": round(crude_chg,2),
                           "signal": "INFLATIONARY" if crude>90 else ("ELEVATED" if crude>75 else "LOW")}
    except: macro["crude"] = {"val":"—","chg":0,"signal":"—"}

    # US 10Y Yield
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        yield10 = float(d["meta"]["regularMarketPrice"])
        cl      = [c for c in d["indicators"]["quote"][0]["close"] if c]
        y_chg   = (yield10-cl[-2]) if len(cl)>=2 else 0
        macro["us10y"] = {"val": round(yield10,3), "chg": round(y_chg,3),
                           "signal": "TIGHT" if yield10>4.5 else ("RISING" if y_chg>0 else "EASING")}
    except: macro["us10y"] = {"val":"—","chg":0,"signal":"—"}

    # S&P 500
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d = r.json()["chart"]["result"][0]
        spx = float(d["meta"]["regularMarketPrice"])
        cl  = [c for c in d["indicators"]["quote"][0]["close"] if c]
        spx_chg = (spx-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        macro["spx"] = {"val": round(spx,1), "chg": round(spx_chg,2),
                         "signal": "RISK-ON" if spx_chg>0.5 else ("RISK-OFF" if spx_chg<-0.5 else "NEUTRAL")}
    except: macro["spx"] = {"val":"—","chg":0,"signal":"—"}

    # Nifty Bank
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        d  = r.json()["chart"]["result"][0]
        nf = float(d["meta"]["regularMarketPrice"])
        cl = [c for c in d["indicators"]["quote"][0]["close"] if c]
        nf_chg = (nf-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
        macro["nifty"] = {"val": round(nf,1), "chg": round(nf_chg,2)}
    except: macro["nifty"] = {"val":"—","chg":0}

    # Market regime signal
    vix_val = macro["india_vix"]["val"] if isinstance(macro["india_vix"]["val"], float) else 18
    dxy_val = macro["dxy"]["val"] if isinstance(macro["dxy"]["val"], float) else 103
    crude_val = macro["crude"]["val"] if isinstance(macro["crude"]["val"], float) else 80
    us10y_val = macro["us10y"]["val"] if isinstance(macro["us10y"]["val"], float) else 4.3

    if vix_val < 15 and dxy_val < 104 and crude_val < 90:
        regime = {"label":"RISK-ON 🟢","color":"#00C896","desc":"Low volatility, weak dollar, stable crude — ideal for equity longs"}
    elif vix_val > 22 or crude_val > 95:
        regime = {"label":"RISK-OFF 🔴","color":"#FF4757","desc":"High fear or expensive energy — reduce exposure, hedge"}
    elif dxy_val > 106:
        regime = {"label":"DOLLAR DOMINANCE ⚠️","color":"#F59E0B","desc":"Strong USD headwind for EM equities and commodities"}
    else:
        regime = {"label":"NEUTRAL ⚪","color":"#7C8FAD","desc":"Mixed signals — be selective, stick to strong setups"}

    macro["regime"] = regime

    # RBI Rate (static — updated periodically)
    macro["rbi_rate"] = {"val": 5.25, "note": "Last cut: Dec 2025 (-25bps) | Total cuts 2025: -125bps"}

    return macro

# ── MA Trades ─────────────────────────────────────────────────────────────────
def fetch_ma_trades():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/ma_trades?trade_date=eq.{today}&select=*&order=created_at.desc",
            headers=HDR, timeout=10)
        return r.json() if r.status_code==200 else []
    except: return []

def get_ma_cmp(symbol):
    try:
        r = requests.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=15m&range=1d",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except: return None

# ── P15 Core Build ────────────────────────────────────────────────────────────
def build_p15():
    now    = datetime.now(IST)
    trades = sup("p15_trades"); cr_data = sup("p15_capital")
    cap    = cr_data[0] if cr_data else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
    ot     = [t for t in trades if t.get("status")=="OPEN"]
    cl     = [t for t in trades if t.get("status")=="CLOSED"]
    en=[]; tu=0
    for t in ot:
        p,dl=gcmp(t["symbol"]); p=p or t["entry_price"]
        pnl=(p-t["entry_price"])*t["quantity"]; pct=(p-t["entry_price"])/t["entry_price"]*100
        d=(now.replace(tzinfo=None)-datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        lf=max(0,90-d); pk=t.get("peak_cmp") or p; pkp=(pk-t["entry_price"])/t["entry_price"]*100
        tier=TIERS.get(t["symbol"],2); cfg=HYBRID.get(t["symbol"],{"t":80,"tr":0})
        ton=pkp>=cfg["t"] and cfg["tr"]>0; ts=round(pk*(1-cfg["tr"]/100),2) if ton else None
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
    cr2=""
    for t in sorted(cl,key=lambda x:x.get("exit_date","0"),reverse=True)[:15]:
        pnl2=t.get("pnl",0); pct2=t.get("pnl_pct",0); col="#10B981" if pnl2>=0 else "#EF4444"
        r2=t.get("exit_reason",""); rt="🛑" if "Stop" in r2 else "📉" if "Trail" in r2 else "🎯" if "target" in r2.lower() else "⏰"
        cr2+=f'<tr class="cr"><td><span class="stag">{t["symbol"]}</span></td><td class="mc">{t.get("entry_date","")}</td><td class="mc">{t.get("exit_date","")}</td><td class="mc">₹{t["entry_price"]:.2f}</td><td class="mc">₹{t.get("exit_price",0):.2f}</td><td style="color:{col};font-weight:700">{fi(pnl2,True)}</td><td style="color:{col};font-weight:700">{pct2:+.1f}%</td><td class="mc" style="font-size:11px">{rt} {r2[:35]}</td></tr>'

    # MA strategy data
    ma_all=fetch_ma_trades(); ma_open=[t for t in ma_all if t.get("status")=="OPEN"]; ma_closed=[t for t in ma_all if t.get("status")=="CLOSED"]
    ma_enriched=[]; ma_total_unreal=0
    for t in ma_open:
        cmp2=get_ma_cmp(t["symbol"]) or t["entry_price"]; pnl2=(cmp2-t["entry_price"])*t["quantity"]; pct2=(cmp2-t["entry_price"])/t["entry_price"]*100
        ma_total_unreal+=pnl2; ma_enriched.append({**t,"cmp2":cmp2,"pnl2":pnl2,"pct2":pct2})
    ma_wins=sum(1 for t in ma_closed if (t.get("exit_price",t["entry_price"])-t["entry_price"])>0)
    ma_total_tr=len(ma_closed); ma_wr=ma_wins/ma_total_tr*100 if ma_total_tr>0 else 0
    ma_realised=sum((t.get("exit_price",t["entry_price"])-t["entry_price"])*t["quantity"] for t in ma_closed)
    ma_total_pnl=ma_realised+ma_total_unreal
    run2=0; ma_equity=[]
    for t in sorted(ma_closed,key=lambda x:x.get("exit_time","00:00")):
        run2+=(t.get("exit_price",t["entry_price"])-t["entry_price"])*t["quantity"]; ma_equity.append(round(run2,2))
    ma_eq_js=json.dumps(ma_equity if ma_equity else [0])
    ma_td_js=json.dumps([{"sym":t["symbol"],"entry":t["entry_price"],"qty":t["quantity"],
        "cmp":t.get("cmp2",t["entry_price"]),"pnl":round(t.get("pnl2",0),2),
        "pct":round(t.get("pct2",0),2)} for t in ma_enriched])

    return {
        "now":now,"en":en,"cl":cl,"cap":cap,"tp":tp,"tr":tr,"wr":wr,"ip":ip,
        "tu":tu,"nc":nc,"np":np,"ns":ns,"ncol":ncol,"ms":ms,"mscol":mscol,
        "sd":sd,"ph":ph,"sj":sj,"pj":pj,"syms":syms,"td":td,"cr2":cr2,
        "ma_total_pnl":ma_total_pnl,"ma_wr":ma_wr,"ma_total_tr":ma_total_tr,
        "ma_enriched":ma_enriched,"ma_total_unreal":ma_total_unreal,
        "ma_eq_js":ma_eq_js,"ma_td_js":ma_td_js
    }

# ── VCP Data from Supabase ────────────────────────────────────────────────────
def build_vcp():
    """
    Read VCP signals and trades from Supabase.
    vcp_scanner.py writes here; dashboard just reads.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")

    # ── Signals (today's detections) ──────────────────────────────────────────
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/vcp_signals"
            f"?signal_date=eq.{today}&select=*&order=score.desc",
            headers=HDR, timeout=10)
        all_signals = r.json() if r.status_code == 200 else []
    except:
        all_signals = []

    eq_signals  = [s for s in all_signals if s.get("market","EQUITY") == "EQUITY"]
    com_signals = [s for s in all_signals if s.get("market") == "COMMODITY"]

    # ── Open trades ────────────────────────────────────────────────────────────
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/vcp_trades?status=eq.OPEN&select=*&order=entry_date.desc",
            headers=HDR, timeout=10)
        open_trades = r.json() if r.status_code == 200 else []
    except:
        open_trades = []

    # Enrich open trades with live CMP
    enriched_trades = []
    for t in open_trades:
        try:
            sym = t["symbol"]
            r2  = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS"
                f"?interval=1d&range=2d",
                headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
            cmp = float(r2.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except:
            cmp = t["entry_price"]
        pnl = round((cmp - t["entry_price"]) * t["quantity"], 2)
        pct = round((cmp - t["entry_price"]) / t["entry_price"] * 100, 2)
        enriched_trades.append({**t, "cmp": cmp, "live_pnl": pnl, "live_pct": pct})

    # ── Closed trades (all-time) ───────────────────────────────────────────────
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/vcp_trades"
            f"?status=eq.CLOSED&select=*&order=exit_date.desc&limit=20",
            headers=HDR, timeout=10)
        closed_trades = r.json() if r.status_code == 200 else []
    except:
        closed_trades = []

    # ── Capital ────────────────────────────────────────────────────────────────
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/vcp_capital?select=*&limit=1",
            headers=HDR, timeout=10)
        cap_rows = r.json() if r.status_code == 200 else []
        cap = cap_rows[0] if cap_rows else {
            "initial":300000,"available":300000,"invested":0,
            "total_pnl":0,"total_trades":0,"winning_trades":0
        }
    except:
        cap = {"initial":300000,"available":300000,"invested":0,
               "total_pnl":0,"total_trades":0,"winning_trades":0}

    # Live unrealised P&L
    live_unreal = sum(t["live_pnl"] for t in enriched_trades)
    total_pnl   = round(cap["total_pnl"] + live_unreal, 2)
    ret_pct     = round(total_pnl / cap["initial"] * 100, 2) if cap["initial"] > 0 else 0
    wr          = round(cap["winning_trades"] / cap["total_trades"] * 100, 1) if cap["total_trades"] > 0 else 0
    ip          = round(min(100, cap["invested"] / cap["initial"] * 100), 1) if cap["initial"] > 0 else 0

    # P&L curve from closed trades
    ph2 = []; run = 0
    for t in sorted(closed_trades, key=lambda x: x.get("exit_date","0")):
        run += t.get("pnl", 0)
        ph2.append(round(run, 2))

    return {
        "eq_signals":      eq_signals,
        "com_signals":     com_signals,
        "open_trades":     enriched_trades,
        "closed_trades":   closed_trades,
        "cap":             cap,
        "live_unreal":     live_unreal,
        "total_pnl":       total_pnl,
        "ret_pct":         ret_pct,
        "wr":              wr,
        "ip":              ip,
        "ph2":             ph2,
        "scanner_active":  len(all_signals) > 0,  # True if scanner ran today
    }

# ── Build HTML ────────────────────────────────────────────────────────────────
def build():
    now = datetime.now(IST)
    p15  = build_p15()
    vcp  = build_vcp()
    macro= fetch_macro()

    # Shorthand
    en=p15["en"]; cl=p15["cl"]; cap=p15["cap"]
    tp=p15["tp"]; tr=p15["tr"]; wr=p15["wr"]
    tu=p15["tu"]; ip=p15["ip"]
    nc=p15["nc"]; ns=p15["ns"]; ncol=p15["ncol"]
    ms=p15["ms"]; mscol=p15["mscol"]
    sj=p15["sj"]; pj=p15["pj"]; syms=p15["syms"]; td=p15["td"]; cr2=p15["cr2"]

    # VCP signal cards (equity) — reads from Supabase vcp_signals
    def score_bar(s, mx=8):
        pct = s/mx*100
        col = "#00C896" if s>=6 else ("#F59E0B" if s>=4 else "#FF4757")
        return f'<div class="sbar-wrap"><div class="sbar-fill" style="width:{pct:.0f}%;background:{col}"></div></div><span class="sbar-val" style="color:{col}">{s}/{mx}</span>'

    eq_cards=""
    for sig in vcp["eq_signals"]:
        bc="#00C896" if sig.get("stage")=="BREAKOUT" else "#F59E0B"
        stage_icon="🚀" if sig.get("stage")=="BREAKOUT" else "🔍"
        try:
            c_pcts = json.loads(sig.get("c_pcts","[]")) if isinstance(sig.get("c_pcts"), str) else (sig.get("c_pcts") or [])
            contr_str = " → ".join([f"{p:.1f}%" for p in c_pcts])
        except:
            contr_str = "—"
        acted = sig.get("acted_upon", False)
        eq_cards+=f"""<div class="vcp-card {'vcp-traded' if acted else ''}">
  <div class="vcp-card-top">
    <div>
      <div class="vcp-sym">{sig['symbol']} {' <span class="traded-tag">📂 TRADED</span>' if acted else ''}</div>
      <div class="vcp-sector">{sig.get('sector','—')}</div>
    </div>
    <div class="vcp-badge" style="background:{'rgba(0,200,150,0.15)' if sig.get('stage')=='BREAKOUT' else 'rgba(245,166,35,0.12)'};color:{bc};border-color:{bc}30">{stage_icon} {sig.get('stage','—')}</div>
  </div>
  <div class="vcp-metrics">
    <div class="vcp-m"><span>CMP</span><b>₹{float(sig.get('cmp',0)):.2f}</b></div>
    <div class="vcp-m"><span>Pivot</span><b style="color:#4A9EFF">₹{float(sig.get('pivot',0)):.2f}</b></div>
    <div class="vcp-m"><span>SL</span><b style="color:#FF4757">₹{float(sig.get('sl_price',0)):.2f}</b></div>
    <div class="vcp-m"><span>T1</span><b style="color:#00C896">₹{float(sig.get('target1',0)):.2f}</b></div>
  </div>
  <div class="vcp-contractions">Contractions: <span style="color:#F59E0B">{contr_str}</span></div>
  <div class="vcp-score-row">Score: {score_bar(sig.get('score',0))} {'💧 Vol Dry' if sig.get('vol_dry') else ''} {'📈 Above MA50' if sig.get('above_ma50') else ''}</div>
  <div class="vcp-time">Detected: {str(sig.get('signal_time',''))[:5]}</div>
</div>"""

    com_cards=""
    for sig in vcp["com_signals"]:
        bc="#00C896" if sig.get("stage")=="BREAKOUT" else "#F59E0B"
        stage_icon="🚀" if sig.get("stage")=="BREAKOUT" else "🔍"
        try:
            c_pcts    = json.loads(sig.get("c_pcts","[]")) if isinstance(sig.get("c_pcts"), str) else (sig.get("c_pcts") or [])
            contr_str = " → ".join([f"{p:.1f}%" for p in c_pcts])
        except:
            contr_str = "—"
        com_cards+=f"""<div class="vcp-card vcp-com">
  <div class="vcp-card-top">
    <div>
      <div class="vcp-sym">{sig['symbol']} <span style="font-size:10px;color:#A855F7">MCX</span></div>
      <div class="vcp-sector">{sig.get('sector','—')} · Options Play</div>
    </div>
    <div class="vcp-badge" style="background:rgba(168,85,247,0.12);color:#A855F7;border-color:#A855F730">{stage_icon} {sig.get('stage','—')}</div>
  </div>
  <div class="vcp-metrics">
    <div class="vcp-m"><span>CMP</span><b>₹{float(sig.get('cmp',0)):.0f}</b></div>
    <div class="vcp-m"><span>Pivot</span><b style="color:#4A9EFF">₹{float(sig.get('pivot',0)):.0f}</b></div>
    <div class="vcp-m"><span>SL</span><b style="color:#FF4757">₹{float(sig.get('sl_price',0)):.0f}</b></div>
    <div class="vcp-m"><span>T1</span><b style="color:#00C896">₹{float(sig.get('target1',0)):.0f}</b></div>
  </div>
  <div class="vcp-contractions">Contractions: <span style="color:#F59E0B">{contr_str}</span></div>
  <div class="vcp-opt-guide">
    <span class="opt-tag">Buy ATM Call</span>
    <span class="opt-tag">15-21 days expiry</span>
    <span class="opt-tag">Low IV entry</span>
  </div>
  <div class="vcp-score-row">Score: {score_bar(sig.get('score',0))} {'💧 Vol Dry' if sig.get('vol_dry') else ''}</div>
</div>"""

    # VCP Open Trades table rows
    vcp_open_rows = ""
    for t in vcp["open_trades"]:
        pnl  = t.get("live_pnl", 0)
        pct  = t.get("live_pct", 0)
        col  = "#00C896" if pnl >= 0 else "#FF4757"
        cmp  = t.get("cmp", t["entry_price"])
        try:
            entry_dt = datetime.strptime(t["entry_date"], "%Y-%m-%d")
            hold_days = (datetime.now() - entry_dt).days
        except:
            hold_days = 0
        trail = "🔄" if t.get("t1_hit") else ""
        vcp_open_rows += f"""<tr class="pos-row">
  <td><div class="psym"><div class="pdot" style="background:#4A9EFF"></div>
    <div><div class="psn">{t['symbol']}</div>
    <div class="pss">{t.get('sector','—')} · Score {t.get('score',0)}/8</div></div></div></td>
  <td class="mc">{t.get('entry_date','')}</td>
  <td style="font-family:monospace;font-size:12px">₹{float(t['entry_price']):.2f}</td>
  <td class="pcmp" id="vcmp_{t['symbol']}">₹{cmp:.2f}</td>
  <td style="color:{col};font-weight:700;font-family:monospace" id="vpnl_{t['symbol']}">{fi(pnl,True)}</td>
  <td><span class="ppct {'pos' if pct>=0 else 'neg'}" id="vpct_{t['symbol']}">{pct:+.2f}%</span></td>
  <td style="font-family:monospace;font-size:11px;color:#FF4757">₹{float(t.get('sl_price',0)):.2f}</td>
  <td style="font-family:monospace;font-size:11px;color:#00C896">₹{float(t.get('target1',0)):.2f}</td>
  <td class="mc">{hold_days}d / 30d</td>
  <td>{trail} {'<span style="color:#F59E0B;font-size:11px">T1 HIT</span>' if t.get('t1_hit') else '<span style="color:#00C896;font-size:11px">HOLD</span>'}</td>
</tr>"""

    # VCP Closed Trades table rows
    vcp_closed_rows = ""
    for t in vcp["closed_trades"][:15]:
        pnl  = t.get("pnl", 0)
        pct  = t.get("pnl_pct", 0)
        col  = "#00C896" if pnl >= 0 else "#FF4757"
        r2   = t.get("exit_reason","")
        icon = "🛑" if "Stop" in r2 else ("🔄" if "Trail" in r2 else ("🎯" if "Target" in r2 else "⏰"))
        vcp_closed_rows += f"""<tr class="cr">
  <td><span class="stag">{t['symbol']}</span></td>
  <td class="mc">{t.get('entry_date','')}</td>
  <td class="mc">{t.get('exit_date','')}</td>
  <td class="mc">₹{float(t['entry_price']):.2f}</td>
  <td class="mc">₹{float(t.get('exit_price',0)):.2f}</td>
  <td style="color:{col};font-weight:700">{fi(pnl,True)}</td>
  <td style="color:{col};font-weight:700">{float(pct):+.1f}%</td>
  <td class="mc" style="font-size:10px">{icon} {r2[:30]}</td>
  <td class="mc">{t.get('score',0)}/8</td>
</tr>"""

    scanner_status = (
        '<span style="color:#00C896">● ACTIVE TODAY</span>'
        if vcp["scanner_active"] else
        '<span style="color:#FF4757">● NOT RUN TODAY — start vcp_scanner.py</span>'
    )

    if not vcp["eq_signals"] and not vcp["com_signals"]:
        eq_cards=f'<div class="vcp-empty">📡 Scanner status: {scanner_status}<br><br>No signals yet today. Run <b>vcp_scanner.py</b> on your PC to start scanning. Signals will appear here automatically.</div>'

    # Macro signal cards
    def sig_chip(label, val, chg, signal, col_map, unit="", chg_unit=""):
        col = col_map.get(signal, "#7C8FAD")
        arrow = "▲" if (chg if isinstance(chg,float) else 0) > 0 else "▼"
        chg_col = "#00C896" if (chg if isinstance(chg,float) else 0) > 0 else "#FF4757"
        return f"""<div class="mac-chip">
  <div class="mac-chip-lbl">{label}</div>
  <div class="mac-chip-val">{val}{unit}</div>
  <div class="mac-chip-chg" style="color:{chg_col}">{arrow} {abs(chg) if isinstance(chg,float) else '—'}{chg_unit}</div>
  <div class="mac-chip-sig" style="color:{col};border-color:{col}30;background:{col}12">{signal}</div>
</div>"""

    regime = macro["regime"]
    rbi    = macro["rbi_rate"]

    mac_html = f"""
<div class="mac-regime" style="border-color:{regime['color']}30;background:{regime['color']}08">
  <div class="mac-regime-label" style="color:{regime['color']}">{regime['label']}</div>
  <div class="mac-regime-desc">{regime['desc']}</div>
</div>
<div class="mac-grid">
  {sig_chip("INDIA VIX", macro['india_vix']['val'], macro['india_vix']['chg'], macro['india_vix']['signal'],
     {"FEAR":"#FF4757","CAUTION":"#F59E0B","CALM":"#00C896","—":"#7C8FAD"})}
  {sig_chip("DXY", macro['dxy']['val'], macro['dxy']['chg'], macro['dxy']['signal'],
     {"STRONG$":"#FF4757","NEUTRAL":"#F59E0B","WEAK$":"#00C896","—":"#7C8FAD"}, chg_unit="%")}
  {sig_chip("USD/INR", macro['usdinr']['val'], macro['usdinr']['chg'], macro['usdinr']['signal'],
     {"WEAK₹":"#FF4757","STABLE":"#F59E0B","STRONG₹":"#00C896","—":"#7C8FAD"})}
  {sig_chip("GOLD (COMEX)", macro['gold']['val'], macro['gold']['chg'], macro['gold']['signal'],
     {"BULLISH":"#00C896","BEARISH":"#FF4757","FLAT":"#F59E0B","—":"#7C8FAD"}, unit="$", chg_unit="%")}
  {sig_chip("CRUDE OIL", macro['crude']['val'], macro['crude']['chg'], macro['crude']['signal'],
     {"INFLATIONARY":"#FF4757","ELEVATED":"#F59E0B","LOW":"#00C896","—":"#7C8FAD"}, unit="$", chg_unit="%")}
  {sig_chip("US 10Y YIELD", macro['us10y']['val'], macro['us10y']['chg'], macro['us10y']['signal'],
     {"TIGHT":"#FF4757","RISING":"#F59E0B","EASING":"#00C896","—":"#7C8FAD"}, unit="%")}
  {sig_chip("S&P 500", macro['spx']['val'], macro['spx']['chg'], macro['spx']['signal'],
     {"RISK-ON":"#00C896","RISK-OFF":"#FF4757","NEUTRAL":"#F59E0B","—":"#7C8FAD"}, chg_unit="%")}
  {sig_chip("NIFTY 50", macro['nifty']['val'], macro['nifty']['chg'], "INDIA",
     {"INDIA":"#4A9EFF"}, chg_unit="%")}
</div>
<div class="mac-rbi">
  <span class="mac-rbi-label">🏦 RBI Repo Rate</span>
  <span class="mac-rbi-val">{rbi['val']}%</span>
  <span class="mac-rbi-note">{rbi['note']}</span>
</div>
<div class="mac-interpretation">
  <div class="mac-int-title">📊 Trader's Read</div>
  <div class="mac-int-body" id="mac-interp">
    {'VIX below 15 → low fear environment. ' if isinstance(macro['india_vix']['val'],float) and macro['india_vix']['val']<15 else 'Elevated VIX → reduce position sizes. '}
    {'Weak dollar (DXY < 104) supports emerging markets and gold. ' if isinstance(macro['dxy']['val'],float) and macro['dxy']['val']<104 else 'Strong dollar headwind for FIIs and commodities. '}
    {'RBI in rate-cut cycle → positive for rate-sensitive sectors (banks, NBFCs, real estate). ' if rbi['val'] < 6.0 else 'Higher rates → cautious on rate-sensitive sectors. '}
    {'Crude below $90 → positive for India current account and inflation outlook.' if isinstance(macro['crude']['val'],float) and macro['crude']['val']<90 else 'High crude → inflationary pressure, negative for import-heavy sectors.'}
  </div>
</div>"""

    # MA tab rows
    ma_rows = ""
    for t in p15["ma_enriched"]:
        col="#10B981" if t.get("pnl2",0)>=0 else "#EF4444"
        ma_rows+=f'<tr><td><span class="stag">{t["symbol"]}</span></td><td class="mc">₹{t["entry_price"]:.2f}</td><td class="mc" id="ma_cmp_{t["symbol"]}">₹{t.get("cmp2",t["entry_price"]):.2f}</td><td id="ma_pnl_{t["symbol"]}" style="color:{col};font-weight:700;font-family:monospace">{fi(t.get("pnl2",0),True)}</td><td><span id="ma_pct_{t["symbol"]}" class="ppct {"pos" if t.get("pct2",0)>=0 else "neg"}">{t.get("pct2",0):+.2f}%</span></td></tr>'

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
<title>⚡ Power 15 Terminal</title>
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
html{{scroll-behavior:smooth}}
body{{background:var(--bg);font-family:'DM Sans',sans-serif;color:var(--txt);min-height:100vh;overflow-x:hidden}}

/* ── HEADER ── */
.hdr{{position:sticky;top:0;z-index:200;height:56px;background:rgba(2,4,8,0.96);backdrop-filter:blur(20px);border-bottom:1px solid var(--bdr);display:flex;align-items:center;padding:0 16px;gap:10px}}
[data-theme="light"] .hdr{{background:rgba(238,242,249,0.96)}}
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

/* ══ COLLAPSIBLE MODULES ══════════════════════════════════════════════════════ */
.module{{margin:0;border-bottom:1px solid var(--bdr)}}
.module-header{{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 20px;cursor:pointer;user-select:none;
  background:var(--s1);transition:background 0.2s;
  position:sticky;top:88px;z-index:90;
}}
.module-header:hover{{background:var(--s2)}}
.module-header-left{{display:flex;align-items:center;gap:12px}}
.module-icon{{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}}
.mod-p15 .module-icon{{background:linear-gradient(135deg,rgba(245,166,35,0.2),rgba(255,71,87,0.2));border:1px solid rgba(245,166,35,0.3)}}
.mod-vcp .module-icon{{background:linear-gradient(135deg,rgba(74,158,255,0.2),rgba(155,109,255,0.2));border:1px solid rgba(74,158,255,0.3)}}
.mod-mac .module-icon{{background:linear-gradient(135deg,rgba(0,212,255,0.2),rgba(0,200,150,0.2));border:1px solid rgba(0,212,255,0.3)}}
.module-title{{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:1.5px}}
.mod-p15 .module-title{{color:var(--gold)}}
.mod-vcp .module-title{{color:var(--blue)}}
.mod-mac .module-title{{color:var(--cyan)}}
.module-subtitle{{font-size:11px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-top:2px}}
.module-right{{display:flex;align-items:center;gap:10px}}
.module-stats{{display:flex;gap:8px}}
.mstat{{font-family:'JetBrains Mono',monospace;font-size:11px;padding:3px 9px;border-radius:6px;background:var(--s3);border:1px solid var(--bdr);color:var(--sub)}}
.mstat.pos{{color:var(--green);background:rgba(0,200,150,0.06);border-color:rgba(0,200,150,0.2)}}
.mstat.neg{{color:var(--red);background:rgba(255,71,87,0.06);border-color:rgba(255,71,87,0.2)}}
.mstat.highlight{{color:var(--gold);background:rgba(245,166,35,0.06);border-color:rgba(245,166,35,0.2)}}
.chevron{{font-size:16px;color:var(--mut);transition:transform 0.3s ease;flex-shrink:0}}
.module.collapsed .chevron{{transform:rotate(-90deg)}}
.module-body{{overflow:hidden;transition:max-height 0.5s cubic-bezier(0.4,0,0.2,1),opacity 0.3s ease;max-height:5000px;opacity:1}}
.module.collapsed .module-body{{max-height:0;opacity:0}}

/* ══ INNER LAYOUT ════════════════════════════════════════════════════════════ */
.pi{{padding:16px;display:flex;flex-direction:column;gap:14px}}

/* ── CARD ── */
.card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden}}
.card-hdr{{padding:12px 14px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;justify-content:space-between}}
.card-title{{font-size:10px;font-weight:700;color:var(--sub);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;display:flex;align-items:center;gap:7px}}
.card-title::before{{content:'';width:3px;height:11px;background:var(--gold);border-radius:2px;flex-shrink:0}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;background:rgba(245,166,35,0.1);color:var(--gold);border:1px solid rgba(245,166,35,0.2)}}
.upd-dot{{width:5px;height:5px;border-radius:50%;background:var(--green);animation:blink 2s ease infinite}}

/* ── P15 TABLE ── */
.desk-table{{display:block;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:700px}}
.pos-table thead th,.ct thead th{{padding:8px 10px;text-align:left;font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--bdr);background:var(--s2);font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.pos-row td,.cr td{{padding:10px;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;white-space:nowrap;transition:background 0.12s}}
.pos-row:hover td,.cr:hover td{{background:rgba(255,255,255,0.025)}}
.pos-row:last-child td,.cr:last-child td{{border-bottom:none}}
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
.stag{{background:var(--s3);border:1px solid var(--bdr2);padding:2px 7px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700}}
.mc{{color:var(--sub);font-family:'JetBrains Mono',monospace;font-size:11px}}

/* ── CHARTS ── */
.charts-row{{display:grid;grid-template-columns:1fr 1fr 2fr;gap:12px}}
.cc{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:14px}}
.ctitle{{font-size:10px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:12px;display:flex;align-items:center;gap:7px}}
.ctitle::before{{content:'';width:3px;height:10px;background:var(--gold);border-radius:2px;flex-shrink:0}}
.cw{{min-height:160px}}

/* P15 sidebar */
.p15-inner{{display:grid;grid-template-columns:200px 1fr;min-height:300px}}
.sidebar{{background:var(--s1);border-right:1px solid var(--bdr);overflow-y:auto}}
.sb-sec{{padding:14px 12px 8px;border-bottom:1px solid var(--bdr)}}
.sb-lbl{{font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;margin-bottom:10px}}
.sb-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.sb-rl{{font-size:11px;color:var(--sub)}}
.sb-rv{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.capbar{{margin:8px 0 4px}}
.cbt{{height:4px;background:var(--s4);border-radius:2px;overflow:hidden}}
.cbf{{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--green),var(--gold))}}
.cbl{{display:flex;justify-content:space-between;font-size:9px;color:var(--mut);font-family:'JetBrains Mono',monospace;margin-top:4px}}
.sb-grid{{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:10px 12px}}
.sb-stat{{background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:8px 10px}}
.sb-sl{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;font-family:'JetBrains Mono',monospace}}
.sb-sv{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700}}

/* ══ VCP CARDS ════════════════════════════════════════════════════════════════ */
.vcp-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;padding:16px}}
.vcp-card{{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:14px;transition:border-color 0.2s,transform 0.2s}}
.vcp-card:hover{{border-color:var(--bdr2);transform:translateY(-2px)}}
.vcp-com{{border-left:3px solid #A855F7}}
.vcp-card-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}}
.vcp-sym{{font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:1px}}
.vcp-sector{{font-size:10px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-top:2px}}
.vcp-badge{{font-size:10px;font-weight:700;padding:3px 8px;border-radius:6px;border:1px solid;font-family:'JetBrains Mono',monospace}}
.vcp-metrics{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:10px}}
.vcp-m{{background:var(--s3);border-radius:8px;padding:7px 8px}}
.vcp-m span{{font-size:8px;color:var(--mut);text-transform:uppercase;letter-spacing:0.8px;display:block;margin-bottom:3px}}
.vcp-m b{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700}}
.vcp-contractions{{font-size:11px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-bottom:8px}}
.vcp-score-row{{display:flex;align-items:center;gap:10px;font-size:10px;color:var(--sub);font-family:'JetBrains Mono',monospace}}
.sbar-wrap{{width:60px;height:4px;background:var(--s4);border-radius:2px;overflow:hidden;display:inline-block;vertical-align:middle}}
.sbar-fill{{height:100%;border-radius:2px;transition:width 1s ease}}
.sbar-val{{font-size:11px;font-weight:700;margin-left:6px}}
.vcp-opt-guide{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}}
.opt-tag{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;background:rgba(168,85,247,0.1);color:#A855F7;border:1px solid rgba(168,85,247,0.2);font-family:'JetBrains Mono',monospace}}
.vcp-traded{{border-left:3px solid var(--green)}}
.traded-tag{{font-size:9px;font-weight:700;padding:1px 6px;border-radius:4px;background:rgba(0,200,150,0.1);color:var(--green);border:1px solid rgba(0,200,150,0.2);font-family:'JetBrains Mono',monospace;vertical-align:middle}}
.vcp-time{{font-size:9px;color:var(--mut);font-family:'JetBrains Mono',monospace;margin-top:6px}}
.vcp-section-title{{padding:14px 16px 0;font-size:10px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;display:flex;align-items:center;gap:8px}}
.vcp-section-title::before{{content:'';width:3px;height:10px;border-radius:2px;flex-shrink:0}}
.vcp-eq-title::before{{background:var(--blue)}}
.vcp-com-title::before{{background:#A855F7}}

/* ══ MACRO CHIPS ══════════════════════════════════════════════════════════════ */
.mac-regime{{margin:16px;padding:14px 16px;border-radius:12px;border:1px solid;display:flex;align-items:center;gap:14px}}
.mac-regime-label{{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:1px;white-space:nowrap;flex-shrink:0}}
.mac-regime-desc{{font-size:12px;color:var(--sub);line-height:1.5}}
.mac-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;padding:0 16px 16px}}
.mac-chip{{background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:12px 14px}}
.mac-chip-lbl{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:5px}}
.mac-chip-val{{font-family:'Bebas Neue',sans-serif;font-size:24px;letter-spacing:0.5px;line-height:1;margin-bottom:3px}}
.mac-chip-chg{{font-family:'JetBrains Mono',monospace;font-size:10px;margin-bottom:6px}}
.mac-chip-sig{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid;font-family:'JetBrains Mono',monospace;display:inline-block}}
.mac-rbi{{margin:0 16px 16px;padding:12px 16px;background:var(--s2);border:1px solid var(--bdr);border-radius:10px;display:flex;align-items:center;gap:12px}}
.mac-rbi-label{{font-size:11px;color:var(--sub);font-family:'JetBrains Mono',monospace;flex-shrink:0}}
.mac-rbi-val{{font-family:'Bebas Neue',sans-serif;font-size:26px;color:var(--gold);letter-spacing:1px;flex-shrink:0}}
.mac-rbi-note{{font-size:10px;color:var(--sub);font-family:'JetBrains Mono',monospace}}
.mac-interpretation{{margin:0 16px 16px;padding:14px 16px;background:var(--s2);border:1px solid var(--bdr);border-left:3px solid var(--cyan);border-radius:10px}}
.mac-int-title{{font-size:10px;font-weight:700;color:var(--cyan);text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;margin-bottom:8px}}
.mac-int-body{{font-size:12px;color:var(--sub);line-height:1.7}}

/* ── BOTTOM BAR ── */
.update-bar{{display:flex;align-items:center;gap:8px;justify-content:flex-end;padding:10px 20px;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--mut);border-top:1px solid var(--bdr);background:var(--s1)}}
.update-bar span{{color:var(--green)}}
.empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 20px;gap:10px;color:var(--sub);text-align:center}}

/* ── RESPONSIVE ── */
@media(max-width:1024px){{
  .charts-row{{grid-template-columns:1fr 1fr}}
  .p15-inner{{grid-template-columns:1fr}}
  .sidebar{{display:none}}
}}
@media(max-width:768px){{
  .hdr{{height:52px;padding:0 12px}}
  .hdr-name{{font-size:16px}}
  .module-header{{padding:12px 14px;top:84px}}
  .module-title{{font-size:17px}}
  .module-stats .mstat:nth-child(n+3){{display:none}}
  .charts-row{{grid-template-columns:1fr}}
  .mac-grid{{grid-template-columns:repeat(2,1fr)}}
  .mac-regime{{flex-direction:column;align-items:flex-start;gap:6px}}
  .vcp-metrics{{grid-template-columns:1fr 1fr}}
  .mac-rbi{{flex-wrap:wrap}}
  .pi{{padding:10px;gap:10px}}
}}
@media(max-width:390px){{
  .hdr-clk{{display:none}}
  .module-stats{{display:none}}
}}
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
    <div class="pill" style="color:{ncol}">NIFTY {ns}</div>
    <div class="pill" style="color:{mscol}">● {ms}</div>
    <div class="pill" style="color:var(--cyan)">REGIME: {macro['regime']['label']}</div>
  </div>
  <div class="hdr-right">
    <div class="hdr-clk" id="clk">{now.strftime('%H:%M:%S')}</div>
    <button class="tbtn" onclick="refreshPrices()" title="Refresh">↻</button>
    <button class="tbtn" onclick="toggleTheme()">🌓</button>
  </div>
</header>

<!-- TICKER -->
<div class="ticker"><div class="ticker-inner">
  {''.join([f'<span class="ti"><span class="ti-s">{t["symbol"]}</span><span id="tc_{t["symbol"]}" style="color:{"#10B981" if t["pct"]>=0 else "#FF4757"}">{t["pct"]:+.2f}%</span><span id="tp_{t["symbol"]}" style="color:{"#10B981" if t["pnl"]>=0 else "#FF4757"}">{fi(t["pnl"],True)}</span><span class="td">·</span></span>' for t in en]*6) if en else '<span class="ti"><span class="ti-s" style="color:#F5A623">⚡ POWER 15 TERMINAL v6.0</span><span style="color:#7C8FAD"> · VCP + MACRO INTELLIGENCE ACTIVE · </span></span>'*4}
</div></div>

<!-- ══════════════════════════════════════════════════════════════════════════ -->
<!--  MODULE 1 — POWER 15                                                      -->
<!-- ══════════════════════════════════════════════════════════════════════════ -->
<div class="module mod-p15" id="mod-p15">
  <div class="module-header" onclick="toggleModule('mod-p15')">
    <div class="module-header-left">
      <div class="module-icon">⚡</div>
      <div>
        <div class="module-title">Power 15</div>
        <div class="module-subtitle">Swing Bot · RSI Crossover · {len(en)} open positions</div>
      </div>
    </div>
    <div class="module-right">
      <div class="module-stats">
        <div class="mstat {'pos' if tp>=0 else 'neg'}">{fi(tp,True)}</div>
        <div class="mstat highlight">{tr:+.2f}%</div>
        <div class="mstat">WR {wr:.0f}%</div>
      </div>
      <div class="chevron">▾</div>
    </div>
  </div>
  <div class="module-body">
    <div class="p15-inner">
      <!-- Sidebar -->
      <div class="sidebar">
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
      </div>
      <!-- Main -->
      <div class="pi">
        <!-- Live Positions -->
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">Live Positions</div>
            <div style="display:flex;align-items:center;gap:8px"><div class="upd-dot"></div><span id="upd-time" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--sub)">...</span><div class="badge">{len(en)} OPEN</div></div>
          </div>
          {f'''<div class="desk-table"><table class="pos-table">
            <thead><tr><th>Symbol</th><th>Entry</th><th>CMP <span style="color:var(--green);font-size:8px">● LIVE</span></th><th>P&L</th><th>Ret%</th><th>Peak</th><th>Stop Loss</th><th>Days</th><th>Status</th></tr></thead>
            <tbody id="posBody">{''.join([f"""<tr class="pos-row">
              <td><div class="psym"><div class="pdot" style="background:{SCOL.get(t['sector'],'#6B7280')}"></div><div><div class="psn">{t['symbol']}</div><div class="pss">{t['sector']} · T{t['tier']}</div></div></div></td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:12px">₹{t['entry_price']:.2f}</td>
              <td class="pcmp" id="cmp_{t['symbol']}">₹{t['cmp']:.2f}</td>
              <td class="ppnl" id="pnl_{t['symbol']}" style="color:{'var(--green)' if t['pnl']>=0 else 'var(--red)'}">{fi(t['pnl'],True)}</td>
              <td><span class="ppct {'pos' if t['pct']>=0 else 'neg'}" id="pct_{t['symbol']}">{t['pct']:+.2f}%</span></td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gold)">₹{t['peak']:.2f} <span style="font-size:9px;color:var(--sub)">(+{t['pkp']:.1f}%)</span></td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--red)">₹{t['sl_price']:.2f}</td>
              <td><div class="pmini"><div class="pmini-f" style="width:{min(100,t['days']/90*100):.0f}%;background:{'#FF4757' if t['left']<=10 else '#F5A623' if t['left']<=30 else '#00C896'}"></div></div><div style="font-size:9px;color:var(--sub);font-family:'JetBrains Mono',monospace;margin-top:3px">{t['days']}d · {t['left']}d left</div></td>
              <td>{'<span class="trail-t">🔄 TRAIL</span>' if t['ton'] else ('<span style="color:var(--green);font-size:11px">HOLD</span>')}</td>
            </tr>""" for t in en])}</tbody>
          </table></div>''' if en else '<div class="empty"><div style="font-size:36px">🌙</div><div>No open positions</div><div style="font-size:12px;color:var(--sub)">Signals fire at 3:25 PM weekdays</div></div>'}
        </div>

        <!-- Charts -->
        <div class="charts-row">
          <div class="cc"><div class="ctitle">P&L Curve</div><div class="cw"><canvas id="lineChart"></canvas></div></div>
          <div class="cc"><div class="ctitle">Sector Mix</div><div class="cw">{f'<canvas id="pieChart"></canvas>' if p15["sd"] else '<div class="empty" style="padding:20px"><div style="font-size:24px">📊</div></div>'}</div></div>
          <div class="cc"><div class="ctitle">Stock Returns</div><div class="cw">{f'<canvas id="barChart"></canvas>' if en else '<div class="empty" style="padding:20px"><div style="font-size:24px">📈</div></div>'}</div></div>
        </div>

        <!-- MA Strategy sub-section -->
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">MA Strategy · 9/21/50 EMA · Intraday</div>
            <div style="display:flex;gap:8px"><span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{'var(--green)' if p15['ma_total_pnl']>=0 else 'var(--red)'}">P&L {fi(p15['ma_total_pnl'],True)}</span><div class="badge">{p15['ma_total_tr']} trades</div></div>
          </div>
          {f'''<div class="desk-table"><table class="ct">
            <thead><tr><th>Symbol</th><th>Entry</th><th>CMP</th><th>P&L</th><th>Ret%</th></tr></thead>
            <tbody>{ma_rows}</tbody></table></div>''' if p15["ma_enriched"] else '<div class="empty" style="padding:24px"><div>No MA trades today</div><div style="font-size:11px;color:var(--sub)">Runs 9:30 AM–3:15 PM on ma_strategy.py</div></div>'}
        </div>

        <!-- Closed trades -->
        {f'''<div class="card">
          <div class="card-hdr"><div class="card-title">Trade History</div><div class="badge">LAST {min(15,len(cl))}</div></div>
          <div style="overflow-x:auto"><table class="ct">
            <thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy</th><th>Sell</th><th>P&L</th><th>Ret%</th><th>Reason</th></tr></thead>
            <tbody>{cr2}</tbody></table></div></div>''' if cl else ''}
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════ -->
<!--  MODULE 2 — VCP STRATEGY                                                  -->
<!-- ══════════════════════════════════════════════════════════════════════════ -->
<div class="module mod-vcp collapsed" id="mod-vcp">
  <div class="module-header" onclick="toggleModule('mod-vcp')">
    <div class="module-header-left">
      <div class="module-icon">📐</div>
      <div>
        <div class="module-title">VCP Strategy</div>
        <div class="module-subtitle">Volatility Contraction · Equity + MCX Commodities · Options</div>
      </div>
    </div>
    <div class="module-right">
      <div class="module-stats">
        <div class="mstat highlight">{len(vcp['eq_signals'])} EQ signals</div>
        <div class="mstat" style="color:var(--purple)">{len(vcp['com_signals'])} COM signals</div>
      </div>
      <div class="chevron">▾</div>
    </div>
  </div>
  <div class="module-body">
    <div class="pi">
      <!-- VCP KPI Stats Row -->
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;padding:0 0 4px">
        <div class="sb-stat"><div class="sb-sl">Total P&L</div><div class="sb-sv" style="color:{'var(--green)' if vcp['total_pnl']>=0 else 'var(--red)'}">{ fi(vcp['total_pnl'],True)}</div></div>
        <div class="sb-stat"><div class="sb-sl">Return</div><div class="sb-sv" style="color:{'var(--green)' if vcp['ret_pct']>=0 else 'var(--red)'}">{vcp['ret_pct']:+.2f}%</div></div>
        <div class="sb-stat"><div class="sb-sl">Available</div><div class="sb-sv" style="color:var(--blue)">{fi(vcp['cap']['available'])}</div></div>
        <div class="sb-stat"><div class="sb-sl">Invested</div><div class="sb-sv" style="color:var(--gold)">{fi(vcp['cap']['invested'])}</div></div>
        <div class="sb-stat"><div class="sb-sl">Win Rate</div><div class="sb-sv" style="color:var(--purple)">{vcp['wr']:.0f}%</div></div>
        <div class="sb-stat"><div class="sb-sl">Trades</div><div class="sb-sv" style="color:var(--cyan)">{vcp['cap']['total_trades']}</div></div>
        <div class="sb-stat"><div class="sb-sl">Unrealised</div><div class="sb-sv" style="color:{'var(--green)' if vcp['live_unreal']>=0 else 'var(--red)'}" id="vcp-unreal">{fi(vcp['live_unreal'],True)}</div></div>
        <div class="sb-stat"><div class="sb-sl">Scanner</div><div class="sb-sv" style="font-size:10px">{ '🟢 ON' if vcp['scanner_active'] else '🔴 OFF'}</div></div>
      </div>

      <!-- VCP Info Banner -->
      <div style="background:var(--s2);border:1px solid rgba(74,158,255,0.2);border-left:3px solid var(--blue);border-radius:10px;padding:12px 16px;font-size:12px;color:var(--sub);line-height:1.6">
        <span style="color:var(--blue);font-weight:700;font-family:'JetBrains Mono',monospace">VCP RULES: </span>
        3 contracting pullbacks · Each smaller than previous · Volume dries up on C3 · Breakout on 1.5x vol · Score ≥5 = high conviction
        &nbsp;·&nbsp; Scanner: {scanner_status}
      </div>

      <!-- Equity VCP Signals -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">Equity VCP Signals · NSE Daily</div>
          <div class="badge" style="color:var(--blue);border-color:rgba(74,158,255,0.3);background:rgba(74,158,255,0.08)">{len(vcp['eq_signals'])} SIGNALS</div>
        </div>
        <div class="vcp-grid" id="vcpEqGrid">
          {eq_cards}
        </div>
      </div>

      <!-- Commodity VCP Signals -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">Commodity VCP · MCX Gold & Silver · Options Setup</div>
          <div class="badge" style="color:#A855F7;border-color:rgba(168,85,247,0.3);background:rgba(168,85,247,0.08)">{len(vcp['com_signals'])} SIGNALS</div>
        </div>
        <div class="vcp-grid">
          {com_cards if vcp['com_signals'] else '<div class="vcp-empty">No commodity VCP signals today.</div>'}
        </div>
      </div>

      <!-- VCP Open Trades -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">VCP Open Trades · Paper Trading</div>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="upd-dot"></div>
            <div class="badge" style="color:var(--blue)">{len(vcp['open_trades'])} OPEN</div>
          </div>
        </div>
        {f'''<div class="desk-table"><table class="pos-table">
          <thead><tr>
            <th>Symbol</th><th>Date</th><th>Entry</th>
            <th>CMP <span style="color:var(--green);font-size:8px">● LIVE</span></th>
            <th>P&L</th><th>Ret%</th><th>SL</th><th>T1</th><th>Hold</th><th>Status</th>
          </tr></thead>
          <tbody id="vcpOpenBody">{vcp_open_rows}</tbody>
        </table></div>''' if vcp['open_trades'] else
        '<div class="empty" style="padding:30px"><div style="font-size:28px">📂</div><div>No open VCP trades</div><div style="font-size:11px;color:var(--sub)">Breakout signals auto-open paper trades</div></div>'}
      </div>

      <!-- VCP P&L Curve + Closed Trades -->
      <div class="charts-row" style="grid-template-columns:1fr 2fr">
        <div class="cc">
          <div class="ctitle">VCP P&L Curve</div>
          <div class="cw"><canvas id="vcpLineChart"></canvas></div>
        </div>
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">VCP Trade History</div>
            <div class="badge">LAST {min(15, len(vcp['closed_trades']))}</div>
          </div>
          {f'''<div style="overflow-x:auto"><table class="ct">
            <thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Buy</th><th>Sell</th><th>P&L</th><th>Ret%</th><th>Reason</th><th>Score</th></tr></thead>
            <tbody>{vcp_closed_rows}</tbody>
          </table></div>''' if vcp['closed_trades'] else
          '<div class="empty" style="padding:30px"><div>No closed trades yet</div><div style="font-size:11px;color:var(--sub)">History will appear here</div></div>'}
        </div>
      </div>

      <!-- VCP Universe Info -->
      <div style="background:var(--s2);border:1px solid var(--bdr);border-radius:10px;padding:14px 16px">
        <div style="font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;margin-bottom:10px">EQUITY UNIVERSE (20 STOCKS)</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">
          {''.join([f'<span style="font-family:monospace;font-size:10px;padding:3px 8px;border-radius:5px;background:var(--s3);color:var(--sub);border:1px solid var(--bdr)">{s}</span>' for s in VCP_EQ_STOCKS.keys()])}
        </div>
        <div style="font-size:9px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1.5px;font-family:'JetBrains Mono',monospace;margin:12px 0 8px">COMMODITY UNIVERSE (MCX OPTIONS)</div>
        <div style="display:flex;gap:6px">
          <span style="font-size:10px;padding:3px 8px;border-radius:5px;background:rgba(168,85,247,0.1);color:#A855F7;border:1px solid rgba(168,85,247,0.2);font-family:monospace">GOLD</span>
          <span style="font-size:10px;padding:3px 8px;border-radius:5px;background:rgba(168,85,247,0.1);color:#A855F7;border:1px solid rgba(168,85,247,0.2);font-family:monospace">SILVER</span>
          <span style="font-size:10px;padding:3px 8px;border-radius:5px;background:rgba(168,85,247,0.1);color:#A855F7;border:1px solid rgba(168,85,247,0.2);font-family:monospace">CRUDE OIL</span>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════ -->
<!--  MODULE 3 — MACRO INTELLIGENCE                                            -->
<!-- ══════════════════════════════════════════════════════════════════════════ -->
<div class="module mod-mac collapsed" id="mod-mac">
  <div class="module-header" onclick="toggleModule('mod-mac')">
    <div class="module-header-left">
      <div class="module-icon">🌐</div>
      <div>
        <div class="module-title">Macro Intelligence</div>
        <div class="module-subtitle">VIX · DXY · INR · Crude · Rates · Global Signals</div>
      </div>
    </div>
    <div class="module-right">
      <div class="module-stats">
        <div class="mstat" style="color:{macro['regime']['color']}">{macro['regime']['label'].split()[0]}</div>
        <div class="mstat">VIX {macro['india_vix']['val']}</div>
        <div class="mstat">RBI {macro['rbi_rate']['val']}%</div>
      </div>
      <div class="chevron">▾</div>
    </div>
  </div>
  <div class="module-body">
    {mac_html}
  </div>
</div>

<!-- BOTTOM BAR -->
<div class="update-bar">
  <div class="upd-dot"></div>
  <span>Prices refresh every 15s</span> ·
  <span>Last: <span id="last-upd-t">—</span></span> ·
  <span>⚡ Power 15 Terminal v6.0</span>
</div>

<script>
const SYMS={syms}, TD={td}, SD={sj}, PH={pj}, WR={round(wr,1)};
const MA_EQ={p15['ma_eq_js']}, MA_TD={p15['ma_td_js']};
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

// Collapsible modules
function toggleModule(id){{
  const m=document.getElementById(id);
  m.classList.toggle('collapsed');
  // Save state
  const states=JSON.parse(localStorage.getItem('p15_modules')||'{{}}');
  states[id]=m.classList.contains('collapsed');
  localStorage.setItem('p15_modules',JSON.stringify(states));
}}
(()=>{{
  const states=JSON.parse(localStorage.getItem('p15_modules')||'{{}}');
  Object.entries(states).forEach(([id,collapsed])=>{{
    const m=document.getElementById(id);
    if(m){{
      if(collapsed)m.classList.add('collapsed');
      else m.classList.remove('collapsed');
    }}
  }});
}})();

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
      const old=prev[t.sym]||cmp;
      totalUnreal+=pnl;
      const ce=document.getElementById(`cmp_${{t.sym}}`);
      if(ce){{ce.textContent='₹'+cmp.toFixed(2);ce.className='pcmp '+(cmp!==old?(cmp>old?'flash-g':'flash-r'):'');setTimeout(()=>{{if(ce)ce.className='pcmp'}},700);}}
      const pe=document.getElementById(`pnl_${{t.sym}}`);if(pe){{pe.textContent=fi(pnl,true);pe.style.color=pnl>=0?'var(--green)':'var(--red)';}}
      const pce=document.getElementById(`pct_${{t.sym}}`);if(pce){{pce.textContent=pnlPct.toFixed(2)+'%';pce.className='ppct '+(pnlPct>=0?'pos':'neg');}}
      const tc=document.getElementById(`tc_${{t.sym}}`);const tp2=document.getElementById(`tp_${{t.sym}}`);
      if(tc){{const dc=(cmp-(m.previousClose||cmp))/(m.previousClose||1)*100;tc.textContent=dc.toFixed(2)+'%';tc.style.color=dc>=0?'#00C896':'#FF4757';}}
      if(tp2){{tp2.textContent=fi(pnl,true);tp2.style.color=pnl>=0?'#00C896':'#FF4757';}}
      prev[t.sym]=cmp;
    }}catch(e){{}}
  }}
  ['sb-unreal'].forEach(id=>{{const el=document.getElementById(id);if(el){{el.textContent=fi(totalUnreal,true);el.style.color=totalUnreal>=0?'var(--green)':'var(--red)';}}}});
  ['upd-time','last-upd-t'].forEach(id=>{{const el=document.getElementById(id);if(el)el.textContent=ts;}});
}}

// MA refresh
async function refreshMA(){{
  for(const t of MA_TD){{
    try{{
      const r=await fetch('https://query2.finance.yahoo.com/v8/finance/chart/'+t.sym+'.NS?interval=15m&range=1d',{{headers:{{'User-Agent':'Mozilla/5.0'}}}});
      const d=await r.json();const cmp=parseFloat(d.chart.result[0].meta.regularMarketPrice);
      const pnl=(cmp-t.entry)*t.qty;const pct=(cmp-t.entry)/t.entry*100;
      const ce=document.getElementById('ma_cmp_'+t.sym);const pe=document.getElementById('ma_pnl_'+t.sym);const pce=document.getElementById('ma_pct_'+t.sym);
      if(ce)ce.textContent='₹'+cmp.toFixed(2);
      if(pe){{pe.textContent=fi(pnl,true);pe.style.color=pnl>=0?'var(--green)':'var(--red)';}}
      if(pce){{pce.textContent=pct.toFixed(2)+'%';pce.className='ppct '+(pct>=0?'pos':'neg');}}
    }}catch(e){{}}
  }}
}}

refreshPrices(); setInterval(refreshPrices,15000);
if(MA_TD.length>0){{refreshMA();setInterval(refreshMA,15000);}}

// Charts
Chart.defaults.color='#3D4F6A'; Chart.defaults.borderColor='rgba(255,255,255,0.05)';
Chart.defaults.font.family="'DM Sans',sans-serif";
const lc=document.getElementById('lineChart');
if(lc){{
  const isP=PH[PH.length-1]>=0,g=lc.getContext('2d').createLinearGradient(0,0,0,150);
  isP?(g.addColorStop(0,'rgba(0,200,150,0.25)'),g.addColorStop(1,'rgba(0,200,150,0)')):(g.addColorStop(0,'rgba(255,71,87,0.25)'),g.addColorStop(1,'rgba(255,71,87,0)'));
  new Chart(lc,{{type:'line',data:{{labels:PH.map((_,i)=>'T'+(i+1)),datasets:[{{data:PH,borderColor:isP?'#00C896':'#FF4757',backgroundColor:g,fill:true,tension:0.45,pointRadius:PH.length>20?0:3,pointHoverRadius:7,borderWidth:2}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}},backgroundColor:'#080D18',borderColor:'rgba(245,166,35,0.3)',borderWidth:1,titleColor:'#F5A623',bodyColor:'#E8F0FF',padding:10,cornerRadius:8}}}},scales:{{x:{{ticks:{{color:'#3D4F6A',maxTicksLimit:6}},grid:{{color:'rgba(255,255,255,0.03)'}}}},y:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}} }}}});
}}
if(SD.length&&document.getElementById('pieChart')){{
  new Chart(document.getElementById('pieChart'),{{type:'doughnut',data:{{labels:SD.map(d=>d.l),datasets:[{{data:SD.map(d=>d.v),backgroundColor:SD.map(d=>d.c),borderWidth:3,borderColor:'#080D18',hoverOffset:8}}]}},options:{{cutout:'70%',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#7C8FAD',padding:6,font:{{size:9}},boxWidth:8}}}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw)}}}}}}}} }});
}}
if(TD.length&&document.getElementById('barChart')){{
  new Chart(document.getElementById('barChart'),{{type:'bar',data:{{labels:TD.map(t=>t.sym),datasets:[{{data:TD.map(t=>{{const c=prev[t.sym]||t.entry;return(c-t.entry)*t.qty}}),backgroundColor:TD.map(t=>{{const c=prev[t.sym]||t.entry;return c>=t.entry?'rgba(0,200,150,0.65)':'rgba(255,71,87,0.65)'}}),borderColor:TD.map(t=>{{const c=prev[t.sym]||t.entry;return c>=t.entry?'#00C896':'#FF4757'}}),borderWidth:1,borderRadius:5}}]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}},y:{{grid:{{display:false}},ticks:{{color:'#E8F0FF',font:{{weight:'700',size:10}}}}}}}}}} }});
}}

// VCP P&L Curve
const VCP_PH={json.dumps(vcp['ph2'])};
const vcplc=document.getElementById('vcpLineChart');
if(vcplc&&VCP_PH.length>1){{
  const isP=VCP_PH[VCP_PH.length-1]>=0;
  const vg=vcplc.getContext('2d').createLinearGradient(0,0,0,150);
  isP?(vg.addColorStop(0,'rgba(74,158,255,0.25)'),vg.addColorStop(1,'rgba(74,158,255,0)'))
     :(vg.addColorStop(0,'rgba(255,71,87,0.25)'),vg.addColorStop(1,'rgba(255,71,87,0)'));
  new Chart(vcplc,{{type:'line',data:{{
    labels:VCP_PH.map((_,i)=>'T'+(i+1)),
    datasets:[{{data:VCP_PH,borderColor:isP?'#4A9EFF':'#FF4757',backgroundColor:vg,
      fill:true,tension:0.45,pointRadius:VCP_PH.length>15?0:4,pointHoverRadius:7,
      pointBackgroundColor:isP?'#4A9EFF':'#FF4757',
      pointBorderColor:'#020408',pointBorderWidth:2,borderWidth:2}}]
  }},options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>' '+fi(c.raw,true)}},
      backgroundColor:'#080D18',borderColor:'rgba(74,158,255,0.3)',borderWidth:1,
      titleColor:'#4A9EFF',bodyColor:'#E8F0FF',padding:10,cornerRadius:8}}}},
    scales:{{x:{{ticks:{{color:'#3D4F6A',maxTicksLimit:6}},grid:{{color:'rgba(255,255,255,0.03)'}}}},
             y:{{ticks:{{color:'#3D4F6A',callback:v=>fi(v)}},grid:{{color:'rgba(255,255,255,0.04)'}}}}}}
  }}}});
}}

// VCP open trades live CMP refresh
const VCP_OPEN_TD={json.dumps([{{"sym":t["symbol"],"entry":float(t["entry_price"]),"qty":t["quantity"]}} for t in vcp["open_trades"]])};
async function refreshVCPPrices(){{
  let totalUnreal=0;
  for(const t of VCP_OPEN_TD){{
    try{{
      const r=await fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+t.sym+'.NS',{{headers:{{'User-Agent':'Mozilla/5.0'}}}});
      const d=await r.json();
      const cmp=parseFloat(d.chart.result[0].meta.regularMarketPrice);
      const pnl=(cmp-t.entry)*t.qty;
      const pct=(cmp-t.entry)/t.entry*100;
      totalUnreal+=pnl;
      const ce=document.getElementById('vcmp_'+t.sym);
      const pe=document.getElementById('vpnl_'+t.sym);
      const pce=document.getElementById('vpct_'+t.sym);
      if(ce)ce.textContent='₹'+cmp.toFixed(2);
      if(pe){{pe.textContent=fi(pnl,true);pe.style.color=pnl>=0?'var(--green)':'var(--red)';}}
      if(pce){{pce.textContent=pct.toFixed(2)+'%';pce.className='ppct '+(pct>=0?'pos':'neg');}}
    }}catch(e){{}}
  }}
  const ue=document.getElementById('vcp-unreal');
  if(ue){{ue.textContent=fi(totalUnreal,true);ue.style.color=totalUnreal>=0?'var(--green)':'var(--red)';}}
}}
if(VCP_OPEN_TD.length>0){{refreshVCPPrices();setInterval(refreshVCPPrices,15000);}}
</script>
</body></html>"""

# ── Server ────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]

        # ── /health — instant response for Render health checks ──────────────
        if path in ('/health', '/ping', '/favicon.ico'):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ── /manifest.json ────────────────────────────────────────────────────
        if path == '/manifest.json':
            manifest = json.dumps({
                "name": "Power 15 Terminal", "short_name": "Power15",
                "description": "VCP + Macro + Swing Trading Dashboard",
                "start_url": "/", "display": "standalone",
                "background_color": "#020408", "theme_color": "#F5A623",
                "icons": [
                    {"src": "https://img.icons8.com/emoji/96/lightning-emoji.png",  "sizes": "96x96",  "type": "image/png"},
                    {"src": "https://img.icons8.com/emoji/192/lightning-emoji.png", "sizes": "192x192","type": "image/png"}
                ]
            })
            data = manifest.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "application/manifest+json")
            self.end_headers()
            self.wfile.write(data)
            return

        # ── Main dashboard ────────────────────────────────────────────────────
        try:
            html = build().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        except Exception as e:
            error_page = f"<h1>Build Error</h1><pre>{e}</pre>".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(error_page)

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  ⚡ Power 15 Terminal v6.0 — port {port}")
    print(f"  ① Power 15  ② VCP Strategy  ③ Macro Intelligence\n")
    server = HTTPServer(("", port), Handler)
    print(f"  Listening on port {port}...")
    server.serve_forever()
