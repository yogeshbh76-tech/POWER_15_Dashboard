import os, sys, json, time, threading, subprocess
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl

BOT   = "8734533440:AAFEvxvdNSjb_8Wsu-yucsph3mqyHVtkhF8"
CID   = "8321668899"
SURL  = "https://xlrbmsmrgosqbioojqfz.supabase.co"
SKEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM"
DIR   = os.path.dirname(os.path.abspath(__file__))
PY    = sys.executable
CTX   = ssl.create_default_context()
HYBRID = {
    "NATIONALUM":{"t":75,"tr":15},"INDIANB":{"t":70,"tr":15},"VEDL":{"t":70,"tr":18},
    "SHRIRAMFIN":{"t":70,"tr":15},"CANBK":{"t":65,"tr":15},"SBIN":{"t":70,"tr":15},
    "MANAPPURAM":{"t":60,"tr":20},"ABCAPITAL":{"t":60,"tr":20},"FEDERALBNK":{"t":65,"tr":15},
    "LTF":{"t":80,"tr":0},"BANKINDIA":{"t":65,"tr":15},"HINDALCO":{"t":70,"tr":15},
    "BAJFINANCE":{"t":80,"tr":0},"HINDZINC":{"t":80,"tr":0},"AUBANK":{"t":80,"tr":0},
}

def log(m): print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)

def http_get(url, headers={}):
    try:
        req = Request(url, headers={"User-Agent":"Mozilla/5.0",**headers})
        with urlopen(req, timeout=10, context=CTX) as r: return json.loads(r.read().decode())
    except Exception as e: log(f"GET err: {e}"); return None

def http_post(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        req  = Request(url, data=body, headers={"Content-Type":"application/json",**headers}, method="POST")
        with urlopen(req, timeout=10, context=CTX) as r: return json.loads(r.read().decode())
    except Exception as e: log(f"POST err: {e}"); return None

def http_patch(url, data, extra_headers={}):
    try:
        body = json.dumps(data).encode()
        h    = {"Content-Type":"application/json","apikey":SKEY,"Authorization":f"Bearer {SKEY}","Prefer":"return=minimal",**extra_headers}
        req  = Request(url, data=body, headers=h, method="PATCH")
        with urlopen(req, timeout=10, context=CTX) as r: return r.status
    except Exception as e: log(f"PATCH err: {e}"); return None

SHDRS = {"apikey":SKEY,"Authorization":f"Bearer {SKEY}"}
def supa(table, q=""): return http_get(f"{SURL}/rest/v1/{table}?{q}", SHDRS) or []
def spatch(table, q, d): return http_patch(f"{SURL}/rest/v1/{table}?{q}", d)

def tg(msg, cid=CID):
    return http_post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                     {"chat_id":cid,"text":msg,"parse_mode":"HTML"})

def price(sym):
    d = http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS")
    if not d: return None, None
    try:
        m = d["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]), float(m.get("regularMarketDayLow",0))
    except: return None, None

def fi(v, s=False):
    sg = ("+" if v>=0 else "-") if s else ("-" if v<0 else "")
    v=abs(v)
    if v>=1e7: r=f"Rs{v/1e7:.2f}Cr"
    elif v>=1e5: r=f"Rs{v/1e5:.1f}L"
    elif v>=1e3: r=f"Rs{v/1e3:.1f}K"
    else: r=f"Rs{v:.0f}"
    return sg+r

def cmd_help(cid):
    tg("Power 15 Bot Commands\n\n/portfolio - Full snapshot\n/positions - Open positions\n/pnl - Profit and loss\n/capital - Capital status\n/history - Closed trades\n/winrate - Win rate\n/status - Market status\n/scan - Run scanner now\n/check - Run buy check\n/help - This message", cid)

def cmd_portfolio(cid):
    trades = supa("p15_trades","status=eq.OPEN&select=*")
    cap    = (supa("p15_capital","select=*") or [{}])[0]
    unreal = 0; lines = []
    for t in trades:
        cmp,_ = price(t["symbol"])
        if cmp:
            pnl=(cmp-t["entry_price"])*t["quantity"]; pct=(cmp-t["entry_price"])/t["entry_price"]*100
            unreal+=pnl; icon="UP" if pnl>=0 else "DN"
            lines.append(f"{icon} {t['symbol']} Rs{cmp:.2f} ({pct:+.1f}%) {fi(pnl,True)}")
    msg = "Power 15 Portfolio\n\n"
    msg += "\n".join(lines) if lines else "No open positions"
    msg += f"\n\nAvailable: {fi(cap.get('available',0))}\nTotal PnL: {fi(cap.get('total_pnl',0)+unreal,True)}\nWin Rate: {cap.get('winning_trades',0)}/{cap.get('total_trades',0)}"
    tg(msg, cid)

def cmd_positions(cid):
    trades = supa("p15_trades","status=eq.OPEN&select=*")
    if not trades: tg("No open positions", cid); return
    msg = f"Open Positions ({len(trades)})\n\n"
    for t in trades:
        cmp,_ = price(t["symbol"])
        p = cmp or t["entry_price"]
        pct=(p-t["entry_price"])/t["entry_price"]*100; pnl=(p-t["entry_price"])*t["quantity"]
        days=(datetime.now()-datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
        msg+=f"{t['symbol']}: Rs{p:.2f} ({pct:+.1f}%) {fi(pnl,True)} Day {days}/90 SL Rs{t['sl_price']:.2f}\n"
    tg(msg, cid)

def cmd_pnl(cid):
    cap = (supa("p15_capital","select=*") or [{}])[0]
    trades = supa("p15_trades","status=eq.OPEN&select=*")
    unreal = sum(((price(t["symbol"])[0] or t["entry_price"])-t["entry_price"])*t["quantity"] for t in trades)
    total = cap.get("total_pnl",0)+unreal
    ret   = total/cap.get("initial",500000)*100
    tg(f"PnL Summary\n\nRealised: {fi(cap.get('total_pnl',0),True)}\nUnrealised: {fi(unreal,True)}\nTotal: {fi(total,True)}\nReturn: {ret:+.2f}%\nTrades: {cap.get('winning_trades',0)}/{cap.get('total_trades',0)} won", cid)

def cmd_capital(cid):
    cap = (supa("p15_capital","select=*") or [{}])[0]
    avail=cap.get("available",0); inv=cap.get("invested",0); init=cap.get("initial",500000)
    pct=inv/init*100 if init else 0
    tg(f"Capital Status\n\nTotal: {fi(init)}\nAvailable: {fi(avail)}\nInvested: {fi(inv)} ({pct:.1f}%)\nPnL: {fi(cap.get('total_pnl',0),True)}", cid)

def cmd_history(cid):
    cl = supa("p15_trades","status=eq.CLOSED&select=*&order=exit_date.desc&limit=10")
    if not cl: tg("No closed trades yet.", cid); return
    msg = "Last Closed Trades\n\n"
    for t in cl:
        icon = "WIN" if (t.get("pnl") or 0)>=0 else "LOSS"
        msg += f"{icon} {t['symbol']} {fi(t.get('pnl',0),True)} ({t.get('pnl_pct',0):+.1f}%) {t.get('entry_date','')} to {t.get('exit_date','')}\n"
    tg(msg, cid)

def cmd_winrate(cid):
    cap = (supa("p15_capital","select=*") or [{}])[0]
    total=cap.get("total_trades",0); wins=cap.get("winning_trades",0)
    wr = wins/total*100 if total else 0
    tg(f"Win Rate Stats\n\nTotal: {total} trades\nWins: {wins} Losses: {total-wins}\nWin Rate: {wr:.1f}%\nBacktest: 98.1% (108 trades)", cid)

def cmd_status(cid):
    now=datetime.now(); hr,mn,wk=now.hour,now.minute,now.weekday()
    if wk>=5: st="WEEKEND - Closed"
    elif (hr==9 and mn>=15) or (10<=hr<=14) or (hr==15 and mn<=30): st="MARKET OPEN"
    else: st="MARKET CLOSED"
    tg(f"System Status\n\n{st}\nIST: {now.strftime('%d %b %Y %H:%M:%S')}\n\nBot: Online\nSL Check: Every 5s\nScanner: 3:30 PM\nBuy Check: 3:25 PM", cid)

def cmd_scan(cid):
    tg("Running scanner...", cid)
    sc=os.path.join(DIR,"scanner.py")
    if os.path.exists(sc):
        r=subprocess.run([PY,sc],capture_output=True,text=True,timeout=120,cwd=DIR)
        tg(f"Scanner done:\n{(r.stdout or r.stderr or 'OK')[-400:]}", cid)
    else: tg("scanner.py not found in "+DIR, cid)

def cmd_check(cid):
    tg("Running buy check...", cid)
    sc=os.path.join(DIR,"buy_check.py")
    if os.path.exists(sc):
        r=subprocess.run([PY,sc],capture_output=True,text=True,timeout=120,cwd=DIR)
        tg(f"Buy check done:\n{(r.stdout or r.stderr or 'OK')[-400:]}", cid)
    else: tg("buy_check.py not found", cid)

def handle(upd):
    msg  = upd.get("message") or upd.get("edited_message")
    if not msg: return
    cid  = str(msg["chat"]["id"])
    text = msg.get("text","").strip()
    if not text.startswith("/"): return
    cmd  = text.split()[0].lower().split("@")[0]
    log(f"CMD: {cmd}")
    if   cmd=="/help":      cmd_help(cid)
    elif cmd=="/portfolio": cmd_portfolio(cid)
    elif cmd=="/positions": cmd_positions(cid)
    elif cmd=="/pnl":       cmd_pnl(cid)
    elif cmd=="/capital":   cmd_capital(cid)
    elif cmd=="/history":   cmd_history(cid)
    elif cmd=="/winrate":   cmd_winrate(cid)
    elif cmd=="/status":    cmd_status(cid)
    elif cmd=="/scan":      cmd_scan(cid)
    elif cmd=="/check":     cmd_check(cid)
    else: tg(f"Unknown: {cmd}. Send /help", cid)

alerted = set()
def check_sl():
    trades = supa("p15_trades","status=eq.OPEN&select=*")
    cap_r  = supa("p15_capital","select=*")
    if not cap_r: return
    cap = cap_r[0]
    for t in trades:
        sym=t["symbol"]; entry=t["entry_price"]; sl=t["sl_price"]; qty=t["quantity"]; cost=entry*qty
        cmp,dl = price(sym)
        if not cmp: continue
        peak = t.get("peak_cmp") or entry
        if cmp > peak:
            spatch("p15_trades",f"id=eq.{t['id']}",{"peak_cmp":round(cmp,2)}); peak=cmp
        pk_pct=(peak-entry)/entry*100; pct=(cmp-entry)/entry*100; cfg=HYBRID.get(sym,{"t":80,"tr":0})
        exit_reason=None; exit_price=cmp; akey=None
        if (dl and dl<=sl) or cmp<=sl:
            exit_price=sl if (dl and dl<=sl and cmp>sl) else cmp
            exit_reason=f"SL hit Rs{exit_price:.2f} (low Rs{dl:.2f})"; akey=(sym,"SL")
        elif cfg["tr"]>0 and pk_pct>=cfg["t"]:
            ts=peak*(1-cfg["tr"]/100)
            if cmp<=ts: exit_reason=f"Trailing stop Rs{cmp:.2f} (peak Rs{peak:.2f})"; akey=(sym,"TRAIL")
        elif pct>=80 and cfg["tr"]==0:
            exit_reason=f"Target +80% hit Rs{cmp:.2f}"; akey=(sym,"TARGET")
        if not exit_reason or akey in alerted: continue
        alerted.add(akey)
        pnl=round((exit_price-entry)*qty,2); pnl_pct=round((exit_price-entry)/entry*100,2)
        spatch("p15_trades",f"id=eq.{t['id']}",{
            "status":"CLOSED","exit_date":datetime.now().strftime("%Y-%m-%d"),
            "exit_price":round(exit_price,2),"pnl":pnl,"pnl_pct":pnl_pct,"exit_reason":exit_reason})
        spatch("p15_capital","id=eq.1",{
            "available":round(cap["available"]+cost+pnl,2),"invested":round(cap["invested"]-cost,2),
            "total_pnl":round(cap["total_pnl"]+pnl,2),"total_trades":cap["total_trades"]+1,
            "winning_trades":cap["winning_trades"]+(1 if pnl>0 else 0)})
        tg(f"EXIT {sym}\n{exit_reason}\nPnL: {fi(pnl,True)} ({pnl_pct:+.1f}%)\nQty: {qty}")
        log(f"EXIT {sym} pnl={pnl}")

def monitor_loop():
    log("SL monitor running — every 5s in market hours")
    ran_buy=ran_scan=False; last_day=None
    while True:
        try:
            now=datetime.now(); today=now.date()
            if last_day!=today: ran_buy=ran_scan=False; alerted.clear(); last_day=today
            hr,mn,wk=now.hour,now.minute,now.weekday()
            mkt=wk<5 and ((hr==9 and mn>=15) or (10<=hr<=14) or (hr==15 and mn<=30))
            if mkt:
                if hr==15 and mn>=25 and not ran_buy:
                    ran_buy=True; sc=os.path.join(DIR,"buy_check.py")
                    if os.path.exists(sc): subprocess.Popen([PY,sc],cwd=DIR)
                if hr==15 and mn>=30 and not ran_scan:
                    ran_scan=True; sc=os.path.join(DIR,"scanner.py")
                    if os.path.exists(sc): subprocess.Popen([PY,sc],cwd=DIR)
                check_sl(); time.sleep(5)
            else: time.sleep(60)
        except Exception as e: log(f"Monitor err: {e}"); time.sleep(10)

def bot_loop():
    log("Telegram bot listening...")
    offset=None
    while True:
        try:
            url=f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=20"
            if offset: url+=f"&offset={offset}"
            data=http_get(url)
            if data and data.get("ok"):
                for u in data.get("result",[]):
                    offset=u["update_id"]+1
                    try: handle(u)
                    except Exception as e: log(f"handle err: {e}")
        except Exception as e: log(f"bot err: {e}"); time.sleep(5)

if __name__=="__main__":
    print("="*50)
    print("  Power 15 Bot + Monitor")
    print("  Zero external dependencies!")
    print("  Started:", datetime.now().strftime("%d %b %Y %H:%M:%S"))
    print("="*50)
    r = tg("Power 15 Bot Online! Send /help for commands. SL monitor active every 5s.")
    log("Telegram: " + ("OK" if r and r.get("ok") else "FAILED - check connection"))
    threading.Thread(target=monitor_loop, daemon=True).start()
    bot_loop()
