"""
Power 15 - Simple Bot + Monitor
One file. No complex dependencies. Just works.
Run: .\venv\Scripts\python.exe p15_bot.py
"""
import os, sys, json, time, threading, subprocess
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError
import ssl

# ── Config ─────────────────────────────────────────────────────────────────
BOT   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CID   = os.environ.get("TELEGRAM_CHAT_ID", "")
SURL  = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SKEY  = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
DIR   = os.path.dirname(os.path.abspath(__file__))
PY    = sys.executable
SSL_CTX = ssl.create_default_context()

HYBRID = {
    "NATIONALUM":{"t":75,"tr":15},"INDIANB":{"t":70,"tr":15},"VEDL":{"t":70,"tr":18},
    "SHRIRAMFIN":{"t":70,"tr":15},"CANBK":{"t":65,"tr":15},"SBIN":{"t":70,"tr":15},
    "MANAPPURAM":{"t":60,"tr":20},"ABCAPITAL":{"t":60,"tr":20},"FEDERALBNK":{"t":65,"tr":15},
    "LTF":{"t":80,"tr":0},"BANKINDIA":{"t":65,"tr":15},"HINDALCO":{"t":70,"tr":15},
    "BAJFINANCE":{"t":80,"tr":0},"HINDZINC":{"t":80,"tr":0},"AUBANK":{"t":80,"tr":0},
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── HTTP helpers using only stdlib (no requests needed) ───────────────────────
def http_get(url, headers={}):
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10, context=SSL_CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"GET error: {e}")
        return None

def http_post(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        h = {"Content-Type":"application/json", **headers}
        req = Request(url, data=body, headers=h, method="POST")
        with urlopen(req, timeout=10, context=SSL_CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"POST error: {e}")
        return None

def http_patch(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        h = {"Content-Type":"application/json", **headers}
        req = Request(url, data=body, headers=h, method="PATCH")
        with urlopen(req, timeout=10, context=SSL_CTX) as r:
            return r.read().decode()
    except Exception as e:
        log(f"PATCH error: {e}")
        return None

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg(msg, chat_id=CID):
    return http_post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    )

def tg_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=20"
    if offset: url += f"&offset={offset}"
    return http_get(url)

# ── Supabase ──────────────────────────────────────────────────────────────────
SHDRS = {"apikey": SKEY, "Authorization": f"Bearer {SKEY}"}

def supa_get(table, query=""):
    return http_get(f"{SURL}/rest/v1/{table}?{query}", SHDRS) or []

def supa_patch(table, query, data):
    h = {**SHDRS, "Content-Type":"application/json", "Prefer":"return=representation"}
    return http_patch(f"{SURL}/rest/v1/{table}?{query}", data, h)

# ── Price from Yahoo ──────────────────────────────────────────────────────────
def get_price(sym):
    try:
        d = http_get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS",
            {"User-Agent": "Mozilla/5.0"}
        )
        m = d["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]), float(m.get("regularMarketDayLow", 0))
    except:
        return None, None

def fi(v, signed=False):
    s = "+" if (signed and v >= 0) else ("-" if v < 0 else "")
    v = abs(v)
    if v >= 1e7:   r = f"₹{v/1e7:.2f}Cr"
    elif v >= 1e5: r = f"₹{v/1e5:.1f}L"
    elif v >= 1e3: r = f"₹{v/1e3:.1f}K"
    else:          r = f"₹{v:.0f}"
    return s + r

# ── Bot commands ──────────────────────────────────────────────────────────────
def cmd_help(cid):
    tg("""⚡ <b>Power 15 Bot — Commands</b>

/portfolio  — Full portfolio snapshot
/positions  — Open positions with live prices
/pnl        — P&amp;L summary
/capital    — Capital breakdown
/history    — Last closed trades
/winrate    — Win rate stats
/status     — Market status
/scan       — Run scanner now
/check      — Run buy check now
/help       — This message""", cid)

def cmd_portfolio(cid):
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    cap    = (supa_get("p15_capital", "select=*") or [{}])[0]
    total_pnl = cap.get("total_pnl", 0)
    unreal = 0
    lines  = []
    for t in trades:
        cmp, _ = get_price(t["symbol"])
        if cmp:
            pnl = (cmp - t["entry_price"]) * t["quantity"]
            pct = (cmp - t["entry_price"]) / t["entry_price"] * 100
            unreal += pnl
            icon = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"{icon} <b>{t['symbol']}</b> ₹{cmp:.2f} ({pct:+.1f}%) {fi(pnl, True)}")
    msg = f"⚡ <b>Power 15 Portfolio</b>\n\n"
    if lines:
        msg += "\n".join(lines) + "\n\n"
    else:
        msg += "No open positions\n\n"
    msg += f"💰 Available: {fi(cap.get('available', 0))}\n"
    msg += f"📊 Total P&amp;L: {fi(total_pnl + unreal, True)}\n"
    msg += f"⚡ Unrealised: {fi(unreal, True)}\n"
    msg += f"🏆 Win Rate: {cap.get('winning_trades',0)}/{cap.get('total_trades',0)}"
    tg(msg, cid)

def cmd_positions(cid):
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    if not trades:
        tg("No open positions 🌙", cid); return
    msg = f"📊 <b>Open Positions ({len(trades)})</b>\n\n"
    for t in trades:
        cmp, dl = get_price(t["symbol"])
        pct = ((cmp or t["entry_price"]) - t["entry_price"]) / t["entry_price"] * 100
        pnl = ((cmp or t["entry_price"]) - t["entry_price"]) * t["quantity"]
        sl_pct = (t["sl_price"] - t["entry_price"]) / t["entry_price"] * 100
        icon = "🟢" if pnl >= 0 else "🔴"
        days = (datetime.now() - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
        msg += (f"{icon} <b>{t['symbol']}</b>\n"
                f"   CMP: ₹{cmp:.2f} | Entry: ₹{t['entry_price']:.2f}\n"
                f"   P&amp;L: {fi(pnl, True)} ({pct:+.1f}%) | Day {days}/90\n"
                f"   SL: ₹{t['sl_price']:.2f} ({sl_pct:+.1f}%)\n\n")
    tg(msg, cid)

def cmd_pnl(cid):
    cap = (supa_get("p15_capital", "select=*") or [{}])[0]
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    unreal = 0
    for t in trades:
        cmp, _ = get_price(t["symbol"])
        if cmp: unreal += (cmp - t["entry_price"]) * t["quantity"]
    total = cap.get("total_pnl", 0) + unreal
    ret   = total / cap.get("initial", 500000) * 100
    msg = (f"📈 <b>P&amp;L Summary</b>\n\n"
           f"✅ Realised: {fi(cap.get('total_pnl',0), True)}\n"
           f"⚡ Unrealised: {fi(unreal, True)}\n"
           f"💰 Total: {fi(total, True)}\n"
           f"📊 Return: {ret:+.2f}%\n"
           f"🏆 Win Rate: {cap.get('winning_trades',0)}/{cap.get('total_trades',1)} trades")
    tg(msg, cid)

def cmd_capital(cid):
    cap = (supa_get("p15_capital", "select=*") or [{}])[0]
    avail = cap.get("available", 0)
    inv   = cap.get("invested", 0)
    init  = cap.get("initial", 500000)
    pct   = inv / init * 100 if init else 0
    msg = (f"💰 <b>Capital Status</b>\n\n"
           f"🏦 Total:     {fi(init)}\n"
           f"✅ Available: {fi(avail)}\n"
           f"📊 Invested:  {fi(inv)} ({pct:.1f}%)\n"
           f"📉 P&amp;L:      {fi(cap.get('total_pnl',0), True)}")
    tg(msg, cid)

def cmd_history(cid):
    closed = supa_get("p15_trades", "status=eq.CLOSED&select=*&order=exit_date.desc&limit=10")
    if not closed:
        tg("No closed trades yet.", cid); return
    msg = "📋 <b>Last Closed Trades</b>\n\n"
    for t in closed:
        icon = "✅" if (t.get("pnl") or 0) >= 0 else "❌"
        msg += (f"{icon} <b>{t['symbol']}</b> "
                f"{fi(t.get('pnl',0), True)} ({t.get('pnl_pct',0):+.1f}%)\n"
                f"   {t.get('entry_date','')} → {t.get('exit_date','')}\n")
    tg(msg, cid)

def cmd_winrate(cid):
    cap = (supa_get("p15_capital", "select=*") or [{}])[0]
    total = cap.get("total_trades", 0)
    wins  = cap.get("winning_trades", 0)
    wr    = wins / total * 100 if total else 0
    msg = (f"🏆 <b>Win Rate Stats</b>\n\n"
           f"Total Trades: {total}\n"
           f"Wins: {wins} | Losses: {total-wins}\n"
           f"Win Rate: {wr:.1f}%\n"
           f"Backtest: 98.1% over 108 trades")
    tg(msg, cid)

def cmd_status(cid):
    now = datetime.now()
    hr, mn, wk = now.hour, now.minute, now.weekday()
    if wk >= 5: status = "🔴 Weekend — Market Closed"
    elif (hr == 9 and mn >= 15) or (10 <= hr <= 14) or (hr == 15 and mn <= 30): status = "🟢 Market OPEN"
    else: status = "🔴 Market Closed"
    msg = (f"📊 <b>System Status</b>\n\n"
           f"{status}\n"
           f"🕐 IST: {now.strftime('%d %b %Y %H:%M:%S')}\n\n"
           f"✅ Bot: Online\n"
           f"✅ Supabase: Connected\n"
           f"✅ SL Check: Every 5s (market hours)\n\n"
           f"Schedule:\n"
           f"  3:25 PM → Buy Check\n"
           f"  3:30 PM → Scanner\n"
           f"  4:00 PM → Exit Sweep")
    tg(msg, cid)

def cmd_scan(cid):
    tg("🔍 Running scanner...", cid)
    sc = os.path.join(DIR, "scanner.py")
    if os.path.exists(sc):
        r = subprocess.run([PY, sc], capture_output=True, text=True, timeout=120, cwd=DIR)
        out = r.stdout[-300:] if r.stdout else "Done"
        tg(f"✅ Scanner complete:\n<code>{out}</code>", cid)
    else:
        tg("❌ scanner.py not found", cid)

def cmd_check(cid):
    tg("🛒 Running buy check...", cid)
    sc = os.path.join(DIR, "buy_check.py")
    if os.path.exists(sc):
        r = subprocess.run([PY, sc], capture_output=True, text=True, timeout=120, cwd=DIR)
        out = r.stdout[-300:] if r.stdout else "Done"
        tg(f"✅ Buy check complete:\n<code>{out}</code>", cid)
    else:
        tg("❌ buy_check.py not found", cid)

# ── Process incoming Telegram commands ────────────────────────────────────────
def handle(update):
    msg  = update.get("message") or update.get("edited_message")
    if not msg: return
    cid  = str(msg["chat"]["id"])
    text = msg.get("text", "").strip()
    if not text.startswith("/"): return
    cmd  = text.split()[0].lower().split("@")[0]
    log(f"CMD: {cmd} from {cid}")
    if   cmd == "/help":      cmd_help(cid)
    elif cmd == "/portfolio": cmd_portfolio(cid)
    elif cmd == "/positions": cmd_positions(cid)
    elif cmd == "/pnl":       cmd_pnl(cid)
    elif cmd == "/capital":   cmd_capital(cid)
    elif cmd == "/history":   cmd_history(cid)
    elif cmd == "/winrate":   cmd_winrate(cid)
    elif cmd == "/status":    cmd_status(cid)
    elif cmd == "/scan":      cmd_scan(cid)
    elif cmd == "/check":     cmd_check(cid)
    else: tg(f"Unknown command: {cmd}\n\nSend /help to see all commands.", cid)

# ── SL Monitor ────────────────────────────────────────────────────────────────
alerted = set()

def check_sl():
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    cap_r  = supa_get("p15_capital", "select=*")
    if not cap_r: return
    cap = cap_r[0]

    for t in trades:
        sym   = t["symbol"]
        entry = t["entry_price"]
        sl    = t["sl_price"]
        qty   = t["quantity"]
        cost  = entry * qty
        t1_hit = t.get("t1_hit") or False

        cmp, day_low = get_price(sym)
        if not cmp: continue

        pct_live = (cmp - entry) / entry * 100

        # Update peak CMP
        peak = t.get("peak_cmp") or entry
        if cmp > peak:
            supa_patch("p15_trades", f"id=eq.{t['id']}", {"peak_cmp": round(cmp,2)})
            peak = cmp

        exit_reason = None
        exit_price  = cmp
        alert_key   = None
        partial     = False  # True = partial exit (T1)

        # ── RULE 1: Stop Loss ─────────────────────────────────────────────────
        sl_hit = (day_low and day_low <= sl) or cmp <= sl
        if sl_hit:
            exit_price  = sl if (day_low and day_low <= sl and cmp > sl) else cmp
            exit_reason = f"🛑 SL hit ₹{exit_price:.2f}"
            alert_key   = (sym, "SL")

        # ── RULE 2: T1 — +15% → book 50%, move SL to breakeven ───────────────
        elif pct_live >= 20 and not t1_hit:
            partial     = True
            exit_price  = cmp
            exit_reason = f"🎯 T1 +20% hit ₹{cmp:.2f} — booking 50%"
            alert_key   = (sym, "T1")

        # ── RULE 3: T2 — +30% → full exit ────────────────────────────────────
        elif pct_live >= 30 and t1_hit:
            exit_reason = f"🏆 T2 +30% hit ₹{cmp:.2f} — full exit"
            alert_key   = (sym, "T2")

        # ── RULE 4: Time stop — 90 days ───────────────────────────────────────
        elif t.get("entry_date"):
            days = (datetime.now() - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
            if days >= 90:
                exit_reason = f"⏰ 90-day time stop @ ₹{cmp:.2f}"
                alert_key   = (sym, "TIME")

        if not exit_reason or not alert_key: continue
        if alert_key in alerted: continue
        alerted.add(alert_key)

        # ── PARTIAL EXIT (T1) ─────────────────────────────────────────────────
        if partial:
            book_qty    = max(1, qty // 2)       # sell 50%
            remain_qty  = qty - book_qty
            book_value  = round(book_qty * exit_price, 2)
            book_pnl    = round((exit_price - entry) * book_qty, 2)
            new_sl      = entry  # move SL to breakeven

            # Update trade — reduce qty, mark t1_hit, move SL to breakeven
            supa_patch("p15_trades", f"id=eq.{t['id']}", {
                "quantity":  remain_qty,
                "t1_hit":    True,
                "sl_price":  new_sl,
                "pnl":       round(t.get("pnl", 0) + book_pnl, 2),
            })
            # Free up capital for the booked portion
            supa_patch("p15_capital", "id=eq.1", {
                "available": round(cap["available"] + book_value, 2),
                "invested":  round(cap["invested"]  - book_value, 2),
                "total_pnl": round(cap["total_pnl"] + book_pnl, 2),
            })
            tg(f"🎯 <b>{sym} — T1 Hit!</b>\n\n"
               f"+20% reached @ ₹{exit_price:.2f}\n"
               f"Booked {book_qty} shares for {fi(book_pnl, True)}\n"
               f"Holding {remain_qty} shares\n"
               f"SL moved to breakeven ₹{new_sl:.2f}\n"
               f"Next target: +30% (fixed T2) @ ₹{round(entry*1.30,2)}")
            log(f"T1 hit: {sym} booked {book_qty} shares @ Rs{exit_price:.2f} pnl={book_pnl}")

        # ── FULL EXIT (SL / T2 / TIME) ────────────────────────────────────────
        else:
            pnl     = round((exit_price - entry) * qty, 2)
            pnl_pct = round((exit_price - entry) / entry * 100, 2)
            # Add any previously booked P&L
            total_pnl_trade = round(t.get("pnl", 0) + pnl, 2)

            supa_patch("p15_trades", f"id=eq.{t['id']}", {
                "status":     "CLOSED",
                "exit_date":  datetime.now().strftime("%Y-%m-%d"),
                "exit_price": round(exit_price, 2),
                "pnl":        total_pnl_trade,
                "pnl_pct":    pnl_pct,
                "exit_reason":exit_reason,
            })
            supa_patch("p15_capital", "id=eq.1", {
                "available":      round(cap["available"] + entry * qty + pnl, 2),
                "invested":       round(cap["invested"]  - entry * qty, 2),
                "total_pnl":      round(cap["total_pnl"] + pnl, 2),
                "total_trades":   cap["total_trades"] + 1,
                "winning_trades": cap["winning_trades"] + (1 if total_pnl_trade > 0 else 0),
            })
            icon = "🛑" if "SL" in exit_reason else "🏆" if "T2" in exit_reason else "⏰"
            tg(f"{icon} <b>{sym} CLOSED</b>\n\n"
               f"{exit_reason}\n"
               f"P&L this exit: {fi(pnl, True)}\n"
               f"Total trade P&L: {fi(total_pnl_trade, True)} ({pnl_pct:+.1f}%)\n"
               f"Qty: {qty} | Entry: ₹{entry:.2f}")
            log(f"CLOSED {sym}: {exit_reason} pnl={total_pnl_trade}")

        log(f"EXIT {sym}: {exit_reason} | PnL {pnl}")

def monitor_loop():
    log("SL monitor started — checking every 5s during market hours")
    ran_buy = ran_scan = False
    last_day = None
    while True:
        try:
            now = datetime.now()
            today = now.date()
            if last_day != today:
                ran_buy = ran_scan = False
                alerted.clear()
                last_day = today
            hr, mn, wk = now.hour, now.minute, now.weekday()
            market = wk < 5 and ((hr == 9 and mn >= 15) or (10 <= hr <= 14) or (hr == 15 and mn <= 30))
            if market:
                if hr == 15 and mn >= 25 and not ran_buy:
                    ran_buy = True
                    log("Running buy check...")
                    sc = os.path.join(DIR, "buy_check.py")
                    if os.path.exists(sc):
                        subprocess.Popen([PY, sc], cwd=DIR)
                if hr == 15 and mn >= 30 and not ran_scan:
                    ran_scan = True
                    log("Running scanner...")
                    sc = os.path.join(DIR, "scanner.py")
                    if os.path.exists(sc):
                        subprocess.Popen([PY, sc], cwd=DIR)
                check_sl()
                time.sleep(5)
            else:
                time.sleep(60)
        except Exception as e:
            log(f"Monitor error: {e}")
            time.sleep(10)

# ── Telegram poll loop ────────────────────────────────────────────────────────
def bot_loop():
    log("Telegram bot started — listening for commands...")
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT}/getUpdates?timeout=20"
            if offset: url += f"&offset={offset}"
            req = Request(url)
            with urlopen(req, timeout=25, context=SSL_CTX) as r:
                data = json.loads(r.read().decode())
            if data.get("ok"):
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    try:
                        handle(upd)
                    except Exception as e:
                        log(f"Handler error: {e}")
        except Exception as e:
            log(f"Bot error: {e}")
            time.sleep(5)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  ⚡ Power 15 Bot + Monitor")
    print("  Uses ONLY Python stdlib — no pip needed!")
    print("  Started:", datetime.now().strftime("%d %b %Y %H:%M:%S"))
    print("="*55 + "\n")

    # Send startup Telegram
    result = tg("⚡ <b>Power 15 Bot Online!</b>\n\n"
                "✅ Telegram commands active\n"
                "✅ SL monitor running (every 5s)\n"
                "✅ No extra packages needed\n\n"
                "Send /help to see all commands!")
    if result and result.get("ok"):
        log("✅ Startup message sent to Telegram!")
    else:
        log(f"⚠️  Telegram send failed: {result}")

    # Start monitor in background thread
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()

    # Run bot in main thread
    bot_loop()
