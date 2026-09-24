"""
Power 15 — VCP Strategy Scanner v1.0
======================================
Volatility Contraction Pattern (Mark Minervini method)
- Scans 20 NSE equity stocks on DAILY candles
- Scans Gold, Silver, Crude on MCX (via international proxies)
- Detects C3-FORMING and BREAKOUT stages
- Scores each setup 0-8
- Writes signals to Supabase: vcp_signals table
- Opens paper trades automatically on BREAKOUT signals
- Monitors open trades: SL / T1 / T2 / trailing stop
- Sends Telegram alerts for every event
- Sends EOD summary at 3:35 PM

Run modes:
  python vcp_scanner.py           → full VCP scan (every 30 min via cron)
  python vcp_scanner.py --monitor → check exits on open trades (every 15 min)
  python vcp_scanner.py --eod     → send end-of-day summary (3:35 PM)
"""
import os, sys, json, ssl
from datetime import datetime, date, timedelta
from urllib.request import urlopen, Request

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPA_URL  = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPA_KEY  = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
CTX       = ssl.create_default_context()

# ── Strategy Config ────────────────────────────────────────────────────────────
CAPITAL_PER_TRADE  = 20000   # Rs 20,000 per equity trade
MAX_OPEN_TRADES    = 5       # max simultaneous VCP trades
MIN_SCORE          = 5       # minimum score to open a trade (out of 8)
SL_BUFFER          = 0.01    # 1% below C3 low for stop loss
T1_PCT             = 0.08    # +8% target 1
T2_PCT             = 0.15    # +15% target 2
TRAIL_TRIGGER_PCT  = 0.08    # start trailing after +8%
TRAIL_SL_PCT       = 0.04    # trail SL 4% below peak
MAX_HOLD_DAYS      = 30      # force exit after 30 days

# ── Stock Universe ─────────────────────────────────────────────────────────────
VCP_EQ_STOCKS = {
    # Banking & Finance
    "HDFCBANK":   "Banking",
    "ICICIBANK":  "Banking",
    "KOTAKBANK":  "Banking",
    "BAJFINANCE": "Finance",
    # Capital Markets
    "BSE":        "Capital Mkts",
    "ANGELONE":   "Capital Mkts",
    "MUTHOOTFIN": "Finance",
    # Defence & Capital Goods
    "BEL":        "Defence",
    "HAL":        "Defence",
    "SIEMENS":    "Capital Goods",
    # IT
    "INFY":       "IT",
    "LTIM":       "IT",
    "COFORGE":    "IT",
    # Pharma
    "SUNPHARMA":  "Pharma",
    "DIVISLAB":   "Pharma",
    "APOLLOHOSP": "Healthcare",
    # Metals
    "TATASTEEL":  "Metals",
    "JSWSTEEL":   "Metals",
    "HINDALCO":   "Metals",
    # Energy
    "RELIANCE":   "Energy",
}

VCP_COM_STOCKS = {
    "GOLD":     {"yahoo": "GC=F",  "sector": "Bullion",  "capital": 50000},
    "SILVER":   {"yahoo": "SI=F",  "sector": "Bullion",  "capital": 50000},
    "CRUDEOIL": {"yahoo": "CL=F",  "sector": "Energy",   "capital": 30000},
}

# ── HTTP Helpers ───────────────────────────────────────────────────────────────
SHDRS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

def http_get(url, headers={}):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0", **headers})
        with urlopen(req, timeout=14, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return None

def http_post(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        req  = Request(url, data=body, headers={"Content-Type":"application/json", **headers})
        with urlopen(req, timeout=12, context=CTX) as r:
            return json.loads(r.read().decode())
    except: return None

def http_patch(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        h    = {"Content-Type":"application/json","Prefer":"return=minimal",**SHDRS,**headers}
        req  = Request(url, data=body, headers=h, method="PATCH")
        with urlopen(req, timeout=12, context=CTX) as r:
            return r.status
    except: return None

def tg(msg):
    http_post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    )

def supa_get(table, query=""):
    """Returns None on a genuine connection/HTTP failure, [] only for a real
    empty result — so a Supabase outage never gets mistaken for "nothing to do"."""
    result = http_get(f"{SUPA_URL}/rest/v1/{table}?{query}", SHDRS)
    return result if isinstance(result, list) else None

def supa_post(table, data):
    h = {**SHDRS, "Content-Type":"application/json", "Prefer":"return=representation"}
    return http_post(f"{SUPA_URL}/rest/v1/{table}", data, h)

def supa_patch(table, query, data):
    return http_patch(f"{SUPA_URL}/rest/v1/{table}?{query}", data)

def log(msg):
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fi(v, signed=False):
    s = ("+" if v >= 0 else "-") if signed else ("-" if v < 0 else "")
    v = abs(v)
    if v >= 1e7:   r = f"Rs{v/1e7:.2f}Cr"
    elif v >= 1e5: r = f"Rs{v/1e5:.1f}L"
    elif v >= 1e3: r = f"Rs{v/1e3:.1f}K"
    else:          r = f"Rs{v:.0f}"
    return s + r

# ── EMA Calculation ────────────────────────────────────────────────────────────
def calc_ema(values, period):
    if len(values) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return round(ema, 4)

# ── Fetch Daily OHLCV ──────────────────────────────────────────────────────────
def get_daily_data(symbol, suffix=".NS", range_="90d"):
    d = http_get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}{suffix}"
        f"?interval=1d&range={range_}"
    )
    if not d:
        return None
    try:
        result  = d["chart"]["result"][0]
        q       = result["indicators"]["quote"][0]
        ts      = result["timestamp"]
        closes  = q.get("close",  [])
        highs   = q.get("high",   [])
        lows    = q.get("low",    [])
        opens   = q.get("open",   [])
        vols    = q.get("volume", [])
        cmp     = float(result["meta"]["regularMarketPrice"])

        candles = []
        for i in range(len(closes)):
            if all(x is not None for x in [closes[i], highs[i], lows[i], opens[i]]):
                candles.append({
                    "ts": ts[i], "o": opens[i], "h": highs[i],
                    "l": lows[i], "c": closes[i], "v": vols[i] or 0
                })
        return {"candles": candles, "cmp": cmp}
    except:
        return None

def get_cmp(symbol, suffix=".NS"):
    d = http_get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}{suffix}?interval=1d&range=2d"
    )
    if not d:
        return None
    try:
        return float(d["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

# ── Swing High/Low Detection ───────────────────────────────────────────────────
def find_swings(candles, window=3):
    """Find swing highs and lows using a rolling window."""
    swings = []
    highs  = [c["h"] for c in candles]
    lows   = [c["l"] for c in candles]
    for i in range(window, len(candles) - window):
        # Swing high: higher than all surrounding candles
        if highs[i] == max(highs[i-window:i+window+1]):
            swings.append({"type": "H", "idx": i, "val": highs[i]})
        # Swing low: lower than all surrounding candles
        elif lows[i] == min(lows[i-window:i+window+1]):
            swings.append({"type": "L", "idx": i, "val": lows[i]})
    return swings

def find_pullbacks(swings):
    """Extract High→Low pullback percentages."""
    pullbacks = []
    for j in range(len(swings) - 1):
        if swings[j]["type"] == "H" and swings[j+1]["type"] == "L":
            hi  = swings[j]["val"]
            lo  = swings[j+1]["val"]
            pct = (hi - lo) / hi * 100
            pullbacks.append({
                "hi": hi, "lo": lo, "pct": round(pct, 2),
                "hi_idx": swings[j]["idx"], "lo_idx": swings[j+1]["idx"]
            })
    return pullbacks

# ── Demand/Supply Zone Detection ───────────────────────────────────────────────
def find_demand_zone(candles):
    """
    Find the most recent strong demand zone:
    A zone where price bounced sharply with high volume.
    Returns (zone_low, zone_high) or None.
    """
    if len(candles) < 20:
        return None
    closes = [c["c"] for c in candles]
    vols   = [c["v"] for c in candles]
    avg_vol= sum(vols[-30:])/30 if len(vols)>=30 else sum(vols)/len(vols)

    # Look for strong up-candles with above-avg volume in the last 60 days
    zones = []
    for i in range(2, min(60, len(candles))-2):
        c = candles[-(i+1)]   # candle from the past
        nxt= candles[-i]
        # Big green candle with strong volume = demand zone base
        body_pct = (c["c"] - c["o"]) / c["o"] * 100 if c["o"] > 0 else 0
        if body_pct > 1.5 and c["v"] > avg_vol * 1.3:
            zones.append({"lo": c["l"], "hi": c["h"], "idx": i, "strength": c["v"]/avg_vol})

    if not zones:
        return None
    # Return strongest zone
    best = max(zones, key=lambda z: z["strength"])
    return {"lo": best["lo"], "hi": best["hi"]}

# ── VCP Pattern Detection ──────────────────────────────────────────────────────
def detect_vcp(symbol, is_commodity=False):
    """
    Full VCP detection with Minervini scoring.
    Returns signal dict (score 0-8) or None if no pattern.
    """
    if is_commodity:
        cfg    = VCP_COM_STOCKS.get(symbol, {})
        suffix = ""
        sym_fetch = cfg.get("yahoo", symbol)
    else:
        suffix    = ".NS"
        sym_fetch = symbol

    data = get_daily_data(sym_fetch, suffix=suffix, range_="120d")
    if not data or len(data["candles"]) < 40:
        return None

    candles = data["candles"]
    closes  = [c["c"] for c in candles]
    vols    = [c["v"] for c in candles]
    cmp     = data["cmp"]

    # ── Step 1: Trend template (must be in uptrend) ──────────────────────────
    if len(closes) < 50:
        return None
    ma20  = sum(closes[-20:]) / 20
    ma50  = sum(closes[-50:]) / 50
    ma200 = sum(closes[-min(200,len(closes)):]) / min(200, len(closes))
    # Price must be above MA50; MA50 above MA200 is bonus
    if cmp < ma50:
        return None  # not in uptrend — skip

    # ── Step 2: Find swing highs/lows ────────────────────────────────────────
    swings   = find_swings(candles, window=3)
    pullbacks= find_pullbacks(swings)
    if len(pullbacks) < 2:
        return None

    # Use last 2-4 pullbacks
    recent = pullbacks[-4:] if len(pullbacks) >= 4 else pullbacks[-2:]

    # ── Step 3: Contracting pullbacks check ──────────────────────────────────
    contracting = all(
        recent[i]["pct"] > recent[i+1]["pct"]
        for i in range(len(recent)-1)
    )
    if not contracting:
        return None

    # Must be genuine contraction (not random noise)
    if recent[-1]["pct"] < 0.5:  # Too tight — may be noise
        return None

    # ── Step 4: Scoring (0-8) ────────────────────────────────────────────────
    score = 0

    # Score 1-2: Number of contractions
    c_count = len(recent)
    if c_count >= 3:   score += 2
    elif c_count == 2: score += 1

    # Score 3-4: Volume dry-up on C3 (last 5 days)
    avg20 = sum(vols[-20:]) / 20 if len(vols) >= 20 else 1
    avg5  = sum(vols[-5:])  / 5  if len(vols) >= 5  else 1
    vol_dry = avg5 < avg20 * 0.8
    if vol_dry: score += 2

    # Score 5: Final contraction is tight (< 6%)
    if recent[-1]["pct"] < 6:   score += 2
    elif recent[-1]["pct"] < 10: score += 1

    # Score 6: Price above MA50 (trend confirmation)
    above_ma50 = cmp > ma50
    if above_ma50: score += 1

    # Score 7: MA20 trending up (momentum)
    ma20_now  = sum(closes[-20:]) / 20
    ma20_prev = sum(closes[-30:-10]) / 20
    if ma20_now > ma20_prev: score += 1

    # ── Step 5: Determine stage ───────────────────────────────────────────────
    pivot = recent[-1]["hi"]   # last swing high = breakout level
    sl    = round(recent[-1]["lo"] * (1 - SL_BUFFER), 2)

    # Base duration check: base should be 15-50 days
    if recent:
        base_start = recent[0]["hi_idx"]
        base_end   = len(candles) - 1
        base_days  = base_end - base_start
    else:
        base_days = 0

    if base_days < 10 or base_days > 60:
        return None  # too short or too long a base

    # Stage: BREAKOUT if CMP closed above pivot; C3-FORMING otherwise
    stage = "BREAKOUT" if cmp > pivot * 1.002 else "C3-FORMING"

    # Demand zone
    dz = find_demand_zone(candles)

    # Target prices
    t1 = round(pivot * (1 + T1_PCT), 2)
    t2 = round(pivot * (1 + T2_PCT), 2)

    return {
        "symbol":       symbol,
        "sector":       VCP_EQ_STOCKS.get(symbol, VCP_COM_STOCKS.get(symbol, {}).get("sector","—")),
        "market":       "COMMODITY" if is_commodity else "EQUITY",
        "cmp":          round(cmp, 2),
        "score":        score,
        "max_score":    8,
        "contractions": c_count,
        "c_pcts":       [r["pct"] for r in recent],
        "pivot":        round(pivot, 2),
        "sl_price":     sl,
        "target1":      t1,
        "target2":      t2,
        "vol_dry":      vol_dry,
        "above_ma50":   above_ma50,
        "stage":        stage,
        "base_days":    base_days,
        "demand_zone":  dz,
        "yahoo_sym":    sym_fetch + suffix,
    }

# ── Capital Management ─────────────────────────────────────────────────────────
def get_vcp_capital():
    """Returns None on a genuine Supabase failure — deliberately does NOT fall
    back to a fake default balance, since that could make a transient outage
    look like a fresh Rs3,00,000 account and risk over-allocating capital
    that's already invested."""
    rows = supa_get("vcp_capital", "select=*&limit=1")
    if rows is None:
        return None
    return rows[0] if rows else {"id":1,"initial":300000,"available":300000,"invested":0,
            "total_pnl":0,"total_trades":0,"winning_trades":0}

def update_vcp_capital(cap_id, data):
    supa_patch("vcp_capital", f"id=eq.{cap_id}", data)

def get_open_vcp_trades():
    return supa_get("vcp_trades", "status=eq.OPEN&select=*")

def get_today_signals():
    today = date.today().strftime("%Y-%m-%d")
    return supa_get("vcp_signals", f"signal_date=eq.{today}&select=*")

# ── Open a Paper Trade ─────────────────────────────────────────────────────────
def open_vcp_trade(sig, signal_id=None):
    """Open a paper trade for a VCP breakout signal."""
    cap = get_vcp_capital()
    if cap is None:
        log(f"Supabase unreachable — skipping {sig['symbol']} entry")
        return None
    price = sig["cmp"]

    # Capital allocation
    alloc = CAPITAL_PER_TRADE if sig["market"] == "EQUITY" else \
            VCP_COM_STOCKS.get(sig["symbol"], {}).get("capital", 30000)

    if cap["available"] < alloc:
        log(f"Insufficient capital for {sig['symbol']} — skipping")
        return None

    qty = max(1, int(alloc / price))
    invested = round(qty * price, 2)

    record = {
        "signal_id":    signal_id,
        "symbol":       sig["symbol"],
        "sector":       sig["sector"],
        "market":       sig["market"],
        "entry_date":   date.today().strftime("%Y-%m-%d"),
        "entry_time":   datetime.now().strftime("%H:%M:%S"),
        "entry_price":  price,
        "quantity":     qty,
        "sl_price":     sig["sl_price"],
        "target1":      sig["target1"],
        "target2":      sig["target2"],
        "peak_cmp":     price,
        "status":       "OPEN",
        "pnl":          0,
        "pnl_pct":      0,
        "score":        sig["score"],
        "vcp_stage":    sig["stage"],
    }

    result = supa_post("vcp_trades", record)

    # Update capital
    new_available = round(cap["available"] - invested, 2)
    new_invested  = round(cap["invested"]  + invested, 2)
    update_vcp_capital(cap["id"], {
        "available": new_available,
        "invested":  new_invested
    })

    log(f"TRADE OPENED: {sig['symbol']} @ Rs{price:.2f} x{qty} | Invested: {fi(invested)}")
    return result

# ── Close a Paper Trade ────────────────────────────────────────────────────────
def close_vcp_trade(trade, exit_price, reason):
    """Close a paper trade and update capital."""
    pnl     = round((exit_price - trade["entry_price"]) * trade["quantity"], 2)
    pnl_pct = round((exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 4)
    invested= round(trade["entry_price"] * trade["quantity"], 2)
    returned= round(exit_price * trade["quantity"], 2)

    supa_patch("vcp_trades", f"id=eq.{trade['id']}", {
        "status":       "CLOSED",
        "exit_date":    date.today().strftime("%Y-%m-%d"),
        "exit_time":    datetime.now().strftime("%H:%M:%S"),
        "exit_price":   round(exit_price, 2),
        "pnl":          pnl,
        "pnl_pct":      pnl_pct,
        "exit_reason":  reason,
    })

    cap = get_vcp_capital()
    if cap is None:
        log(f"Supabase unreachable — {trade['symbol']} closed but capital not updated")
        return pnl
    is_win = pnl > 0
    update_vcp_capital(cap["id"], {
        "available":      round(cap["available"] + returned, 2),
        "invested":       round(max(0, cap["invested"] - invested), 2),
        "total_pnl":      round(cap["total_pnl"] + pnl, 2),
        "total_trades":   cap["total_trades"] + 1,
        "winning_trades": cap["winning_trades"] + (1 if is_win else 0),
    })

    log(f"TRADE CLOSED: {trade['symbol']} @ Rs{exit_price:.2f} | P&L: {fi(pnl,True)} ({pnl_pct:+.2f}%) | {reason}")
    return pnl

# ── Monitor Open Trades ────────────────────────────────────────────────────────
def monitor_open_trades():
    """Check all open VCP trades for SL / T1 / T2 / trailing / max hold."""
    trades = get_open_vcp_trades()
    if trades is None:
        log("Supabase unreachable — skipping trade monitor")
        return
    if not trades:
        return

    for t in trades:
        sym    = t["symbol"]
        suffix = "" if t["market"] == "COMMODITY" else ".NS"
        yf_sym = VCP_COM_STOCKS.get(sym, {}).get("yahoo", sym) if t["market"] == "COMMODITY" else sym

        cmp = get_cmp(yf_sym, suffix=suffix)
        if cmp is None:
            continue

        entry  = t["entry_price"]
        sl     = t["sl_price"]
        t1     = t["target1"]
        t2     = t["target2"]
        peak   = t.get("peak_cmp") or cmp
        pnl    = (cmp - entry) * t["quantity"]
        pct    = (cmp - entry) / entry * 100

        # Update peak CMP
        if cmp > peak:
            peak = cmp
            supa_patch("vcp_trades", f"id=eq.{t['id']}", {"peak_cmp": round(peak, 2)})

        # Trailing stop calculation
        peak_pct = (peak - entry) / entry * 100
        trail_sl = round(peak * (1 - TRAIL_SL_PCT), 2) if peak_pct >= TRAIL_TRIGGER_PCT * 100 else None

        # Entry date for max hold check
        try:
            entry_date = datetime.strptime(t["entry_date"], "%Y-%m-%d").date()
            hold_days  = (date.today() - entry_date).days
        except:
            hold_days  = 0

        # ── Exit checks ──────────────────────────────────────────────────────
        exit_price  = None
        exit_reason = None

        # 1. Stop Loss
        if cmp <= sl:
            exit_price  = cmp
            exit_reason = f"Stop Loss hit @ Rs{cmp:.2f}"

        # 2. Trailing Stop (after T1 trigger)
        elif trail_sl and cmp <= trail_sl and t.get("t1_hit"):
            exit_price  = cmp
            exit_reason = f"Trailing SL @ Rs{cmp:.2f} (peak Rs{peak:.2f})"

        # 3. Target 2 — full exit
        elif cmp >= t2:
            exit_price  = cmp
            exit_reason = f"Target 2 hit @ Rs{cmp:.2f} (+{T2_PCT*100:.0f}%)"

        # 4. Max hold period
        elif hold_days >= MAX_HOLD_DAYS:
            exit_price  = cmp
            exit_reason = f"Max hold ({MAX_HOLD_DAYS}d) @ Rs{cmp:.2f}"

        if exit_price:
            trade_pnl = close_vcp_trade(t, exit_price, exit_reason)
            icon = "✅" if trade_pnl >= 0 else "❌"
            tg(f"{icon} <b>VCP Strategy — Trade Closed</b>\n\n"
               f"📌 <b>{sym}</b> ({t.get('sector','—')})\n\n"
               f"Entry:  Rs{entry:.2f}\n"
               f"Exit:   Rs{exit_price:.2f}\n"
               f"P&L:    <b>{fi(trade_pnl, True)} ({pct:+.2f}%)</b>\n"
               f"Reason: {exit_reason}\n"
               f"Hold:   {hold_days} days")
            continue

        # 5. Target 1 hit — alert only (book 50% manually or log flag)
        if cmp >= t1 and not t.get("t1_hit"):
            supa_patch("vcp_trades", f"id=eq.{t['id']}", {"t1_hit": True})
            tg(f"🎯 <b>VCP Strategy — Target 1 Hit!</b>\n\n"
               f"📌 <b>{sym}</b>\n"
               f"CMP: Rs{cmp:.2f} | T1: Rs{t1:.2f}\n"
               f"P&L so far: <b>{fi(pnl, True)} ({pct:+.2f}%)</b>\n"
               f"Consider booking 50% here.\n"
               f"Trailing SL now active at Rs{trail_sl:.2f}" if trail_sl else "")

# ── Save Signal to Supabase ────────────────────────────────────────────────────
def save_signal(sig):
    """Write a VCP signal to vcp_signals table. Returns the inserted id."""
    record = {
        "signal_date":  date.today().strftime("%Y-%m-%d"),
        "signal_time":  datetime.now().strftime("%H:%M:%S"),
        "symbol":       sig["symbol"],
        "sector":       sig["sector"],
        "market":       sig["market"],
        "stage":        sig["stage"],
        "score":        sig["score"],
        "max_score":    8,
        "cmp":          sig["cmp"],
        "pivot":        sig["pivot"],
        "sl_price":     sig["sl_price"],
        "target1":      sig["target1"],
        "target2":      sig["target2"],
        "contractions": sig["contractions"],
        "c_pcts":       json.dumps(sig["c_pcts"]),
        "vol_dry":      sig["vol_dry"],
        "above_ma50":   sig["above_ma50"],
        "acted_upon":   False,
    }
    result = supa_post("vcp_signals", record)
    if result and isinstance(result, list) and len(result) > 0:
        return result[0].get("id")
    return None

def signal_already_sent_today(symbol, stage):
    """Avoid duplicate alerts for the same symbol+stage on the same day.
    Fails safe: an unreadable result counts as "already sent" — a missed
    alert is a lot cheaper than a spam duplicate."""
    today   = date.today().strftime("%Y-%m-%d")
    results = supa_get("vcp_signals",
                       f"signal_date=eq.{today}&symbol=eq.{symbol}&stage=eq.{stage}&select=id")
    if results is None:
        return True
    return len(results) > 0

def trade_already_open(symbol):
    """Check if there's already an open trade for this symbol. Fails safe:
    an unreadable result counts as "already open" — never risk a duplicate
    position because Supabase hiccupped."""
    trades = supa_get("vcp_trades",
                      f"symbol=eq.{symbol}&status=eq.OPEN&select=id")
    if trades is None:
        return True
    return len(trades) > 0

# ── Scan All Stocks ────────────────────────────────────────────────────────────
def run_scan():
    """Main scan: detect VCP signals on all stocks."""
    log("=" * 55)
    log(f"Starting VCP scan — {datetime.now().strftime('%d %b %Y %H:%M:%S')}")

    open_trades = get_open_vcp_trades()
    if open_trades is None:
        log("Supabase unreachable — aborting scan")
        return []
    open_count    = len(open_trades)
    open_symbols  = {t["symbol"] for t in open_trades}
    new_signals   = []
    new_breakouts = []

    all_stocks = list(VCP_EQ_STOCKS.keys())
    com_stocks = list(VCP_COM_STOCKS.keys())

    log(f"Scanning {len(all_stocks)} equity + {len(com_stocks)} commodity stocks...")

    for sym in all_stocks:
        try:
            sig = detect_vcp(sym, is_commodity=False)
            if not sig:
                continue
            if sig["score"] < MIN_SCORE:
                log(f"  {sym}: score {sig['score']}/8 — below threshold, skipping")
                continue

            log(f"  {sym}: {sig['stage']} score={sig['score']}/8 CMP=Rs{sig['cmp']:.2f} pivot=Rs{sig['pivot']:.2f}")

            # Save signal if not already sent today
            if not signal_already_sent_today(sym, sig["stage"]):
                signal_id = save_signal(sig)
                new_signals.append(sig)

                # Send Telegram alert
                contr_str = " → ".join([f"{p:.1f}%" for p in sig["c_pcts"]])
                dz_str    = f"Demand zone: Rs{sig['demand_zone']['lo']:.2f}–Rs{sig['demand_zone']['hi']:.2f}" if sig.get("demand_zone") else ""

                if sig["stage"] == "C3-FORMING":
                    tg(f"🔍 <b>VCP — C3 Forming!</b>\n\n"
                       f"📌 <b>{sym}</b> ({sig['sector']})\n"
                       f"Score: {sig['score']}/8 | Base: {sig['base_days']}d\n\n"
                       f"CMP:    Rs{sig['cmp']:.2f}\n"
                       f"Pivot:  Rs{sig['pivot']:.2f}  ← watch this level\n"
                       f"SL:     Rs{sig['sl_price']:.2f}\n"
                       f"T1/T2:  Rs{sig['t1']:.2f} / Rs{sig['t2']:.2f}\n\n"
                       f"Contractions: {contr_str}\n"
                       f"{'💧 Vol drying up' if sig['vol_dry'] else ''} {'📈 Above MA50' if sig['above_ma50'] else ''}\n"
                       f"{dz_str}\n\n"
                       f"<i>Wait for breakout above Rs{sig['pivot']:.2f} on 1.5x volume</i>")

                elif sig["stage"] == "BREAKOUT":
                    new_breakouts.append((sig, signal_id))
                    tg(f"🚀 <b>VCP — BREAKOUT!</b>\n\n"
                       f"📌 <b>{sym}</b> ({sig['sector']})\n"
                       f"Score: {sig['score']}/8 | Base: {sig['base_days']}d\n\n"
                       f"Entry:  Rs{sig['cmp']:.2f}  ← BUY NOW\n"
                       f"SL:     Rs{sig['sl_price']:.2f} ({((sig['sl_price']-sig['cmp'])/sig['cmp']*100):.1f}%)\n"
                       f"T1:     Rs{sig['target1']:.2f} (+{T1_PCT*100:.0f}%)\n"
                       f"T2:     Rs{sig['target2']:.2f} (+{T2_PCT*100:.0f}%)\n\n"
                       f"Contractions: {contr_str}\n"
                       f"{'💧 Vol dry' if sig['vol_dry'] else ''} {'📈 Above MA50' if sig['above_ma50'] else ''}\n"
                       f"{dz_str}\n\n"
                       f"<i>Paper trade auto-opening...</i>")

        except Exception as e:
            log(f"  {sym}: ERROR — {e}")

    # Commodity scan
    for sym in com_stocks:
        try:
            sig = detect_vcp(sym, is_commodity=True)
            if not sig or sig["score"] < (MIN_SCORE - 1):
                continue
            log(f"  {sym}[COM]: {sig['stage']} score={sig['score']}/8 CMP=Rs{sig['cmp']:.0f}")
            if not signal_already_sent_today(sym, sig["stage"]):
                signal_id = save_signal(sig)
                new_signals.append(sig)
                if sig["stage"] == "BREAKOUT":
                    new_breakouts.append((sig, signal_id))
                    tg(f"🚀 <b>VCP COMMODITY — BREAKOUT!</b>\n\n"
                       f"📌 <b>{sym}</b> (MCX)\n"
                       f"Score: {sig['score']}/8\n\n"
                       f"CMP:    Rs{sig['cmp']:.0f}\n"
                       f"Pivot:  Rs{sig['pivot']:.0f}\n"
                       f"SL:     Rs{sig['sl_price']:.0f}\n"
                       f"T1:     +{T1_PCT*100:.0f}% | T2: +{T2_PCT*100:.0f}%\n\n"
                       f"<b>Options Play:</b> Buy ATM Call, 15-21 days expiry\n"
                       f"<i>Paper signal logged.</i>")
        except Exception as e:
            log(f"  {sym}[COM]: ERROR — {e}")

    # Auto-open paper trades for breakout signals
    for (sig, signal_id) in new_breakouts:
        if open_count >= MAX_OPEN_TRADES:
            log(f"Max trades reached — not opening {sig['symbol']}")
            break
        if trade_already_open(sig["symbol"]):
            log(f"{sig['symbol']} already has an open trade — skipping")
            continue
        result = open_vcp_trade(sig, signal_id)
        if result:
            # Mark signal as acted upon
            if signal_id:
                supa_patch("vcp_signals", f"id=eq.{signal_id}", {"acted_upon": True})
            open_count += 1

    log(f"Scan complete — {len(new_signals)} new signals, {len(new_breakouts)} breakouts, {open_count} open trades")
    return new_signals

# ── EOD Summary ────────────────────────────────────────────────────────────────
def send_eod_summary():
    """Send VCP strategy EOD summary on Telegram."""
    today  = date.today().strftime("%Y-%m-%d")
    trades = supa_get("vcp_trades", f"entry_date=eq.{today}&select=*")
    cap    = get_vcp_capital()
    all_signals = supa_get("vcp_signals", f"signal_date=eq.{today}&select=*")

    if trades is None or cap is None or all_signals is None:
        log("Supabase unreachable — skipping EOD summary")
        return

    eq_sigs  = [s for s in all_signals if s.get("market") == "EQUITY"]
    com_sigs = [s for s in all_signals if s.get("market") == "COMMODITY"]

    open_trades = get_open_vcp_trades()

    msg  = f"📊 <b>VCP Strategy — EOD {datetime.now().strftime('%d %b %Y')}</b>\n\n"
    msg += f"💼 Capital: {fi(cap['available'])} available | {fi(cap['invested'])} invested\n"
    msg += f"📈 Total P&L: <b>{fi(cap['total_pnl'], True)}</b>\n"
    msg += f"🏆 Win Rate: {cap['winning_trades']}/{cap['total_trades']}\n\n"

    if trades:
        msg += "📋 <b>Today's Trades:</b>\n"
        for t in trades:
            ep   = t.get("exit_price", t["entry_price"])
            pnl  = (ep - t["entry_price"]) * t["quantity"]
            icon = "✅" if pnl >= 0 else "❌"
            st   = "OPEN" if t["status"] == "OPEN" else f"CLOSED {fi(pnl, True)}"
            msg += f"{icon} {t['symbol']}: {st}\n"
    else:
        msg += "No trades today.\n"

    msg += f"\n🔍 Signals today: {len(eq_sigs)} equity, {len(com_sigs)} commodity\n"
    if open_trades:
        msg += f"📂 Open positions: {', '.join(t['symbol'] for t in open_trades)}\n"

    tg(msg)
    log("EOD summary sent")

# ── Entry ──────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    mode = "scan"
    if "--monitor" in sys.argv: mode = "monitor"
    elif "--eod" in sys.argv:   mode = "eod"

    print(f"[VCP Scanner — {mode} — {datetime.now().strftime('%d %b %Y %H:%M:%S')}]")

    if mode == "monitor":
        monitor_open_trades()
    elif mode == "eod":
        send_eod_summary()
    else:
        run_scan()

    print("Done")

if __name__ == "__main__":
    main()
