"""
Power 15 — MA Strategy v2.0
=================================================
9 EMA + 21 EMA + 50 EMA on 15-minute candles
Scans 10 high-quality NSE stocks for intraday signals
Zero external dependencies — only Python stdlib

Signals sent to Telegram instantly.
Trades stored in Supabase: ma_trades table

v2.0: runs as a single bounded pass per invocation instead of an infinite
while-loop, so it can be triggered by GitHub Actions cron (every 15 min
during market hours) instead of needing a PC running all day.

Run modes:
  python ma_strategy.py             → scan for exits + new entries
  python ma_strategy.py --squareoff → force-close all open trades (3:15 PM)
  python ma_strategy.py --eod       → send end-of-day summary (3:31 PM)
"""
import os, sys, json, ssl
from datetime import datetime, date
from urllib.request import urlopen, Request

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPA_URL   = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPA_KEY   = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
CTX        = ssl.create_default_context()

# ── Strategy config ───────────────────────────────────────────────────────────
CAPITAL_PER_TRADE = 10000   # Rs10,000 per trade
MAX_TRADES        = 6       # max simultaneous intraday trades
SL_PCT            = 0.0075  # 0.75% stop loss
TARGET1_PCT       = 0.010   # 1.0% target 1
TARGET2_PCT       = 0.015   # 1.5% target 2

# ── Stock universe ────────────────────────────────────────────────────────────
MA_STOCKS = {
    "RELIANCE":   "Energy",
    "HDFCBANK":   "Banking",
    "ICICIBANK":  "Banking",
    "SBIN":       "Banking",
    "TMPV":       "Auto",        # Tata Motors Passenger Vehicles (was TATAMOTORS, renamed Oct 2025)
    "BAJFINANCE": "Finance",
    "INFY":       "IT",
    "WIPRO":      "IT",
    "AXISBANK":   "Banking",
    "LT":         "Infra",
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────
SHDRS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

def http_get(url, headers={}):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0", **headers})
        with urlopen(req, timeout=12, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"GET error ({url[:60]}...): {e}")
        return None

def http_post(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        req  = Request(url, data=body,
                       headers={"Content-Type": "application/json", **headers})
        with urlopen(req, timeout=10, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return None

def http_patch(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        h    = {"Content-Type": "application/json",
                "Prefer": "return=minimal", **SHDRS, **headers}
        req  = Request(url, data=body, headers=h, method="PATCH")
        with urlopen(req, timeout=10, context=CTX) as r:
            return r.status
    except Exception as e:
        log(f"PATCH error: {e}")
        return None

def tg(msg):
    """Send Telegram message. Silently swallows errors."""
    try:
        http_post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except Exception as e:
        log(f"Telegram error: {e}")

def supa_get(table, query=""):
    """Returns None on a genuine connection/HTTP failure, [] only for a real
    empty result — so a Supabase outage never gets mistaken for "nothing to do"."""
    result = http_get(f"{SUPA_URL}/rest/v1/{table}?{query}", SHDRS)
    return result if isinstance(result, list) else None

def supa_post(table, data):
    h = {**SHDRS, "Content-Type": "application/json", "Prefer": "return=representation"}
    return http_post(f"{SUPA_URL}/rest/v1/{table}", data, h)

def supa_patch(table, query, data):
    return http_patch(f"{SUPA_URL}/rest/v1/{table}?{query}", data)

def log(msg):
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── EMA calculation (matches TradingView / Chartink) ─────────────────────────
def calc_ema(values, period):
    if len(values) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(values[:period]) / period   # seed with SMA
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return round(ema, 4)

def fi(v, signed=False):
    """Format Indian currency."""
    s = ("+" if v >= 0 else "-") if signed else ("-" if v < 0 else "")
    v = abs(v)
    if v >= 1e7:   r = f"Rs{v/1e7:.2f}Cr"
    elif v >= 1e5: r = f"Rs{v/1e5:.1f}L"
    elif v >= 1e3: r = f"Rs{v/1e3:.1f}K"
    else:          r = f"Rs{v:.0f}"
    return s + r

# ── Fetch 15-min OHLCV from Yahoo Finance ─────────────────────────────────────
def get_15min_data(symbol):
    """Fetch last 5 days of 15-minute candles. Returns {candles, cmp} or None."""
    for host in ["query1", "query2"]:
        try:
            d = http_get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
                f"?interval=15m&range=5d"
            )
            if not d or not d.get("chart", {}).get("result"):
                continue
            result = d["chart"]["result"][0]
            ts     = result["timestamp"]
            q      = result["indicators"]["quote"][0]
            closes = q.get("close",  [])
            highs  = q.get("high",   [])
            lows   = q.get("low",    [])
            opens  = q.get("open",   [])
            vols   = q.get("volume", [])
            cmp    = float(result["meta"]["regularMarketPrice"])

            candles = []
            for i in range(len(closes)):
                if all(x is not None for x in [closes[i], highs[i], lows[i], opens[i]]):
                    candles.append({
                        "ts": ts[i], "o": opens[i], "h": highs[i],
                        "l": lows[i], "c": closes[i], "v": vols[i] or 0,
                    })
            return {"candles": candles, "cmp": cmp}
        except Exception as e:
            log(f"Data fetch failed for {symbol} on {host}: {e}")
            continue
    return None

# ── Signal detection ──────────────────────────────────────────────────────────
def check_signal(symbol):
    """
    Check for EMA 9/21 crossover with EMA 50 trend filter.
    Returns signal dict or None.
    BUY conditions (ALL must be true):
      1. EMA9 crosses above EMA21 on this candle
      2. Price is above EMA50
      3. Current candle is green (close > open)
      4. Volume >= 80% of 20-candle average
    """
    data = get_15min_data(symbol)
    if not data or len(data["candles"]) < 60:
        return None

    candles = data["candles"]
    closes  = [c["c"] for c in candles]
    vols    = [c["v"] for c in candles]

    # Current candle EMAs
    ema9_now  = calc_ema(closes,      9)
    ema21_now = calc_ema(closes,     21)
    ema50_now = calc_ema(closes,     50)

    # Previous candle EMAs (exclude last close)
    ema9_prev  = calc_ema(closes[:-1],  9)
    ema21_prev = calc_ema(closes[:-1], 21)

    if not all([ema9_now, ema21_now, ema50_now, ema9_prev, ema21_prev]):
        return None

    cmp          = data["cmp"]
    last_c       = candles[-1]
    avg_vol      = sum(vols[-20:]) / 20 if len(vols) >= 20 else None
    curr_vol     = vols[-1]
    vol_ok       = (curr_vol >= avg_vol * 0.8) if avg_vol else True
    green_candle = last_c["c"] > last_c["o"]

    # BUY: EMA9 crosses above EMA21, price above EMA50
    buy_cross   = (ema9_prev <= ema21_prev) and (ema9_now > ema21_now)
    above_ema50 = cmp > ema50_now

    if buy_cross and above_ema50 and green_candle and vol_ok:
        sl  = round(cmp * (1 - SL_PCT), 2)
        t1  = round(cmp * (1 + TARGET1_PCT), 2)
        t2  = round(cmp * (1 + TARGET2_PCT), 2)
        qty = max(1, int(CAPITAL_PER_TRADE / cmp))
        vol_ratio = round(curr_vol / avg_vol, 2) if avg_vol else None
        return {
            "signal":    "BUY",
            "symbol":    symbol,
            "sector":    MA_STOCKS[symbol],
            "cmp":       round(cmp, 2),
            "sl":        sl,
            "target1":   t1,
            "target2":   t2,
            "qty":       qty,
            "ema9":      round(ema9_now, 2),
            "ema21":     round(ema21_now, 2),
            "ema50":     round(ema50_now, 2),
            "vol_ratio": vol_ratio,
        }

    return None

# ── Trade management ──────────────────────────────────────────────────────────
def get_open_trades():
    today = date.today().strftime("%Y-%m-%d")
    return supa_get("ma_trades", f"status=eq.OPEN&trade_date=eq.{today}&select=*")

def get_ma_capital():
    """MA strategy's own capital pool — separate from Power15's and VCP's."""
    rows = supa_get("ma_capital", "select=*")
    if rows is None:
        return None
    return rows[0] if rows else {
        "id": 1, "initial": 100000, "available": 100000, "invested": 0,
        "total_pnl": 0, "total_trades": 0, "winning_trades": 0
    }

def already_traded_today(symbol):
    """True if this symbol already has a trade (open or closed) today — takes
    the place of the old in-memory alerted_today set, which can't survive
    between separate cron-triggered runs. Fails safe: an unreachable Supabase
    counts as "already traded" so we never risk a duplicate buy."""
    today = date.today().strftime("%Y-%m-%d")
    rows = supa_get("ma_trades", f"symbol=eq.{symbol}&trade_date=eq.{today}&select=id&limit=1")
    if rows is None:
        return True
    return len(rows) > 0

def open_trade(sig):
    capital = get_ma_capital()
    if capital is None:
        log(f"Supabase unreachable — skipping {sig['symbol']} entry")
        return None

    cost = round(sig["qty"] * sig["cmp"], 2)
    if capital["available"] < cost:
        log(f"Insufficient MA capital for {sig['symbol']} — need Rs{cost:.0f}, have Rs{capital['available']:.0f}")
        return None

    today  = date.today().strftime("%Y-%m-%d")
    now_t  = datetime.now().strftime("%H:%M:%S")
    record = {
        "symbol":      sig["symbol"],
        "sector":      sig["sector"],
        "trade_date":  today,
        "entry_time":  now_t,
        "entry_price": sig["cmp"],
        "quantity":    sig["qty"],
        "sl_price":    sig["sl"],
        "target1":     sig["target1"],
        "target2":     sig["target2"],
        "ema9":        sig["ema9"],
        "ema21":       sig["ema21"],
        "ema50":       sig["ema50"],
        "status":      "OPEN",
        "pnl":         0,
    }
    result = supa_post("ma_trades", record)
    if result:
        log(f"Trade opened in Supabase: {sig['symbol']}")
        supa_patch("ma_capital", "id=eq.1", {
            "available": round(capital["available"] - cost, 2),
            "invested":  round(capital["invested"] + cost, 2),
        })
    else:
        log(f"WARNING: Supabase insert may have failed for {sig['symbol']}")
    return result

def close_trade(trade_id, exit_price, reason, entry_price, quantity):
    """Close a trade, write final PnL, and settle it against MA's own capital pool."""
    now_t = datetime.now().strftime("%H:%M:%S")
    pnl   = round((exit_price - entry_price) * quantity, 2)
    supa_patch("ma_trades", f"id=eq.{trade_id}", {
        "status":      "CLOSED",
        "exit_time":   now_t,
        "exit_price":  round(exit_price, 2),
        "exit_reason": reason,
        "pnl":         pnl,
    })

    capital = get_ma_capital()
    if capital is None:
        log("Supabase unreachable — trade closed but capital pool not updated")
        return
    cost = round(entry_price * quantity, 2)
    supa_patch("ma_capital", "id=eq.1", {
        "available":      round(capital["available"] + cost + pnl, 2),
        "invested":       round(max(0, capital["invested"] - cost), 2),
        "total_pnl":      round(capital["total_pnl"] + pnl, 2),
        "total_trades":   capital["total_trades"] + 1,
        "winning_trades": capital["winning_trades"] + (1 if pnl > 0 else 0),
    })

def check_exits():
    """Check all open MA trades for SL / target / EMA crossover exits."""
    trades = get_open_trades()
    if trades is None:
        log("Supabase unreachable — skipping exit check")
        return
    for t in trades:
        sym        = t["symbol"]
        entry_px   = float(t["entry_price"])
        qty        = int(t["quantity"])
        sl_price   = float(t["sl_price"])
        target1    = float(t["target1"])
        target2    = float(t["target2"])
        t1_hit     = t.get("t1_hit", False)

        d = get_15min_data(sym)
        if not d:
            continue
        cmp = d["cmp"]
        pnl = (cmp - entry_px) * qty
        pct = (cmp - entry_px) / entry_px * 100

        # ── SL hit ────────────────────────────────────────────────────────────
        if cmp <= sl_price:
            close_trade(t["id"], cmp, f"SL hit @ Rs{cmp:.2f}", entry_px, qty)
            tg(f"🛑 <b>MA Strategy — SL Hit</b>\n\n"
               f"<b>{sym}</b> exit @ Rs{cmp:.2f}\n"
               f"P&amp;L: <b>{fi(pnl, True)} ({pct:+.2f}%)</b>\n"
               f"Entry was Rs{entry_px:.2f}")
            log(f"SL hit: {sym} @ Rs{cmp:.2f}  PnL={pnl:.0f}")
            continue

        # ── Target 2 hit — full exit (check before T1 so it takes priority) ──
        if cmp >= target2:
            close_trade(t["id"], cmp, f"Target 2 hit @ Rs{cmp:.2f}", entry_px, qty)
            tg(f"🏆 <b>MA Strategy — Target 2 Hit!</b>\n\n"
               f"<b>{sym}</b> exit @ Rs{cmp:.2f} (+{TARGET2_PCT*100:.1f}%)\n"
               f"P&amp;L: <b>{fi(pnl, True)} ({pct:+.2f}%)</b>\n"
               f"Full exit! 🎉")
            log(f"Target 2 hit: {sym} @ Rs{cmp:.2f}  PnL={pnl:.0f}")
            continue

        # ── Target 1 hit — alert only (partial book reminder) ────────────────
        if cmp >= target1 and not t1_hit:
            supa_patch("ma_trades", f"id=eq.{t['id']}", {"t1_hit": True})
            tg(f"🎯 <b>MA Strategy — Target 1 Hit!</b>\n\n"
               f"<b>{sym}</b> @ Rs{cmp:.2f} (+{TARGET1_PCT*100:.1f}%)\n"
               f"Book 50% profit here!\n"
               f"P&amp;L so far: <b>{fi(pnl, True)}</b>")
            log(f"Target 1 hit: {sym} @ Rs{cmp:.2f}")
            # Continue holding for T2 — don't close

        # ── EMA crossover exit ────────────────────────────────────────────────
        candles = d["candles"]
        if len(candles) >= 2:
            closes    = [c["c"] for c in candles]
            ema9_now  = calc_ema(closes,      9)
            ema21_now = calc_ema(closes,     21)
            ema9_prev = calc_ema(closes[:-1], 9)
            ema21_prev= calc_ema(closes[:-1],21)
            if all([ema9_now, ema21_now, ema9_prev, ema21_prev]):
                # Actual crossover: was above, now below
                crossed_down = (ema9_prev >= ema21_prev) and (ema9_now < ema21_now)
                if crossed_down:
                    close_trade(t["id"], cmp,
                                f"EMA crossover exit @ Rs{cmp:.2f}",
                                entry_px, qty)
                    tg(f"📉 <b>MA Strategy — EMA Exit</b>\n\n"
                       f"<b>{sym}</b> exit @ Rs{cmp:.2f}\n"
                       f"EMA9 crossed below EMA21\n"
                       f"P&amp;L: <b>{fi(pnl, True)} ({pct:+.2f}%)</b>")
                    log(f"EMA exit: {sym} @ Rs{cmp:.2f}")

# ── Scan for new entries + check exits (runs every 15 min via cron) ──────────
def run_scan():
    log("[MA Strategy — Scan]")

    check_exits()

    open_trades = get_open_trades()
    if open_trades is None:
        log("Supabase unreachable — skipping new-entry scan")
        return
    slots_free = MAX_TRADES - len(open_trades)
    if slots_free <= 0:
        log(f"Max trades ({MAX_TRADES}) reached — skipping new entries")
        return

    log(f"Scanning {len(MA_STOCKS)} stocks ({slots_free} slot(s) free)...")
    signals_found = 0
    for sym in MA_STOCKS:
        if slots_free <= 0:
            break
        if already_traded_today(sym):
            continue
        sig = check_signal(sym)
        if sig and sig["signal"] == "BUY":
            log(f"BUY signal: {sym} @ Rs{sig['cmp']:.2f}")

            if not open_trade(sig):
                continue  # insufficient capital or Supabase issue — no alert, no slot used

            signals_found += 1
            slots_free    -= 1

            vr_str = f"{sig['vol_ratio']}x" if sig["vol_ratio"] else "n/a"
            tg(
                f"⚡ <b>MA Strategy — BUY Signal!</b>\n\n"
                f"📈 <b>{sym}</b> ({sig['sector']})\n\n"
                f"Entry:     Rs{sig['cmp']:.2f}\n"
                f"Stop Loss: Rs{sig['sl']:.2f}  (-{SL_PCT*100:.2f}%)\n"
                f"Target 1:  Rs{sig['target1']:.2f}  (+{TARGET1_PCT*100:.1f}%)\n"
                f"Target 2:  Rs{sig['target2']:.2f}  (+{TARGET2_PCT*100:.1f}%)\n"
                f"Qty: {sig['qty']} shares\n\n"
                f"EMA9: {sig['ema9']} | EMA21: {sig['ema21']} | EMA50: {sig['ema50']}\n"
                f"Vol ratio: {vr_str}\n\n"
                f"<i>Paper trade — 15 min chart</i>"
            )

    if signals_found == 0:
        log("No new signals this scan")

# ── EOD square off (runs once at 3:15 PM via cron) ────────────────────────────
def square_off_all():
    """Force close all open MA trades."""
    trades = get_open_trades()
    if trades is None:
        log("Supabase unreachable — skipping square-off")
        return
    if not trades:
        log("Square off: no open trades")
        return
    log(f"Square off time — closing {len(trades)} open MA trades")
    for t in trades:
        sym      = t["symbol"]
        entry_px = float(t["entry_price"])
        qty      = int(t["quantity"])
        d        = get_15min_data(sym)
        cmp      = d["cmp"] if d else entry_px
        pnl      = (cmp - entry_px) * qty
        pct      = (cmp - entry_px) / entry_px * 100
        close_trade(t["id"], cmp, f"EOD square off @ Rs{cmp:.2f}", entry_px, qty)
        tg(f"⏰ <b>MA Strategy — EOD Square Off</b>\n\n"
           f"<b>{sym}</b> @ Rs{cmp:.2f}\n"
           f"P&amp;L: <b>{fi(pnl, True)} ({pct:+.2f}%)</b>")
        log(f"Squared off: {sym} @ Rs{cmp:.2f}  PnL={pnl:.0f}")

# ── EOD summary (runs once at 3:31 PM via cron) ───────────────────────────────
def send_eod_summary():
    """Send today's MA strategy summary."""
    today  = date.today().strftime("%Y-%m-%d")
    trades = supa_get("ma_trades", f"trade_date=eq.{today}&select=*")
    if trades is None:
        log("Supabase unreachable — skipping EOD summary")
        return
    if not trades:
        tg("📊 <b>MA Strategy EOD</b>\n\nNo trades today.")
        return
    total_pnl = sum(float(t.get("pnl") or 0) for t in trades)
    wins      = sum(1 for t in trades if float(t.get("pnl") or 0) > 0)
    total     = len(trades)
    msg = f"📊 <b>MA Strategy — EOD {datetime.now().strftime('%d %b %Y')}</b>\n\n"
    for t in trades:
        pnl  = float(t.get("pnl") or 0)
        icon = "✅" if pnl >= 0 else "❌"
        reason = (t.get("exit_reason") or "open")[:28]
        msg += f"{icon} <b>{t['symbol']}</b>: {fi(pnl, True)}  ({reason})\n"
    msg += f"\n<b>Total P&amp;L: {fi(total_pnl, True)}</b>\n"
    msg += f"Win Rate: {wins}/{total} ({wins/total*100:.0f}%)" if total else ""
    tg(msg)
    log("EOD summary sent")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    mode = "scan"
    if "--squareoff" in sys.argv: mode = "squareoff"
    elif "--eod" in sys.argv:     mode = "eod"

    print(f"[MA Strategy — {mode} — {datetime.now().strftime('%d %b %Y %H:%M:%S')}]")

    if mode == "squareoff":
        square_off_all()
    elif mode == "eod":
        send_eod_summary()
    else:
        run_scan()

    print("Done")

if __name__ == "__main__":
    main()
