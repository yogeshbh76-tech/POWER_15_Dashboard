"""
Power 15 — Sell Alert v3.0 — Option B Exit Strategy
=====================================================
T1: +20% → sell 50% quantity
T2: +30% → sell remaining 50% (full exit)
SL: -8%  → full exit
Trail: after T1 hit, trail 10% from peak on remaining qty
Time: 90 days → full exit
"""
import os, sys, json, ssl
from datetime import datetime
from urllib.request import urlopen, Request

CTX      = ssl.create_default_context()
BOT      = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID",   "")
SUPA_URL = os.environ.get("SUPABASE_URL",        "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPA_KEY = os.environ.get("SUPABASE_KEY",        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
HDRS     = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

# ── Exit config ───────────────────────────────────────────────────────────────
SL_PCT       = -0.08   # -8% stop loss
T1_PCT       =  0.20   # +20% first target — book 50%
T2_PCT       =  0.30   # +30% second target — book remaining 50%
TRAIL_PCT    =  0.10   # 10% trail from peak (activates after T1 hit)
MAX_DAYS     = 90

TIERS = {
    "NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
    "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,
    "FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
    "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3,
}

def http_get(url, headers={}):
    try:
        req = Request(url, headers={"User-Agent":"Mozilla/5.0",**headers})
        with urlopen(req, timeout=12, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  GET err: {e}")
        return None

def http_post(url, data, headers={}):
    try:
        body = json.dumps(data).encode()
        req  = Request(url, data=body,
                       headers={"Content-Type":"application/json",**headers})
        with urlopen(req, timeout=10, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  POST err: {e}")
        return None

def http_patch(url, data):
    try:
        body = json.dumps(data).encode()
        h    = {**HDRS, "Content-Type":"application/json", "Prefer":"return=minimal"}
        req  = Request(url, data=body, headers=h, method="PATCH")
        with urlopen(req, timeout=10, context=CTX) as r:
            return r.status
    except Exception as e:
        print(f"  PATCH err: {e}")
        return None

def tg(msg):
    http_post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    )

def supa_get(table, q=""):
    return http_get(f"{SUPA_URL}/rest/v1/{table}?{q}", HDRS) or []

def supa_patch(table, q, data):
    return http_patch(f"{SUPA_URL}/rest/v1/{table}?{q}", data)

def get_price(symbol):
    d = http_get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
    )
    if not d: return None, None
    try:
        m  = d["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]), float(m.get("regularMarketDayLow", 0))
    except: return None, None

def get_nifty():
    d = http_get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d")
    if not d: return None, None
    try:
        r      = d["chart"]["result"][0]
        closes = [c for c in r["indicators"]["quote"][0]["close"] if c]
        price  = float(r["meta"]["regularMarketPrice"])
        change = (price - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0.0
        return price, change
    except: return None, None

def fi(v, signed=False):
    s = ("+" if v>=0 else "-") if signed else ("-" if v<0 else "")
    v = abs(v)
    if v>=1e7:   r=f"Rs{v/1e7:.2f}Cr"
    elif v>=1e5: r=f"Rs{v/1e5:.1f}L"
    elif v>=1e3: r=f"Rs{v/1e3:.1f}K"
    else:        r=f"Rs{v:.0f}"
    return s+r

def check_and_alert():
    now    = datetime.now()
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    cap_r  = supa_get("p15_capital", "select=*")
    if not cap_r:
        print("  Could not fetch capital")
        return
    cap = cap_r[0]

    print(f"\n  Checking {len(trades)} open trades...")

    for t in trades:
        sym      = t["symbol"]
        entry    = float(t["entry_price"])
        qty      = int(t["quantity"])
        sl_price = float(t["sl_price"])
        ed       = t.get("entry_date", "")
        t1_hit   = t.get("t1_hit", False)
        peak     = float(t.get("peak_cmp") or entry)
        cost     = entry * qty

        cmp, day_low = get_price(sym)
        if not cmp:
            print(f"  [{sym}] Could not fetch price")
            continue

        pct  = (cmp - entry) / entry * 100
        pnl  = (cmp - entry) * qty
        days = (now - datetime.strptime(ed, "%Y-%m-%d")).days if ed else 0

        # Update live price (+ peak if new high) — feeds the GitHub Pages dashboard
        live_fields = {"cmp": round(cmp, 2), "cmp_updated_at": now.isoformat()}
        if cmp > peak:
            peak = cmp
            live_fields["peak_cmp"] = round(cmp, 2)
        supa_patch("p15_trades", f"id=eq.{t['id']}", live_fields)

        peak_pct = (peak - entry) / entry * 100

        print(f"  [{sym}] CMP Rs{cmp:.2f} | {pct:+.1f}% | Peak {peak_pct:+.1f}% | Day {days} | T1={'HIT' if t1_hit else 'NO'}")

        exit_action  = None
        exit_reason  = None
        partial      = False
        exit_qty     = qty
        exit_price   = cmp

        # ── Rule 1: Stop Loss ─────────────────────────────────────────────────
        sl_triggered = (day_low and day_low > 0 and day_low <= sl_price) or cmp <= sl_price
        if sl_triggered:
            exit_price  = sl_price if (day_low and day_low <= sl_price and cmp > sl_price) else cmp
            exit_action = "SL"
            exit_reason = f"Stop Loss hit Rs{exit_price:.2f} (Day Low Rs{day_low:.2f})"
            exit_qty    = qty  # full exit on SL

        # ── Rule 2: T1 — first target +15% ───────────────────────────────────
        elif not t1_hit and pct >= T1_PCT * 100:
            exit_action = "T1"
            exit_qty    = max(1, qty // 2)  # sell 50%
            remaining   = qty - exit_qty
            exit_reason = f"T1 +{T1_PCT*100:.0f}% hit Rs{cmp:.2f} — booking {exit_qty} shares, holding {remaining}"
            partial     = True

        # ── Rule 3: T2 — second target +30% ──────────────────────────────────
        elif t1_hit and pct >= T2_PCT * 100:
            exit_action = "T2"
            exit_qty    = qty  # sell remaining
            exit_reason = f"T2 +{T2_PCT*100:.0f}% hit Rs{cmp:.2f} — full exit"

        # ── Rule 4: No trail — T2 is fixed at +30% ──────────────────────────
        # After T1, only T2 (+30%) or time stop will exit the remaining shares

        # ── Rule 5: Time stop — 90 days ───────────────────────────────────────
        elif days >= MAX_DAYS:
            exit_action = "TIME"
            exit_qty    = qty
            exit_reason = f"90-day time stop — Day {days}"

        if not exit_action:
            # No exit — just report status
            t1_price = round(entry * (1 + T1_PCT), 2)
            t2_price = round(entry * (1 + T2_PCT), 2)
            status = "T1 HIT — trailing" if t1_hit else f"Watching | T1: Rs{t1_price} | T2: Rs{t2_price}"
            print(f"  [{sym}] HOLD — {status}")
            continue

        # ── Execute exit ──────────────────────────────────────────────────────
        exit_pnl     = round((exit_price - entry) * exit_qty, 2)
        exit_pnl_pct = round((exit_price - entry) / entry * 100, 2)
        remaining_qty = qty - exit_qty

        if partial:
            # T1 partial exit — update trade with reduced qty and mark t1_hit
            supa_patch("p15_trades", f"id=eq.{t['id']}", {
                "quantity":  remaining_qty,
                "t1_hit":    True,
                "peak_cmp":  round(peak, 2),
                "cmp":       round(exit_price, 2),
            })
            # Update capital — add back the partial proceeds
            partial_proceeds = exit_price * exit_qty
            new_available = round(cap["available"] + partial_proceeds + exit_pnl, 2)
            # invested stays for remaining qty
            new_pnl = round(cap["total_pnl"] + exit_pnl, 2)
            supa_patch("p15_capital", "id=eq.1", {
                "available":    new_available,
                "total_pnl":    new_pnl,
            })
            cap["available"] = new_available
            cap["total_pnl"] = new_pnl

            tg(
                f"🎯 <b>{sym} — T1 Target Hit!</b>\n\n"
                f"Sold {exit_qty} shares @ Rs{exit_price:.2f}\n"
                f"P&L on sold: <b>{fi(exit_pnl, True)} ({exit_pnl_pct:+.1f}%)</b>\n\n"
                f"Remaining: {remaining_qty} shares still open\n"
                f"T2 target: Rs{round(entry*(1+T2_PCT),2)} (+{T2_PCT*100:.0f}%) — fixed exit"
            )
            print(f"  [{sym}] T1 HIT — booked {exit_qty} shares, {remaining_qty} remaining")

        else:
            # Full exit
            supa_patch("p15_trades", f"id=eq.{t['id']}", {
                "status":      "CLOSED",
                "exit_date":   now.strftime("%Y-%m-%d"),
                "exit_price":  round(exit_price, 2),
                "cmp":         round(exit_price, 2),
                "pnl":         exit_pnl,
                "pnl_pct":     exit_pnl_pct,
                "exit_reason": exit_reason,
            })
            # Update capital fully
            won = 1 if exit_pnl > 0 else 0
            supa_patch("p15_capital", "id=eq.1", {
                "available":      round(cap["available"] + cost + exit_pnl, 2),
                "invested":       round(cap["invested"]  - cost, 2),
                "total_pnl":      round(cap["total_pnl"] + exit_pnl, 2),
                "total_trades":   cap["total_trades"] + 1,
                "winning_trades": cap["winning_trades"] + won,
            })

            icon = {"SL":"🛑","T2":"🏆","TRAIL":"📉","TIME":"⏰"}.get(exit_action,"✅")
            tg(
                f"{icon} <b>{sym} — {exit_action} Exit</b>\n\n"
                f"{exit_reason}\n\n"
                f"Exit: Rs{exit_price:.2f} | Qty: {exit_qty}\n"
                f"P&L: <b>{fi(exit_pnl, True)} ({exit_pnl_pct:+.1f}%)</b>\n"
                f"Entry was Rs{entry:.2f} | Held {days} days"
            )
            print(f"  [{sym}] {exit_action} EXIT @ Rs{exit_price:.2f} | P&L {fi(exit_pnl, True)}")

    # Sync Nifty index + last-updated timestamp — feeds the GitHub Pages dashboard
    nifty_price, nifty_change = get_nifty()
    capital_fields = {"updated_at": now.isoformat()}
    if nifty_price is not None:
        capital_fields["nifty_price"] = round(nifty_price, 2)
        capital_fields["nifty_change_pct"] = round(nifty_change, 2)
    supa_patch("p15_capital", "id=eq.1", capital_fields)

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Power 15 — Sell Alert v3.0 (Option B: T1+20% T2+30%)")
    print("  T1: +20% (50%) | T2: +30% (50%) | SL: -8%")
    print("  No trail — fixed T2 at +30%")
    print("="*55)
    check_and_alert()
    print("\n  Done.\n")
