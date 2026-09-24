"""
Power 15 — Buy Check v2.1 (Run at 3:25 PM daily)
=================================================
UPGRADES vs v1:
  #1 Tier-Based Sizing : Tier 1 = ₹20,000 | Tier 2 = ₹15,000 | Tier 3 = ₹10,000
                         Better stocks get more capital. Same total exposure.
  #2 Volume Filter     : Red candle is only valid if volume < 1.5x 20-day avg
                         High volume red = distribution/panic — SKIP
                         Low-medium volume red = healthy pullback — BUY
  #4 Intraday SL Check : Also runs at 10 AM and 1 PM (same script, mode flag)
                         At those times only checks stop losses + trailing stops
                         Full buy logic only at 3:25 PM

v2.1: Trades, capital and the watchlist now live in Supabase instead of local
JSON files, so this runs the same way from GitHub Actions or a local PC —
GitHub Actions gives each scheduled run a fresh, disposable filesystem, so a
local file written by scanner.py could never reach buy_check.py's later run.

Run modes:
  python buy_check.py          → 3:25 PM full buy check
  python buy_check.py --sl     → 10 AM / 1 PM SL-only check
"""
import os, requests, sys
from datetime import datetime
from dotenv import load_dotenv
import pytz

load_dotenv(r"C:\power15_bot\.env")

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPA_URL         = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPA_KEY         = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
HDRS             = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}
IST              = pytz.timezone("Asia/Kolkata")
SL_PCT           = 0.08

# ── Tier-based position sizing ────────────────────────────────────────────────
TIER_TRADE_VALUE = {
    1: 20000,   # Tier 1 — 100% win rate, best stocks — double allocation
    2: 15000,   # Tier 2 — 100% win rate, solid stocks — 1.5x allocation
    3: 10000,   # Tier 3 — 87% win rate — standard allocation
}

# ── Volume filter thresholds ──────────────────────────────────────────────────
VOLUME_CAUTION_X = 1.2   # warn if volume > 1.2x avg (note it but still buy)
VOLUME_SKIP_X    = 1.5   # skip if volume > 1.5x avg (distribution/panic sell)

POWER_15 = {
    "NATIONALUM":1,"INDIANB":1,"VEDL":1,"SHRIRAMFIN":1,
    "CANBK":2,"SBIN":2,"MANAPPURAM":2,"ABCAPITAL":2,
    "FEDERALBNK":2,"LTF":2,"BANKINDIA":2,"HINDALCO":2,
    "BAJFINANCE":3,"HINDZINC":3,"AUBANK":3,
}
POWER_15_SECTORS = {
    "NATIONALUM":"Metals & Mining","VEDL":"Metals & Mining",
    "HINDALCO":"Metals & Mining","HINDZINC":"Metals & Mining",
    "INDIANB":"PSU Bank","CANBK":"PSU Bank","SBIN":"PSU Bank","BANKINDIA":"PSU Bank",
    "SHRIRAMFIN":"Financials","MANAPPURAM":"Financials","ABCAPITAL":"Financials",
    "LTF":"Financials","BAJFINANCE":"Financials",
    "FEDERALBNK":"Private Bank","AUBANK":"Private Bank",
}

# ── Hybrid exit config (same as sell_alert.py) ────────────────────────────────
HYBRID_CONFIG = {
    "NATIONALUM": {"threshold_pct": 75, "trail_pct": 15},
    "INDIANB":    {"threshold_pct": 70, "trail_pct": 15},
    "VEDL":       {"threshold_pct": 70, "trail_pct": 18},
    "SHRIRAMFIN": {"threshold_pct": 70, "trail_pct": 15},
    "CANBK":      {"threshold_pct": 65, "trail_pct": 15},
    "SBIN":       {"threshold_pct": 70, "trail_pct": 15},
    "MANAPPURAM": {"threshold_pct": 60, "trail_pct": 20},
    "ABCAPITAL":  {"threshold_pct": 60, "trail_pct": 20},
    "FEDERALBNK": {"threshold_pct": 65, "trail_pct": 15},
    "LTF":        {"threshold_pct": 80, "trail_pct":  0},
    "BANKINDIA":  {"threshold_pct": 65, "trail_pct": 15},
    "HINDALCO":   {"threshold_pct": 70, "trail_pct": 15},
    "BAJFINANCE": {"threshold_pct": 80, "trail_pct":  0},
    "HINDZINC":   {"threshold_pct": 80, "trail_pct":  0},
    "AUBANK":     {"threshold_pct": 80, "trail_pct":  0},
}

# ── Supabase helpers ────────────────────────────────────────────────────────
def supa_get(table, query=""):
    try:
        r = requests.get(f"{SUPA_URL}/rest/v1/{table}?{query}", headers=HDRS, timeout=15)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"  [Supabase] GET error: {e}")
        return []

def supa_post(table, data):
    try:
        h = {**HDRS, "Content-Type": "application/json", "Prefer": "return=minimal"}
        r = requests.post(f"{SUPA_URL}/rest/v1/{table}", headers=h, json=data, timeout=15)
        if r.status_code not in (200, 201):
            print(f"  [Supabase] POST error [{table}]: {r.status_code} — {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"  [Supabase] POST error: {e}")
        return False

def supa_patch(table, query, data):
    try:
        h = {**HDRS, "Content-Type": "application/json", "Prefer": "return=minimal"}
        r = requests.patch(f"{SUPA_URL}/rest/v1/{table}?{query}", headers=h, json=data, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"  [Supabase] PATCH error: {e}")
        return False

def get_capital():
    rows = supa_get("p15_capital", "select=*")
    return rows[0] if rows else {
        "initial":500000,"available":500000,"invested":0,
        "total_pnl":0,"total_trades":0,"winning_trades":0
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        print("  [Telegram] Sent ✓")
    except Exception as e:
        print(f"  [Telegram] Error: {e}")

def get_candle_data(symbol):
    """
    Fetch today's open, current CMP, today's volume, and 20-day avg volume.
    Returns dict or None on failure.
    """
    try:
        url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=1d&range=30d"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        result    = resp.json()["chart"]["result"][0]
        meta      = result["meta"]
        quote     = result["indicators"]["quote"][0]
        opens     = [o for o in quote["open"]   if o is not None]
        volumes   = [v for v in quote["volume"] if v is not None]
        cmp       = float(meta["regularMarketPrice"])
        today_open = opens[-1]
        today_vol  = volumes[-1] if volumes else None
        avg_vol_20 = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
        return {
            "cmp":       cmp,
            "open":      today_open,
            "is_red":    cmp < today_open,
            "vol":       today_vol,
            "avg_vol":   avg_vol_20,
            "vol_ratio": (today_vol / avg_vol_20) if (today_vol and avg_vol_20) else None,
        }
    except Exception as e:
        print(f"  [{symbol}] Candle fetch failed: {e}")
        return None

def get_cmp(symbol):
    try:
        url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        return float(resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

def paper_buy(symbol, cmp, tier):
    trades = supa_get("p15_trades", "select=id,symbol,status")
    if any(t["symbol"] == symbol and t["status"] == "OPEN" for t in trades):
        print(f"  [Paper] Already holding {symbol} — skipping")
        return False, "Already in portfolio"

    capital     = get_capital()
    trade_value = TIER_TRADE_VALUE.get(tier, 10000)
    quantity    = max(1, int(trade_value / cmp))
    cost        = quantity * cmp
    sl_price    = round(cmp * (1 - SL_PCT), 2)

    if capital["available"] < cost:
        print(f"  [Paper] Insufficient capital — need ₹{cost:.0f}, have ₹{capital['available']:.0f}")
        return False, "Insufficient capital"

    new_id = max([t.get("id", 0) for t in trades], default=0) + 1
    trade = {
        "id":           new_id,
        "symbol":       symbol,
        "entry_date":   datetime.now(IST).strftime("%Y-%m-%d"),
        "entry_price":  round(cmp, 2),
        "quantity":     quantity,
        "sl_price":     sl_price,
        "peak_cmp":     round(cmp, 2),
        "cmp":          round(cmp, 2),
        "status":       "OPEN",
        "tier":         tier,
        "sector":       POWER_15_SECTORS.get(symbol, "Other"),
    }
    if not supa_post("p15_trades", trade):
        return False, "Supabase insert failed"

    supa_patch("p15_capital", "id=eq.1", {
        "available": round(capital["available"] - cost, 2),
        "invested":  round(capital["invested"] + cost, 2),
    })

    print(f"  [Paper] ✅ BUY {symbol} @ ₹{cmp:.2f} x {quantity} qty = ₹{cost:.0f}  (Tier {tier}, alloc ₹{trade_value:,})")
    return True, "OK"

# ── Intraday SL-only check (10 AM + 1 PM) ─────────────────────────────────────

def intraday_sl_check(now):
    """
    Lightweight check — only looks for stop loss hits and trailing stops.
    Does NOT process new buys.
    """
    print(f"\n[Intraday SL Check — {now.strftime('%H:%M IST')}]")
    open_trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    if not open_trades:
        print("  No open positions")
        return

    capital = get_capital()
    alerts  = []

    for t in open_trades:
        symbol = t["symbol"]
        entry  = t["entry_price"]
        sl     = t["sl_price"]

        # Get CMP AND intraday low
        try:
            url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            meta = resp.json()["chart"]["result"][0]["meta"]
            cmp     = float(meta["regularMarketPrice"])
            day_low = float(meta.get("regularMarketDayLow", cmp))
        except:
            print(f"  ⚠️  Could not fetch {symbol}")
            continue

        # Update peak + live price (feeds the GitHub Pages dashboard too)
        peak_cmp    = t.get("peak_cmp") or entry
        live_fields = {"cmp": round(cmp, 2), "cmp_updated_at": now.isoformat()}
        if cmp > peak_cmp:
            peak_cmp = cmp
            live_fields["peak_cmp"] = round(cmp, 2)

        pct       = (cmp - entry) / entry * 100
        cfg       = HYBRID_CONFIG.get(symbol, {"threshold_pct": 80, "trail_pct": 0})
        peak_pct  = (peak_cmp - entry) / entry * 100
        exit_reason = None
        exit_price  = cmp

        # Stop loss — use day_low to catch intraday breaches even if CMP recovered
        sl_breached = day_low <= sl
        if sl_breached:
            exit_price  = min(cmp, sl)  # exit at SL price if CMP recovered above it
            exit_reason = f"🛑 Intraday SL breached — Day Low ₹{day_low:.2f} ≤ SL ₹{sl:.2f} — exit @ ₹{exit_price:.2f}"
            print(f"  🛑 {symbol} SL BREACHED — Day Low ₹{day_low:.2f} ≤ SL ₹{sl:.2f}")

        # Trailing stop check (only if peak crossed threshold)
        elif cfg["trail_pct"] > 0 and peak_pct >= cfg["threshold_pct"]:
            trail_stop = peak_cmp * (1 - cfg["trail_pct"] / 100)
            if cmp <= trail_stop:
                exit_reason = f"📉 Intraday trailing stop @ ₹{cmp:.2f} (peak ₹{peak_cmp:.2f})"
                print(f"  📉 {symbol} TRAIL STOP — CMP ₹{cmp:.2f} ≤ trail ₹{trail_stop:.2f}")

        if exit_reason:
            pnl     = (exit_price - entry) * t["quantity"]
            pnl_pct = (exit_price - entry) / entry * 100
            cost    = entry * t["quantity"]

            supa_patch("p15_trades", f"id=eq.{t['id']}", {
                "status":      "CLOSED",
                "exit_date":   now.strftime("%Y-%m-%d"),
                "exit_price":  round(exit_price, 2),
                "cmp":         round(exit_price, 2),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round(pnl_pct, 2),
                "exit_reason": exit_reason,
            })
            capital["available"]    += cost + pnl
            capital["invested"]     -= cost
            capital["total_pnl"]    += pnl
            capital["total_trades"] += 1
            if pnl > 0:
                capital["winning_trades"] += 1
            supa_patch("p15_capital", "id=eq.1", {
                "available":      round(capital["available"], 2),
                "invested":       round(capital["invested"], 2),
                "total_pnl":      round(capital["total_pnl"], 2),
                "total_trades":   capital["total_trades"],
                "winning_trades": capital["winning_trades"],
            })
            alerts.append({"symbol": symbol, "cmp": cmp, "pnl": pnl, "pct": pnl_pct, "reason": exit_reason})
        else:
            supa_patch("p15_trades", f"id=eq.{t['id']}", live_fields)
            print(f"  ✅ {symbol}: ₹{cmp:.2f} ({pct:+.1f}%) | SL ₹{sl:.2f} | Safe")

    if alerts:
        msg = f"🚨 <b>Power 15 — Intraday Exit ({now.strftime('%H:%M IST')})</b>\n\n"
        for a in alerts:
            color = "🟢" if a["pnl"] >= 0 else "🔴"
            msg  += f"{color} <b>{a['symbol']}</b> — {a['reason']}\n"
            msg  += f"   P&L: ₹{a['pnl']:+.0f} ({a['pct']:+.1f}%)\n\n"
        send_telegram(msg)
    else:
        print("  All positions safe — no intraday exits")

# ── Full buy check (3:25 PM) ──────────────────────────────────────────────────

def full_buy_check(now):
    print(f"\n[Full Buy Check — {now.strftime('%H:%M IST')}]")

    wl_rows   = supa_get("p15_watchlist", "id=eq.1&select=*")
    watchlist = wl_rows[0] if wl_rows else {}
    symbols   = watchlist.get("symbols") or []
    nifty_st  = watchlist.get("nifty_status", "UNKNOWN")

    if not symbols:
        print("  Watchlist empty — no signals from yesterday")
        send_telegram(f"⚡ <b>Power 15 Buy Check — {now.strftime('%d %b %Y %H:%M')}</b>\n\n📭 Watchlist empty")
        return

    print(f"  Watchlist ({len(symbols)}): {symbols}")
    print(f"  Nifty status from yesterday: {nifty_st}")
    print(f"\n[Candle + Volume Check]")

    buy_list    = []
    skip_list   = []

    for symbol in symbols:
        tier = POWER_15.get(symbol, 2)
        data = get_candle_data(symbol)

        if not data:
            skip_list.append((symbol, "Could not fetch data"))
            continue

        cmp       = data["cmp"]
        is_red    = data["is_red"]
        vol_ratio = data["vol_ratio"]

        if not is_red:
            skip_list.append((symbol, f"Green candle (CMP ₹{cmp:.2f} > Open ₹{data['open']:.2f})"))
            print(f"  [{symbol}] 🟢 GREEN candle — skip")
            continue

        # Volume filter
        vol_tag = ""
        if vol_ratio is not None:
            if vol_ratio > VOLUME_SKIP_X:
                skip_list.append((symbol, f"High volume red candle ({vol_ratio:.1f}x avg) — possible distribution"))
                print(f"  [{symbol}] 🔴 RED but vol={vol_ratio:.1f}x avg — DISTRIBUTION SIGNAL, skipping")
                continue
            elif vol_ratio > VOLUME_CAUTION_X:
                vol_tag = f" ⚠️ vol {vol_ratio:.1f}x avg"
                print(f"  [{symbol}] 🔴 RED — vol={vol_ratio:.1f}x avg (caution but buying)")
            else:
                vol_tag = f" ✅ vol {vol_ratio:.1f}x avg"
                print(f"  [{symbol}] 🔴 RED — vol={vol_ratio:.1f}x avg (healthy pullback)")
        else:
            vol_tag = " (vol data N/A)"
            print(f"  [{symbol}] 🔴 RED — vol ratio unavailable")

        trade_value = TIER_TRADE_VALUE.get(tier, 10000)
        qty         = max(1, int(trade_value / cmp))
        sl          = round(cmp * (1 - SL_PCT), 2)
        buy_list.append({
            "symbol":    symbol,
            "cmp":       cmp,
            "open":      data["open"],
            "tier":      tier,
            "qty":       qty,
            "sl":        sl,
            "cost":      qty * cmp,
            "vol_ratio": vol_ratio,
            "vol_tag":   vol_tag,
            "alloc":     trade_value,
        })

    # Execute buys
    msg  = f"⚡ <b>Power 15 Buy Check v2.1 — {now.strftime('%d %b %Y %H:%M')}</b>\n\n"
    nifty_emoji = {"STRONG":"🟢","CAUTION":"🟡","AVOID":"🔴"}.get(nifty_st, "⚪")
    msg += f"{nifty_emoji} Nifty trend: <b>{nifty_st}</b>\n\n"

    if buy_list:
        msg += f"🛒 <b>Buying {len(buy_list)} stock(s):</b>\n"
        for b in buy_list:
            tier_label = ["","🔥 T1","✅ T2","⚡ T3"][b["tier"]]
            success, reason = paper_buy(b["symbol"], b["cmp"], b["tier"])
            status = "✅ Bought" if success else f"❌ {reason}"
            msg += f"\n{tier_label} <b>{b['symbol']}</b>\n"
            msg += f"   Open: ₹{b['open']:.2f} → CMP: ₹{b['cmp']:.2f}{b['vol_tag']}\n"
            msg += f"   Alloc: ₹{b['alloc']:,} | Qty: {b['qty']} | SL: ₹{b['sl']:.2f}\n"
            msg += f"   {status}\n"
    else:
        msg += "📭 <b>No buys today</b> — all signals filtered\n"

    if skip_list:
        msg += f"\n⛔ <b>Skipped ({len(skip_list)}):</b>\n"
        for sym, reason in skip_list:
            msg += f"  • {sym}: {reason}\n"

    print("\n[Telegram]")
    send_telegram(msg)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    now  = datetime.now(IST)
    mode = "--sl" in sys.argv   # True if called with --sl flag (10 AM / 1 PM runs)

    print(f"\n{'='*55}")
    if mode:
        print(f"  ⚡ Power 15 Intraday SL Check")
    else:
        print(f"  ⚡ Power 15 Buy Check v2.1")
    print(f"  {now.strftime('%d %b %Y %H:%M IST')}")
    print(f"{'='*55}")

    if mode:
        intraday_sl_check(now)
    else:
        full_buy_check(now)

    print("\n✅ Done\n")

if __name__ == "__main__":
    main()
