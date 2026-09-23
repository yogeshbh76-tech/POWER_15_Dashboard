# -*- coding: utf-8 -*-
"""
Power 15 — Telegram Bot Listener
=================================
Listens for commands via Telegram long-polling (no extra libraries needed).

Commands:
  /help       — Show available commands
  /portfolio  — Live portfolio snapshot with P&L
  /watchlist  — Today's watchlist (from scanner)
  /status     — Capital + win-rate summary
  /scan       — Trigger scanner manually (runs scanner.py)
"""
import os, sys, json, time, subprocess, requests
from datetime import datetime
from dotenv import load_dotenv
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
LOG_FILE   = os.path.join(BASE_DIR, "trade_log.json")
CAP_FILE   = os.path.join(BASE_DIR, "paper_capital.json")
WATCH_FILE = os.path.join(BASE_DIR, "watchlist.json")
IST        = pytz.timezone("Asia/Kolkata")

# ── Telegram helpers ──────────────────────────────────────────────────────────

def api(method, **kwargs):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    resp = requests.post(url, json=kwargs, timeout=10)
    return resp.json()

def send(chat_id, text):
    api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")

def get_updates(offset):
    result = api("getUpdates", offset=offset, timeout=30)
    return result.get("result", [])

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            pass
    return default

def get_cmp(symbol):
    try:
        url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        return float(resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        return None

# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_help():
    return (
        "⚡ <b>Power 15 Bot — Commands</b>\n\n"
        "/portfolio  — Live P&amp;L of all open positions\n"
        "/watchlist  — Today's scanner watchlist\n"
        "/status     — Capital &amp; win-rate summary\n"
        "/scan       — Run scanner now (3:30 PM scan)\n"
        "/help       — Show this message"
    )

def cmd_portfolio():
    trades  = load_json(LOG_FILE, [])
    capital = load_json(CAP_FILE, {
        "initial": 500000, "available": 500000, "invested": 0,
        "total_pnl": 0, "total_trades": 0, "winning_trades": 0
    })
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    now = datetime.now(IST)

    if not open_trades:
        snap  = "📊 <b>Portfolio Snapshot</b>\n\n"
        snap += "📭 No open positions\n\n"
        snap += f"💰 Available: ₹{capital['available']:,.0f} / ₹{capital['initial']:,.0f}\n"
        if capital["total_trades"] > 0:
            wr = capital["winning_trades"] / capital["total_trades"] * 100
            snap += f"🎯 Win Rate: {wr:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)\n"
            snap += f"📈 Realised P&amp;L: ₹{capital['total_pnl']:+,.0f}"
        return snap

    lines = [f"📊 <b>Portfolio ({len(open_trades)} open)</b>\n"]
    total_unreal = 0

    for t in open_trades:
        cmp = get_cmp(t["symbol"]) or t["entry_price"]
        pnl = (cmp - t["entry_price"]) * t["quantity"]
        pct = (cmp - t["entry_price"]) / t["entry_price"] * 100
        days_held = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
        days_left = max(0, 90 - days_held)
        total_unreal += pnl
        arrow  = "🟢" if pnl >= 0 else "🔴"
        warn   = " ⚠️" if days_left <= 10 else ""
        lines.append(
            f"{arrow} <b>{t['symbol']}</b>: ₹{cmp:.0f} ({pct:+.1f}%) "
            f"| P&amp;L: ₹{pnl:+.0f} | {days_held}d/{90}d{warn}"
        )

    total_pnl    = capital["total_pnl"] + total_unreal
    total_return = total_pnl / capital["initial"] * 100 if capital["initial"] > 0 else 0
    used_pct     = (capital["invested"] / capital["initial"] * 100) if capital["initial"] > 0 else 0

    lines.append(f"\n💰 Available: ₹{capital['available']:,.0f} ({100-used_pct:.0f}% free)")
    lines.append(f"📈 Total P&amp;L: ₹{total_pnl:+,.0f} ({total_return:+.1f}%)")
    if capital["total_trades"] > 0:
        wr = capital["winning_trades"] / capital["total_trades"] * 100
        lines.append(f"🎯 Win Rate: {wr:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)")

    return "\n".join(lines)

def cmd_watchlist():
    data = load_json(WATCH_FILE, None)
    if not data or not data.get("symbols"):
        return "📭 <b>Watchlist</b>\n\nNo watchlist yet. Run scanner at 3:30 PM."

    now    = datetime.now(IST)
    date   = data.get("date", "?")
    nifty  = data.get("nifty_status", "UNKNOWN")
    nifty_emoji = {"STRONG": "🟢", "CAUTION": "🟡", "AVOID": "🔴"}.get(nifty, "⚪")
    details = {d["symbol"]: d for d in data.get("details", [])}

    lines = [f"📋 <b>Watchlist — {date}</b>", f"{nifty_emoji} Nifty: <b>{nifty}</b>\n"]
    for sym in data["symbols"]:
        d    = details.get(sym, {})
        tier = d.get("tier", "?")
        tier_label = {1: "🔥 T1", 2: "✅ T2", 3: "⚡ T3"}.get(tier, f"T{tier}")
        sector = d.get("sector", "")
        cmp    = d.get("cmp", 0)
        rsi    = d.get("rsi", None)
        lines.append(
            f"{tier_label} <b>{sym}</b> ({sector})\n"
            f"   Scan CMP: ₹{cmp:.2f} | RSI: {rsi or 'N/A'}"
        )

    rejected = data.get("rejected", [])
    if rejected:
        lines.append(f"\n⛔ <b>Rejected ({len(rejected)}):</b>")
        for item in rejected:
            sym, tier, reason = item[0], item[1], item[2]
            lines.append(f"  • {sym}: {reason}")

    return "\n".join(lines)

def cmd_status():
    capital = load_json(CAP_FILE, {
        "initial": 500000, "available": 500000, "invested": 0,
        "total_pnl": 0, "total_trades": 0, "winning_trades": 0
    })
    trades     = load_json(LOG_FILE, [])
    open_count = sum(1 for t in trades if t["status"] == "OPEN")
    used_pct   = capital["invested"] / capital["initial"] * 100 if capital["initial"] > 0 else 0
    win_rate   = (
        capital["winning_trades"] / capital["total_trades"] * 100
        if capital["total_trades"] > 0 else 0
    )
    now = datetime.now(IST)

    lines = [
        f"⚡ <b>Power 15 Status</b>",
        f"🕐 {now.strftime('%d %b %Y %H:%M IST')}\n",
        f"💰 Available: ₹{capital['available']:,.0f}",
        f"📦 Invested:  ₹{capital['invested']:,.0f} ({used_pct:.0f}% deployed)",
        f"📈 Realised P&amp;L: ₹{capital['total_pnl']:+,.0f}",
        f"📊 Open Positions: {open_count}",
    ]
    if capital["total_trades"] > 0:
        lines.append(
            f"🎯 Win Rate: {win_rate:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)"
        )
    return "\n".join(lines)

def cmd_scan(chat_id):
    send(chat_id, "⏳ Running scanner... this may take 30–60 seconds.")
    py = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    try:
        result = subprocess.run(
            [py, os.path.join(BASE_DIR, "scanner.py")],
            capture_output=True, text=True, timeout=120, cwd=BASE_DIR
        )
        if result.returncode == 0:
            return "✅ Scanner complete — check your Telegram for the scan result!"
        else:
            err = (result.stderr or result.stdout or "Unknown error")[-500:]
            return f"❌ Scanner error:\n<code>{err}</code>"
    except subprocess.TimeoutExpired:
        return "⏱ Scanner timed out (>120s). Try again later."
    except Exception as e:
        return f"❌ Could not run scanner: {e}"

# ── Main polling loop ─────────────────────────────────────────────────────────

def handle_message(message):
    chat_id = message["chat"]["id"]
    text    = message.get("text", "").strip().lower().split()[0]  # first word only

    if text == "/help"      : send(chat_id, cmd_help())
    elif text == "/portfolio": send(chat_id, cmd_portfolio())
    elif text == "/watchlist": send(chat_id, cmd_watchlist())
    elif text == "/status"  : send(chat_id, cmd_status())
    elif text == "/scan"    : send(chat_id, cmd_scan(chat_id))
    else:
        send(chat_id, "❓ Unknown command. Send /help for the list.")

def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    print(f"⚡ Power 15 Telegram Bot started — {datetime.now(IST).strftime('%d %b %Y %H:%M IST')}")
    print("  Listening for commands... (Ctrl+C to stop)\n")

    # Send startup notification
    try:
        send(CHAT_ID, f"⚡ <b>Power 15 Bot online!</b>\n{datetime.now(IST).strftime('%d %b %Y %H:%M IST')}\n\nSend /help for commands.")
    except Exception as e:
        print(f"  [Startup] Could not send startup message: {e}")

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
        except requests.exceptions.Timeout:
            pass  # normal — long-poll timed out, retry
        except requests.exceptions.ConnectionError as e:
            print(f"  [Poll] Connection error: {e} — retrying in 5s")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nBot stopped.")
            break
        except Exception as e:
            print(f"  [Poll] Unexpected error: {e} — retrying in 5s")
            time.sleep(5)

if __name__ == "__main__":
    main()
