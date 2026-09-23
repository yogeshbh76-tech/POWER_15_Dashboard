"""
Power 15 — Paper Trading Engine
Simulates Rs.5,00,000 virtual capital using real Yahoo Finance live prices
Auto buys on signal, auto sells on 90 days / -8% SL / +80% target
"""
import json, os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram_alert import send_telegram
import pytz

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

LOG_FILE     = os.path.join(BASE_DIR, "trade_log.json")
CAPITAL_FILE = os.path.join(BASE_DIR, "paper_capital.json")
IST         = pytz.timezone("Asia/Kolkata")
STOP_LOSS   = 0.08   # 8% stop loss
HOLD_DAYS   = 90     # exit after 90 days
PROFIT_TARGET = 0.80 # early exit at 80% profit
QUANTITY    = int(os.environ.get("QUANTITY", 2))

INITIAL_CAPITAL = 500000  # Rs.5,00,000

# ── Capital Management ─────────────────────────────────────────────────

def load_capital():
    if not os.path.exists(CAPITAL_FILE):
        data = {
            "initial": INITIAL_CAPITAL,
            "available": INITIAL_CAPITAL,
            "invested": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0,
            "created_on": datetime.now(IST).strftime("%Y-%m-%d")
        }
        save_capital(data)
        return data
    with open(CAPITAL_FILE) as f:
        return json.load(f)

def save_capital(data):
    with open(CAPITAL_FILE, "w") as f:
        json.dump(data, f, indent=2)

def recalculate_capital():
    """Recompute paper_capital.json from trade_log.json (source of truth).
    Call this any time the capital file drifts out of sync."""
    trades  = load_trades()
    current = load_capital()

    invested       = 0.0
    total_pnl      = 0.0
    total_trades   = 0
    winning_trades = 0

    for t in trades:
        cost = t["entry_price"] * t["quantity"]
        if t["status"] == "OPEN":
            invested += cost
        elif t["status"] == "CLOSED":
            pnl = t.get("pnl") or 0
            total_pnl    += pnl
            total_trades += 1
            if pnl > 0:
                winning_trades += 1

    initial   = current.get("initial", INITIAL_CAPITAL)
    available = initial + total_pnl - invested

    data = {
        "initial":        initial,
        "available":      round(available, 2),
        "invested":       round(invested, 2),
        "total_trades":   total_trades,
        "winning_trades": winning_trades,
        "total_pnl":      round(total_pnl, 2),
        "created_on":     current.get("created_on", datetime.now(IST).strftime("%Y-%m-%d"))
    }
    save_capital(data)
    print(f"  Capital recalculated from {len(trades)} trade(s):")
    print(f"    Available : Rs.{data['available']:>12,.2f}")
    print(f"    Invested  : Rs.{data['invested']:>12,.2f}")
    print(f"    Total P&L : Rs.{data['total_pnl']:>+12,.2f}")
    print(f"    Trades    : {data['total_trades']} ({data['winning_trades']} wins)")
    return data

# ── Trade Log ──────────────────────────────────────────────────────────

def load_trades():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        return json.load(f)

def save_trades(trades):
    with open(LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)

# ── Live Price ─────────────────────────────────────────────────────────

def get_cmp(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

# ── Paper Buy ──────────────────────────────────────────────────────────

def paper_buy(symbol, tier, sector):
    now     = datetime.now(IST)
    capital = load_capital()
    trades  = load_trades()

    # Check if already holding this stock
    open_syms = [t["symbol"] for t in trades if t["status"] == "OPEN"]
    if symbol in open_syms:
        print(f"  ⚠️  Already holding {symbol} — skipping")
        return None

    # Get live price
    price = get_cmp(symbol)
    if not price:
        print(f"  ❌ Could not fetch price for {symbol}")
        return None

    cost = price * QUANTITY

    # Check available capital
    if capital["available"] < cost:
        print(f"  ⚠️  Insufficient capital for {symbol} — need Rs.{cost:.0f}, have Rs.{capital['available']:.0f}")
        return None

    # Place paper order
    trade = {
        "symbol":      symbol,
        "tier":        tier,
        "sector":      sector,
        "entry_price": round(price, 2),
        "quantity":    QUANTITY,
        "entry_date":  now.strftime("%Y-%m-%d"),
        "entry_time":  now.strftime("%H:%M IST"),
        "exit_price":  None,
        "exit_date":   None,
        "exit_reason": None,
        "status":      "OPEN",
        "sl_price":    round(price * (1 - STOP_LOSS), 2),
        "target_price":round(price * (1 + PROFIT_TARGET), 2),
        "exit_by_date":(now + timedelta(days=HOLD_DAYS)).strftime("%Y-%m-%d"),
        "pnl":         0,
        "type":        "PAPER"
    }
    trades.append(trade)
    save_trades(trades)

    # Update capital
    capital["available"] -= cost
    capital["invested"]  += cost
    capital["total_trades"] += 1
    save_capital(capital)

    tier_emoji = "🔥" if tier==1 else "✅" if tier==2 else "⚡"
    print(f"  {tier_emoji} PAPER BUY: {symbol} @ Rs.{price:.2f} x {QUANTITY} = Rs.{cost:.0f}")
    print(f"     SL: Rs.{trade['sl_price']:.2f} | Target: Rs.{trade['target_price']:.2f} | Exit by: {trade['exit_by_date']}")
    print(f"     Capital remaining: Rs.{capital['available']:,.0f}")

    return trade

# ── Paper Sell ─────────────────────────────────────────────────────────

def paper_sell(trade, reason, cmp):
    now    = datetime.now(IST)
    trades = load_trades()
    capital= load_capital()

    pnl    = (cmp - trade["entry_price"]) * trade["quantity"]
    pct    = (cmp - trade["entry_price"]) / trade["entry_price"] * 100
    cost   = trade["entry_price"] * trade["quantity"]
    proceeds = cmp * trade["quantity"]

    # Update trade record
    for t in trades:
        if t["symbol"] == trade["symbol"] and t["status"] == "OPEN" and t["entry_date"] == trade["entry_date"]:
            t["status"]      = "CLOSED"
            t["exit_price"]  = round(cmp, 2)
            t["exit_date"]   = now.strftime("%Y-%m-%d")
            t["exit_time"]   = now.strftime("%H:%M IST")
            t["exit_reason"] = reason
            t["pnl"]         = round(pnl, 2)
            t["pnl_pct"]     = round(pct, 2)
            break
    save_trades(trades)

    # Update capital
    capital["available"] += proceeds
    capital["invested"]  -= cost
    capital["total_pnl"] += pnl
    if pnl > 0:
        capital["winning_trades"] += 1
    save_capital(capital)

    emoji = "✅" if pnl >= 0 else "❌"
    print(f"  {emoji} PAPER SELL: {trade['symbol']} @ Rs.{cmp:.2f} | P&L: Rs.{pnl:+.0f} ({pct:+.1f}%)")
    print(f"     Reason: {reason}")
    print(f"     Capital after: Rs.{capital['available']:,.0f}")

    return pnl

# ── Auto Buy on Signals ────────────────────────────────────────────────

def process_buy_signals(triggered_stocks):
    """Called from scanner.py after signals are found"""
    if not triggered_stocks:
        print("  No signals to process.")
        return

    capital = load_capital()
    print(f"\n{'='*50}")
    print(f"  💰 PAPER TRADING — Available Capital: Rs.{capital['available']:,.0f}")
    print(f"{'='*50}")

    bought = []
    for s in triggered_stocks:
        trade = paper_buy(s["symbol"], s["tier"], s["sector"])
        if trade:
            bought.append(trade)

    if bought:
        # Send Telegram notification
        lines = [f"📝 <b>Paper Trade — {len(bought)} BUY Order(s) Placed</b>\n"]
        for t in bought:
            lines.append(
                f"✅ <b>{t['symbol']}</b> — Tier {t['tier']}\n"
                f"   Entry: Rs.{t['entry_price']:.2f} x {t['quantity']} qty\n"
                f"   Cost: Rs.{t['entry_price']*t['quantity']:.0f}\n"
                f"   SL: Rs.{t['sl_price']:.2f} | Exit by: {t['exit_by_date']}"
            )
        cap = load_capital()
        lines.append(f"\n💰 Capital Remaining: Rs.{cap['available']:,.0f} / Rs.{cap['initial']:,.0f}")
        send_telegram("\n\n".join(lines))
        print(f"\n  ✅ {len(bought)} paper trade(s) placed successfully!")

    return bought

# ── Auto Sell Check ────────────────────────────────────────────────────

def check_exit_signals():
    """Called daily at 3:45 PM — check all open positions for exit"""
    trades  = load_trades()
    open_tr = [t for t in trades if t["status"] == "OPEN" and t.get("type") == "PAPER"]
    now     = datetime.now(IST)

    if not open_tr:
        print("  No open paper trades to check.")
        return

    print(f"\n{'='*50}")
    print(f"  🔍 Checking {len(open_tr)} open paper trade(s)...")
    print(f"{'='*50}")

    sold = []
    for t in open_tr:
        symbol     = t["symbol"]
        entry_date = datetime.strptime(t["entry_date"], "%Y-%m-%d")
        days_held  = (now.replace(tzinfo=None) - entry_date).days
        sl_price   = t["sl_price"]
        exit_date  = datetime.strptime(t["exit_by_date"], "%Y-%m-%d")

        print(f"\n  Checking {symbol} (held {days_held} days)...")
        cmp = get_cmp(symbol)
        if not cmp:
            print(f"    ⚠️  Could not fetch price, skipping.")
            continue

        pct = (cmp - t["entry_price"]) / t["entry_price"] * 100
        print(f"    CMP: Rs.{cmp:.2f} | Change: {pct:+.1f}% | SL: Rs.{sl_price:.2f}")

        reason = None

        # Rule 1: 90-day exit
        if days_held >= HOLD_DAYS:
            reason = "90-Day Exit"
        # Rule 2: Stop loss
        elif cmp <= sl_price:
            reason = f"Stop Loss Hit (-8%)"
        # Rule 3: Early profit target
        elif pct >= PROFIT_TARGET * 100:
            reason = f"Profit Target Hit (+{pct:.0f}%)"

        if reason:
            pnl = paper_sell(t, reason, cmp)
            sold.append({"symbol": symbol, "pnl": pnl, "pct": pct, "reason": reason, "cmp": cmp})

    if sold:
        # Send Telegram
        lines = [f"🔴 <b>Paper Trade — {len(sold)} SELL Order(s) Executed</b>\n"]
        total_pnl = 0
        for s in sold:
            emoji = "✅" if s["pnl"] >= 0 else "❌"
            lines.append(
                f"{emoji} <b>{s['symbol']}</b> CLOSED\n"
                f"   Exit: Rs.{s['cmp']:.2f} | P&L: Rs.{s['pnl']:+.0f} ({s['pct']:+.1f}%)\n"
                f"   Reason: {s['reason']}"
            )
            total_pnl += s["pnl"]
        cap = load_capital()
        win_rate = (cap["winning_trades"] / cap["total_trades"] * 100) if cap["total_trades"] > 0 else 0
        lines.append(f"\n📊 Portfolio P&L: Rs.{cap['total_pnl']:+,.0f} | Win Rate: {win_rate:.0f}%")
        lines.append(f"💰 Available Capital: Rs.{cap['available']:,.0f}")
        send_telegram("\n\n".join(lines))

    return sold

# ── Portfolio Summary ──────────────────────────────────────────────────

def print_portfolio():
    trades  = load_trades()
    capital = load_capital()
    open_tr = [t for t in trades if t["status"] == "OPEN"]
    closed  = [t for t in trades if t["status"] == "CLOSED"]
    now     = datetime.now(IST)

    print(f"\n{'='*60}")
    print(f"  ⚡ POWER 15 PAPER PORTFOLIO")
    print(f"{'='*60}")
    print(f"  Initial Capital : Rs.{capital['initial']:>12,.0f}")
    print(f"  Available       : Rs.{capital['available']:>12,.0f}")
    print(f"  Invested        : Rs.{capital['invested']:>12,.0f}")
    print(f"  Realised P&L    : Rs.{capital['total_pnl']:>+12,.0f}")
    print(f"  Total Trades    : {capital['total_trades']}")
    if capital['total_trades'] > 0:
        wr = capital['winning_trades'] / capital['total_trades'] * 100
        print(f"  Win Rate        : {wr:.0f}%")

    if open_tr:
        print(f"\n  OPEN POSITIONS ({len(open_tr)}):")
        print(f"  {'Symbol':<13} {'Entry':>8} {'CMP':>8} {'P&L':>8} {'Days':>5} {'Left':>5}")
        print(f"  {'-'*55}")
        unrealised = 0
        for t in open_tr:
            days = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
            left = max(0, 90 - days)
            cmp  = get_cmp(t["symbol"]) or t["entry_price"]
            pnl  = (cmp - t["entry_price"]) * t["quantity"]
            pct  = (cmp - t["entry_price"]) / t["entry_price"] * 100
            unrealised += pnl
            print(f"  {t['symbol']:<13} {t['entry_price']:>8.2f} {cmp:>8.2f} {pnl:>+8.0f} ({pct:+.1f}%) {days:>3}d {left:>3}d left")
        print(f"\n  Unrealised P&L  : Rs.{unrealised:>+,.0f}")
        total = capital["total_pnl"] + unrealised
        ret   = total / capital["initial"] * 100
        print(f"  Total P&L       : Rs.{total:>+,.0f} ({ret:+.1f}%)")

    if closed:
        print(f"\n  CLOSED TRADES ({len(closed)}):")
        for t in closed:
            emoji = "✅" if t.get("pnl", 0) >= 0 else "❌"
            print(f"  {emoji} {t['symbol']:<13} Rs.{t.get('pnl',0):>+8.0f}  ({t.get('pnl_pct',0):+.1f}%)  {t.get('exit_reason','')}")

    print(f"{'='*60}\n")

if __name__ == "__main__":
    import sys
    if "--recalc" in sys.argv:
        recalculate_capital()
    else:
        print_portfolio()