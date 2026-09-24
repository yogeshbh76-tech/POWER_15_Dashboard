# -*- coding: utf-8 -*-
"""
Power 15 — Telegram Bot Listener v2.0
=======================================
Runs as a single bounded pass (fetch pending commands, respond, exit) so it
can be triggered every few minutes by a GitHub Actions cron instead of
needing an always-on process. Telegram's getUpdates offset is tracked
server-side by Telegram itself, so no state needs to persist between runs.

Commands:
  /help       — Show available commands
  /portfolio  — Live portfolio snapshot with P&L
  /positions  — Alias for /portfolio
  /watchlist  — Today's watchlist (from scanner)
  /status     — Capital + win-rate summary
  /scan       — Trigger scanner manually (runs scanner.py)
"""
import os, sys, subprocess, requests
from datetime import datetime
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SUPA_URL  = os.environ.get("SUPABASE_URL", "https://xlrbmsmrgosqbioojqfz.supabase.co")
SUPA_KEY  = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM")
HDRS      = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}
IST       = pytz.timezone("Asia/Kolkata")

# ── Telegram helpers ──────────────────────────────────────────────────────────

def api(method, **kwargs):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        resp = requests.post(url, json=kwargs, timeout=20)
        return resp.json()
    except Exception as e:
        print(f"  [Telegram] {method} error: {e}")
        return {}

def send(chat_id, text):
    api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")

def get_pending_updates():
    """Short-poll for whatever's immediately available, then confirm receipt
    so Telegram doesn't redeliver them next run."""
    result = api("getUpdates", timeout=5)
    updates = result.get("result", [])
    if updates:
        last_id = max(u["update_id"] for u in updates)
        api("getUpdates", offset=last_id + 1, timeout=0)  # ack — clears the queue
    return updates

# ── Supabase helpers ──────────────────────────────────────────────────────────

def supa_get(table, query=""):
    """Returns None on a genuine connection/HTTP failure, [] only for a real
    empty result — so a Supabase outage never gets reported as "nothing open"."""
    try:
        r = requests.get(f"{SUPA_URL}/rest/v1/{table}?{query}", headers=HDRS, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"  [Supabase] GET error: {e}")
        return None

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
        "/portfolio, /positions — Live P&amp;L of all open positions\n"
        "/watchlist  — Today's scanner watchlist\n"
        "/status     — Capital &amp; win-rate summary\n"
        "/scan       — Run scanner now\n"
        "/help       — Show this message"
    )

def cmd_portfolio():
    trades = supa_get("p15_trades", "status=eq.OPEN&select=*")
    cap_r  = supa_get("p15_capital", "select=*")
    if trades is None or cap_r is None:
        return "⚠️ Couldn't reach Supabase right now — try again in a minute."
    capital = cap_r[0] if cap_r else {
        "initial": 500000, "available": 500000, "invested": 0,
        "total_pnl": 0, "total_trades": 0, "winning_trades": 0
    }
    now = datetime.now(IST)

    if not trades:
        snap  = "📊 <b>Portfolio Snapshot</b>\n\n"
        snap += "📭 No open positions\n\n"
        snap += f"💰 Available: ₹{capital['available']:,.0f} / ₹{capital['initial']:,.0f}\n"
        if capital["total_trades"] > 0:
            wr = capital["winning_trades"] / capital["total_trades"] * 100
            snap += f"🎯 Win Rate: {wr:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)\n"
        snap += f"📈 Realised P&amp;L: ₹{capital['total_pnl']:+,.0f}"
        return snap

    lines = [f"📊 <b>Portfolio ({len(trades)} open)</b>\n"]
    total_unreal = 0

    for t in trades:
        cmp = get_cmp(t["symbol"]) or t.get("cmp") or t["entry_price"]
        pnl = (cmp - t["entry_price"]) * t["quantity"]
        pct = (cmp - t["entry_price"]) / t["entry_price"] * 100
        days_held = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"], "%Y-%m-%d")).days
        days_left = max(0, 90 - days_held)
        total_unreal += pnl
        arrow = "🟢" if pnl >= 0 else "🔴"
        warn  = " ⚠️" if days_left <= 10 else ""
        lines.append(
            f"{arrow} <b>{t['symbol']}</b>: ₹{cmp:.0f} ({pct:+.1f}%) "
            f"| P&amp;L: ₹{pnl:+.0f} | {days_held}d/90d{warn}"
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
    rows = supa_get("p15_watchlist", "id=eq.1&select=*")
    if rows is None:
        return "⚠️ Couldn't reach Supabase right now — try again in a minute."
    data = rows[0] if rows else None
    if not data or not data.get("symbols"):
        return "📭 <b>Watchlist</b>\n\nNo signals in today's scan."

    nifty = data.get("nifty_status", "UNKNOWN")
    nifty_emoji = {"STRONG": "🟢", "CAUTION": "🟡", "AVOID": "🔴"}.get(nifty, "⚪")
    nifty_cmp = data.get("nifty_cmp")

    lines = [f"📋 <b>Watchlist — {data.get('trade_date','?')}</b>",
             f"{nifty_emoji} Nifty: <b>{nifty}</b>" + (f" (₹{nifty_cmp:,.0f})" if nifty_cmp else "") + "\n"]
    for sym in data["symbols"]:
        lines.append(f"• <b>{sym}</b>")
    return "\n".join(lines)

def cmd_status():
    cap_r  = supa_get("p15_capital", "select=*")
    trades = supa_get("p15_trades", "status=eq.OPEN&select=id")
    if cap_r is None or trades is None:
        return "⚠️ Couldn't reach Supabase right now — try again in a minute."
    capital = cap_r[0] if cap_r else {
        "initial": 500000, "available": 500000, "invested": 0,
        "total_pnl": 0, "total_trades": 0, "winning_trades": 0
    }
    used_pct = capital["invested"] / capital["initial"] * 100 if capital["initial"] > 0 else 0
    win_rate = (
        capital["winning_trades"] / capital["total_trades"] * 100
        if capital["total_trades"] > 0 else 0
    )
    now = datetime.now(IST)

    lines = [
        "⚡ <b>Power 15 Status</b>",
        f"🕐 {now.strftime('%d %b %Y %H:%M IST')}\n",
        f"💰 Available: ₹{capital['available']:,.0f}",
        f"📦 Invested:  ₹{capital['invested']:,.0f} ({used_pct:.0f}% deployed)",
        f"📈 Realised P&amp;L: ₹{capital['total_pnl']:+,.0f}",
        f"📊 Open Positions: {len(trades)}",
    ]
    if capital["total_trades"] > 0:
        lines.append(
            f"🎯 Win Rate: {win_rate:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)"
        )
    return "\n".join(lines)

def cmd_scan(chat_id):
    send(chat_id, "⏳ Running scanner... this may take 30–60 seconds.")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "scanner.py")],
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

# ── Dispatch ──────────────────────────────────────────────────────────────────

def handle_message(message):
    chat_id = message["chat"]["id"]
    text    = message.get("text", "").strip().lower().split()[0] if message.get("text") else ""

    if text == "/help"                       : send(chat_id, cmd_help())
    elif text in ("/portfolio", "/positions"): send(chat_id, cmd_portfolio())
    elif text == "/watchlist"                : send(chat_id, cmd_watchlist())
    elif text == "/status"                   : send(chat_id, cmd_status())
    elif text == "/scan"                     : send(chat_id, cmd_scan(chat_id))
    elif text.startswith("/"):
        send(chat_id, "❓ Unknown command. Send /help for the list.")

def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    print(f"[Telegram Bot Check — {datetime.now(IST).strftime('%d %b %Y %H:%M IST')}]")
    updates = get_pending_updates()
    print(f"  {len(updates)} pending update(s)")
    for update in updates:
        msg = update.get("message") or update.get("edited_message")
        if msg:
            try:
                handle_message(msg)
            except Exception as e:
                print(f"  [Handler] error: {e}")
    print("  Done")

if __name__ == "__main__":
    main()
