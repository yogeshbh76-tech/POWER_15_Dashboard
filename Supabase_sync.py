"""
Power 15 — Supabase Sync v2.0
Fixed: proper upsert with on_conflict, peak_cmp field, null safety
"""
import json, os, requests

SUPABASE_URL = "https://xlrbmsmrgosqbioojqfz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM"
LOG_FILE = r"C:\power15_bot\trade_log.json"
CAP_FILE = r"C:\power15_bot\paper_capital.json"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}

def safe_float(v, default=0.0):
    try: return float(v) if v is not None else default
    except: return default

def safe_int(v, default=0):
    try: return int(v) if v is not None else default
    except: return default

def upsert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=id"
    if not isinstance(data, list):
        data = [data]
    resp = requests.post(url, headers=HEADERS, json=data, timeout=15)
    if resp.status_code not in (200, 201):
        print(f"  Upsert error [{table}]: {resp.status_code} — {resp.text[:200]}")
        return False
    return True

def patch_trade(trade_id, fields):
    """Directly PATCH a single trade by ID."""
    url = f"{SUPABASE_URL}/rest/v1/p15_trades?id=eq.{trade_id}"
    h = {**HEADERS, "Prefer": "return=minimal"}
    resp = requests.patch(url, headers=h, json=fields, timeout=15)
    return resp.status_code in (200, 204)

def normalize_trade(t, idx):
    return {
        "id":           safe_int(t.get("id"), idx + 1),
        "symbol":       str(t.get("symbol", "")),
        "entry_date":   str(t.get("entry_date", "")),
        "entry_price":  safe_float(t.get("entry_price")),
        "quantity":     safe_int(t.get("quantity")),
        "sl_price":     safe_float(t.get("sl_price")),
        "peak_cmp":     safe_float(t.get("peak_cmp")) or None,
        "status":       str(t.get("status", "OPEN")),
        "exit_date":    t.get("exit_date") or None,
        "exit_price":   safe_float(t.get("exit_price")) if t.get("exit_price") else None,
        "pnl":          safe_float(t.get("pnl")),
        "pnl_pct":      safe_float(t.get("pnl_pct")),
        "exit_reason":  t.get("exit_reason") or None,
        "sector":       str(t.get("sector", "")),
        "tier":         safe_int(t.get("tier"), 2),
    }

def sync_capital():
    cap = {}
    if os.path.exists(CAP_FILE):
        try: cap = json.load(open(CAP_FILE, encoding="utf-8"))
        except: pass
    data = {
        "id":             1,
        "initial":        safe_float(cap.get("initial"), 500000),
        "available":      safe_float(cap.get("available"), 500000),
        "invested":       safe_float(cap.get("invested")),
        "total_pnl":      safe_float(cap.get("total_pnl")),
        "total_trades":   safe_int(cap.get("total_trades")),
        "winning_trades": safe_int(cap.get("winning_trades")),
    }
    ok = upsert("p15_capital", data)
    print(f"  Capital: {'✅' if ok else '❌'}")
    return ok

def sync_trades():
    trades = []
    if os.path.exists(LOG_FILE):
        try: trades = json.load(open(LOG_FILE, encoding="utf-8"))
        except: pass
    if not trades:
        print("  Trades: ✅ (0 trades)")
        return True
    normalized = [normalize_trade(t, i) for i, t in enumerate(trades)]
    ok = upsert("p15_trades", normalized)
    print(f"  Trades: {'✅' if ok else '❌'} ({len(normalized)} trades)")
    return ok

def sync_all():
    print("[Supabase Sync]")
    ok1 = sync_capital()
    ok2 = sync_trades()
    if ok1 and ok2:
        print("  ✅ Sync complete")
    else:
        print("  ⚠️  Some syncs failed")
    return ok1 and ok2

if __name__ == "__main__":
    sync_all()
