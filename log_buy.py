import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "trade_log.json")

def log_buy(symbol, entry_price, quantity):
    trades = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            trades = json.load(f)
    trade = {
        "symbol":      symbol.upper(),
        "entry_price": entry_price,
        "quantity":    quantity,
        "entry_date":  datetime.today().strftime("%Y-%m-%d"),
        "status":      "OPEN",
    }
    trades.append(trade)
    with open(LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)
    print(f"  Logged: BUY {quantity} x {symbol} @ Rs.{entry_price}")

if __name__ == "__main__":
    print("Log a buy trade:")
    symbol = input("  Symbol (e.g. SBIN): ").strip().upper()
    price  = float(input("  Entry price: "))
    qty    = int(input("  Quantity: "))
    log_buy(symbol, price, qty)
    print("  Done! Run sell_alert.py to check exit signals.")