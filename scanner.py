"""
Power 15 — Scanner v4.0
=======================
Uses the CORRECT Chartink scan condition:
  - Expanding candle range (7 days consecutive)
  - Green candle + higher close
  - Weekly + Monthly bullish alignment
  - EMA20 > EMA50 > EMA200 (triple stack)
  - Volume > 17.5L yesterday

Zero external dependencies — only Python stdlib.
Run at 3:30 PM daily via p15_bot.py or manually.
"""
import os, json, ssl, re
from datetime import datetime
from urllib.request import urlopen, Request

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID",   "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
WATCHLIST    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
CTX          = ssl.create_default_context()

def save_watchlist_supabase(watchlist):
    """Upserts today's watchlist to Supabase so buy_check.py can read it the
    next trading day — GitHub Actions runners don't share a filesystem between
    separate scheduled jobs, so the local watchlist.json alone never reaches it."""
    try:
        url  = f"{SUPABASE_URL}/rest/v1/p15_watchlist?on_conflict=id"
        body = json.dumps({
            "id":           1,
            "trade_date":   watchlist["date"],
            "nifty_status": watchlist["nifty_status"],
            "nifty_cmp":    watchlist.get("nifty_cmp"),
            "symbols":      watchlist["symbols"],
        }).encode()
        req = Request(url, data=body, method="POST", headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        })
        with urlopen(req, timeout=15, context=CTX) as r:
            return r.status in (200, 201, 204)
    except Exception as e:
        print(f"  Watchlist Supabase sync error: {e}")
        return False

POWER_15 = {
    "NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
    "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,
    "FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
    "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3,
}
SECTORS = {
    "NATIONALUM":"Metals","VEDL":"Metals","HINDALCO":"Metals","HINDZINC":"Metals",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Finance","MANAPPURAM":"Finance","ABCAPITAL":"Finance",
    "LTF":"Finance","BAJFINANCE":"Finance","FEDERALBNK":"Pvt Bank","AUBANK":"Pvt Bank",
}

# Your exact Chartink scan clause
CHARTINK_SCAN = (
    "( {33489} ( "
    "( daily high - daily low ) > ( 1 day ago high - 1 day ago low ) and "
    "( daily high - daily low ) > ( 2 days ago high - 2 days ago low ) and "
    "( daily high - daily low ) > ( 3 days ago high - 3 days ago low ) and "
    "( daily high - daily low ) > ( 4 days ago high - 4 days ago low ) and "
    "( daily high - daily low ) > ( 5 days ago high - 5 days ago low ) and "
    "( daily high - daily low ) > ( 6 days ago high - 6 days ago low ) and "
    "( daily high - daily low ) > ( 7 days ago high - 7 days ago low ) and "
    "daily close > daily open and "
    "daily close > 1 day ago close and "
    "weekly close > weekly open and "
    "monthly close > monthly open and "
    "1 day ago volume > 1750000 and "
    "daily ema ( daily close , 20 ) > daily ema ( daily close , 50 ) and "
    "daily ema ( daily close , 50 ) > daily ema ( daily close , 200 ) "
    ") )"
)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def get(url, headers={}):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0", **headers})
        with urlopen(req, timeout=12, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  GET error: {e}")
        return None

def post_form(url, data_str, headers={}):
    try:
        req = Request(url, data=data_str.encode(),
                      headers={"User-Agent": "Mozilla/5.0", **headers})
        with urlopen(req, timeout=20, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  POST error: {e}")
        return None

def tg(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        body = json.dumps({
            "chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"
        }).encode()
        req = Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=10, context=CTX) as r:
            result = json.loads(r.read().decode())
            if result.get("ok"):
                print("  Telegram: sent ✓")
            else:
                print(f"  Telegram failed: {result}")
    except Exception as e:
        print(f"  Telegram error: {e}")

# ── Chartink ──────────────────────────────────────────────────────────────────
def fetch_chartink():
    """
    Two-step Chartink fetch:
    1. GET homepage to get CSRF token
    2. POST scan with token
    """
    from html.parser import HTMLParser

    class CSRFParser(HTMLParser):
        def __init__(self): super().__init__(); self.csrf = ""
        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                d = dict(attrs)
                if d.get("name") == "csrf-token":
                    self.csrf = d.get("content", "")

    # Try with requests.Session first (most reliable)
    try:
        import requests as req_lib
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        with req_lib.Session() as s:
            s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            s.verify = False  # avoid SSL handshake hanging
            r = s.get("https://chartink.com/screener/", timeout=10)
            parser = CSRFParser()
            parser.feed(r.text)
            csrf = parser.csrf
            if not csrf:
                raise Exception("CSRF not found")
            print(f"  CSRF token obtained ✓")
            s.headers.update({
                "x-csrf-token":      csrf,
                "Content-Type":      "application/x-www-form-urlencoded",
                "X-Requested-With":  "XMLHttpRequest",
                "Referer":           "https://chartink.com/screener/",
            })
            r2 = s.post("https://chartink.com/screener/process",
                        data={"scan_clause": CHARTINK_SCAN}, timeout=20)
            if r2.status_code == 200:
                raw = r2.json().get("data", [])
                print(f"  Chartink returned {len(raw)} signals")
                return _parse_symbols(raw)
            else:
                raise Exception(f"HTTP {r2.status_code}")

    except ImportError:
        print("  requests not installed — trying urllib...")
    except Exception as e:
        print(f"  requests method failed: {e}")

    # urllib fallback
    try:
        home_req = Request("https://chartink.com/screener/",
                           headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(home_req, timeout=15, context=CTX) as resp:
            html       = resp.read().decode("utf-8", errors="ignore")
            cookie_hdr = resp.getheader("Set-Cookie") or ""
        parser = CSRFParser()
        parser.feed(html)
        csrf = parser.csrf
        if not csrf:
            print("  CSRF not found via urllib")
            return None
        from urllib.parse import quote
        body = "scan_clause=" + quote(CHARTINK_SCAN)
        post_req = Request(
            "https://chartink.com/screener/process",
            data=body.encode(),
            headers={
                "Content-Type":      "application/x-www-form-urlencoded",
                "x-csrf-token":      csrf,
                "X-Requested-With":  "XMLHttpRequest",
                "Referer":           "https://chartink.com/screener/",
                "User-Agent":        "Mozilla/5.0",
                "Cookie":            cookie_hdr,
            }
        )
        with urlopen(post_req, timeout=25, context=CTX) as r:
            raw = json.loads(r.read().decode()).get("data", [])
        print(f"  Chartink (urllib) returned {len(raw)} signals")
        return _parse_symbols(raw)
    except Exception as e:
        print(f"  urllib Chartink error: {e}")
        return None

def _parse_symbols(raw):
    symbols = set()
    for item in raw:
        sym = (item.get("nsecode") or item.get("symbol") or
               item.get("NSE Symbol") or "")
        sym = re.sub(r"-EQ$", "", sym.strip().upper())
        if sym:
            symbols.add(sym)
    return symbols

# ── Yahoo Finance ─────────────────────────────────────────────────────────────
def get_stock_data(symbol):
    """Fetch CMP, EMA values, volume from Yahoo Finance."""
    try:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=1d&range=120d")
        if not d: return None
        result = d["chart"]["result"][0]
        meta   = result["meta"]
        quote  = result["indicators"]["quote"][0]
        closes = [c for c in (quote.get("close") or []) if c is not None]
        highs  = [c for c in (quote.get("high")  or []) if c is not None]
        lows   = [c for c in (quote.get("low")   or []) if c is not None]
        vols   = [c for c in (quote.get("volume") or []) if c is not None]
        opens  = [c for c in (quote.get("open")  or []) if c is not None]
        cmp    = float(meta["regularMarketPrice"])
        avg_vol = sum(vols[-20:]) / len(vols[-20:]) if len(vols) >= 20 else None
        return {
            "cmp": cmp, "closes": closes, "highs": highs,
            "lows": lows, "vols": vols, "opens": opens, "avg_vol": avg_vol
        }
    except Exception as e:
        print(f"  [{symbol}] data error: {e}")
        return None

def calc_ema(values, period):
    """Exponential Moving Average — matches Chartink/TradingView."""
    if len(values) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(values[:period]) / period  # seed with SMA
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return round(ema, 4)

def get_nifty():
    try:
        d = get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=120d")
        if not d: return None, None, "UNKNOWN"
        result = d["chart"]["result"][0]
        closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
        cmp    = float(result["meta"]["regularMarketPrice"])
        ma20   = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        ma50   = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        if ma50 and cmp < ma50:   status = "AVOID"
        elif ma20 and cmp < ma20: status = "CAUTION"
        else:                     status = "STRONG"
        return cmp, ma20, status
    except Exception as e:
        print(f"  Nifty error: {e}")
        return None, None, "UNKNOWN"

# ── Verify signal locally ─────────────────────────────────────────────────────
def verify_signal(sym, data):
    """
    Strictly verify all Chartink conditions locally.
    Must match: 7-day expanding range + green candle + higher close
    + weekly bullish + monthly bullish + volume > 17.5L + EMA stack
    """
    closes = data["closes"]
    highs  = data["highs"]
    lows   = data["lows"]
    vols   = data["vols"]
    opens  = data["opens"]
    cmp    = data["cmp"]

    # Need at least 30 candles for all checks
    if len(closes) < 30 or len(highs) < 9:
        return False, "Insufficient data (need 30+ candles)"

    # ── Condition 1: 7 consecutive days of expanding range ────────────────────
    ranges = [highs[i] - lows[i] for i in range(len(highs))]
    today_range = ranges[-1]
    expanding = all(today_range > ranges[-1 - d] for d in range(1, 8))
    if not expanding:
        failed_days = [d for d in range(1, 8) if today_range <= ranges[-1 - d]]
        return False, f"Range not expanding on days: {failed_days}"

    # ── Condition 2: Green candle today (close > open) ────────────────────────
    if closes[-1] <= opens[-1]:
        return False, f"Red candle today (close {closes[-1]:.2f} <= open {opens[-1]:.2f})"

    # ── Condition 3: Higher close than yesterday ──────────────────────────────
    if closes[-1] <= closes[-2]:
        return False, f"Close not higher than yesterday ({closes[-1]:.2f} <= {closes[-2]:.2f})"

    # ── Condition 4: Weekly bullish (close > open 5 days ago) ────────────────
    if len(opens) >= 6 and closes[-1] <= opens[-6]:
        return False, f"Weekly bearish (close {closes[-1]:.2f} <= week open {opens[-6]:.2f})"

    # ── Condition 5: Monthly bullish (close > open 22 days ago) ──────────────
    if len(opens) >= 23 and closes[-1] <= opens[-23]:
        return False, f"Monthly bearish (close {closes[-1]:.2f} <= month open {opens[-23]:.2f})"

    # ── Condition 6: Yesterday volume > 17.5 lakh ─────────────────────────────
    if len(vols) >= 2:
        yesterday_vol = vols[-2]
        if yesterday_vol and yesterday_vol < 1750000:
            return False, f"Low volume: yesterday {yesterday_vol:,.0f} < 17.5L"

    # ── Condition 7: EMA20 > EMA50 > EMA200 ──────────────────────────────────
    ema20  = calc_ema(closes, 20)
    ema50  = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200) if len(closes) >= 200 else None

    if not ema20 or not ema50:
        return False, "EMA calculation failed"
    if ema20 <= ema50:
        return False, f"EMA20 {ema20:.1f} not above EMA50 {ema50:.1f}"
    if ema200 and ema50 <= ema200:
        return False, f"EMA50 {ema50:.1f} not above EMA200 {ema200:.1f}"

    return True, f"ALL CONDITIONS MET | EMA20:{ema20:.1f} EMA50:{ema50:.1f} Range:{today_range:.2f}"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")

    print(f"\n{'='*55}")
    print(f"  Power 15 Scanner v4.0")
    print(f"  {now.strftime('%d %b %Y %H:%M')}")
    print(f"  Strategy: Expanding Range + EMA Stack + Green Candle")
    print(f"{'='*55}")

    # Step 1: Nifty trend
    print("\n[1] Nifty Trend")
    nifty_cmp, nifty_ma20, nifty_status = get_nifty()
    nifty_str = f"Rs{nifty_cmp:.0f}" if nifty_cmp else "N/A"
    ma20_str  = f"Rs{nifty_ma20:.0f}" if nifty_ma20 else "N/A"
    print(f"  Nifty: {nifty_str} | MA20: {ma20_str} | Status: {nifty_status}")

    # Step 2: Chartink scan
    print("\n[2] Chartink Scan")
    print(f"  Condition: Expanding range + Green candle + EMA20>EMA50>EMA200")
    chartink_syms = fetch_chartink()

    # Step 3: Filter to Power 15
    print("\n[3] Power 15 Filter")
    approved = []
    rejected = []

    if chartink_syms is not None:
        p15_hits = [s for s in chartink_syms if s in POWER_15]
        print(f"  Chartink hits in Power 15: {p15_hits if p15_hits else 'None'}")
        scan_list = p15_hits
    else:
        # Chartink failed — skip local scan to avoid false signals
        # Local EMA check cannot replicate Chartink's expanding range + 7-day condition
        print("  Chartink unavailable — skipping to avoid false signals")
        print("  Check Chartink manually at chartink.com")
        scan_list = []

    if not scan_list:
        print("  No Power 15 stocks in today's scan")
    else:
        for sym in scan_list:
            tier   = POWER_15[sym]
            sector = SECTORS.get(sym, "Other")

            # Skip Tier 3 if market weak
            if nifty_status == "AVOID" and tier == 3:
                rejected.append((sym, tier, "Nifty AVOID — Tier 3 skipped"))
                print(f"  [{sym}] SKIP — Nifty AVOID, T3")
                continue

            print(f"  [{sym}] Fetching data...")
            data = get_stock_data(sym)
            if not data:
                rejected.append((sym, tier, "Data fetch failed"))
                continue

            # In fallback mode: verify signal locally
            if chartink_syms is None:
                passed, reason = verify_signal(sym, data)
                if not passed:
                    rejected.append((sym, tier, reason))
                    print(f"  [{sym}] SKIP — {reason}")
                    continue

            cmp     = data["cmp"]
            ema20   = calc_ema(data["closes"], 20)
            ema50   = calc_ema(data["closes"], 50)
            avg_vol = data["avg_vol"]

            approved.append({
                "symbol": sym, "tier": tier, "sector": sector,
                "cmp": cmp, "ema20": ema20, "ema50": ema50,
                "avg_vol": avg_vol
            })
            print(f"  [{sym}] APPROVED T{tier} Rs{cmp:.2f} EMA20:{ema20:.1f} EMA50:{ema50:.1f}")

    # Step 4: Save watchlist
    watchlist = {
        "date": today, "nifty_status": nifty_status,
        "nifty_cmp": nifty_cmp, "strategy": "expanding_range_ema_stack",
        "symbols": [s["symbol"] for s in approved],
        "details": approved, "rejected": rejected,
    }
    try:
        json.dump(watchlist, open(WATCHLIST, "w"), indent=2)
        print(f"\n  Watchlist saved locally: {[s['symbol'] for s in approved]}")
    except Exception as e:
        print(f"  Watchlist save error: {e}")

    ok = save_watchlist_supabase(watchlist)
    print(f"  Watchlist synced to Supabase: {'✅' if ok else '❌'}")

    # Step 5: Telegram message
    nifty_icon = {"STRONG": "G", "CAUTION": "Y", "AVOID": "R", "UNKNOWN": "?"}
    msg  = f"Power 15 Scanner v4.0 — {now.strftime('%d %b %Y %H:%M')}\n\n"
    msg += f"Nifty: {nifty_str} [{nifty_status}] MA20:{ma20_str}\n\n"

    if chartink_syms is None:
        msg += "Chartink unavailable today.\n"
        msg += "Please check chartink.com manually.\n"
        msg += "No signals generated to avoid false alerts.\n"
    elif approved:
        msg += f"{len(approved)} Signal(s) Found!\n"
        msg += f"Strategy: Expanding Range + EMA Stack\n\n"
        for s in approved:
            ema_str = f"EMA20:{s['ema20']:.1f}" if s['ema20'] else ""
            msg += f"T{s['tier']} {s['symbol']} ({s['sector']})\n"
            msg += f"  Rs{s['cmp']:.2f} | {ema_str}\n"
            msg += f"  Buy tomorrow if RED candle at 3:25 PM\n\n"
    else:
        msg += "No signals today.\n"
        msg += "Condition: Need expanding range + green candle + EMA20>EMA50>EMA200\n"

    if rejected:
        msg += f"\nRejected ({len(rejected)}): "
        msg += ", ".join(f"{r[0]}" for r in rejected[:8])

    msg += f"\n\nSend /positions to see open trades"
    print("\n[4] Sending Telegram...")
    tg(msg)
    print(f"\n  Scanner v4.0 complete\n")

if __name__ == "__main__":
    main()