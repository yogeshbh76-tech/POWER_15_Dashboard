import requests, os, json
from datetime import datetime
from dotenv import load_dotenv
import pytz

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
IST       = pytz.timezone("Asia/Kolkata")
LOG_FILE  = os.path.join(BASE_DIR, "trade_log.json")
CAP_FILE  = os.path.join(BASE_DIR, "paper_capital.json")
QUANTITY  = int(os.environ.get("QUANTITY", 2))

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("  Telegram not configured")
        return False
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, data=data, timeout=10)
    return resp.json().get("ok", False)

def send_buy_alert(triggered_stocks, quantity=2):
    if not triggered_stocks:
        msg = "⚡ <b>Power 15 Scan Complete</b>\n\nNo signals today. Markets may be flat.\n\n" + portfolio_snapshot()
    else:
        lines = [f"⚡ <b>Power 15 — {len(triggered_stocks)} BUY Signal(s)!</b>\n"]
        total = 0
        for s in triggered_stocks:
            emoji = "🔥" if s["tier"]==1 else "✅" if s["tier"]==2 else "⚡"
            amt   = s["close"] * quantity
            total += amt
            lines.append(
                f"{emoji} <b>{s['symbol']}</b> — Tier {s['tier']} | {s['sector']}\n"
                f"   Rs.{s['close']:.2f} ({s['change']:+.2f}%)\n"
                f"   BUY {quantity} QTY = Rs.{amt:.0f}"
            )
        lines.append(f"\n💰 Total Capital Needed: Rs.{total:,.0f}")
        lines.append("📅 Exit: 90 days | SL: -8%")
        lines.append("\n" + portfolio_snapshot())
        msg = "\n\n".join(lines)
    return send_telegram(msg)

def send_sell_alert(sell_signals):
    if not sell_signals:
        return
    lines = [f"🔴 <b>Power 15 — {len(sell_signals)} SELL Signal(s)!</b>\n"]
    for s in sell_signals:
        emoji = "🔴" if s["urgency"] == "exit" else "🟡"
        lines.append(
            f"{emoji} <b>{s['symbol']}</b>\n"
            f"   Entry: Rs.{s['entry_price']:.2f} → CMP: Rs.{s['cmp']:.2f}\n"
            f"   P&L: Rs.{s['pnl']:+.0f} ({s['pct_change']:+.1f}%)\n"
            f"   Reason: {s['reason']}\n"
            f"   {'SELL NOW on Zerodha!' if s['urgency']=='exit' else 'Consider selling'}"
        )
    lines.append("\n" + portfolio_snapshot())
    return send_telegram("\n\n".join(lines))

def portfolio_snapshot():
    try:
        trades  = json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else []
        capital = json.load(open(CAP_FILE))  if os.path.exists(CAP_FILE) else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
        open_tr = [t for t in trades if t["status"] == "OPEN"]
        now     = datetime.now(IST)

        used_pct = (capital["invested"] / capital["initial"] * 100) if capital["initial"] > 0 else 0
        win_rate = (capital["winning_trades"] / capital["total_trades"] * 100) if capital["total_trades"] > 0 else 0

        lines = ["📊 <b>Portfolio Snapshot</b>"]
        lines.append(f"💰 Available: Rs.{capital['available']:,.0f} / Rs.{capital['initial']:,.0f} ({100-used_pct:.0f}% free)")
        lines.append(f"📈 Realised P&L: Rs.{capital['total_pnl']:+,.0f}")
        if capital["total_trades"] > 0:
            lines.append(f"🎯 Win Rate: {win_rate:.0f}% ({capital['winning_trades']}/{capital['total_trades']} trades)")

        if open_tr:
            lines.append(f"\n<b>Open Positions ({len(open_tr)}):</b>")
            for t in open_tr:
                days = (now.replace(tzinfo=None) - datetime.strptime(t["entry_date"],"%Y-%m-%d")).days
                left = max(0, 90 - days)
                emoji = "🟢" if left > 30 else "🟡" if left > 10 else "🔴"
                lines.append(f"{emoji} <b>{t['symbol']}</b> @ Rs.{t['entry_price']:.0f} | {days}d held | {left}d left | SL: Rs.{t['sl_price']:.0f}")
        else:
            lines.append("\nNo open positions yet.")

        return "\n".join(lines)
    except Exception as e:
        return f"Portfolio: Error loading data ({e})"

def send_portfolio_update():
    now = datetime.now(IST)
    msg = f"📊 <b>Power 15 — Daily Portfolio Update</b>\n{now.strftime('%d %b %Y %H:%M IST')}\n\n" + portfolio_snapshot()
    return send_telegram(msg)

if __name__ == "__main__":
    print("Sending portfolio snapshot to Telegram...")
    ok = send_portfolio_update()
    print("Sent!" if ok else "Failed — check BOT_TOKEN and CHAT_ID in .env")