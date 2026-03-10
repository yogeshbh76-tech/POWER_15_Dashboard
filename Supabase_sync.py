import json, os, requests
from datetime import datetime

SUPABASE_URL = "https://xlrbmsmrgosqbioojqfz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhscmJtc21yZ29zcWJpb29qcWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTk2ODYsImV4cCI6MjA4ODczNTY4Nn0.FDMG6lKMXtMpESj3bEH1HbyTrJyPbn-Tn0WitMkLxiM"
LOG_FILE = r"C:\power15_bot\trade_log.json"
CAP_FILE = r"C:\power15_bot\paper_capital.json"
H = {"apikey":SUPABASE_KEY,"Authorization":"Bearer "+SUPABASE_KEY,"Content-Type":"application/json","Prefer":"resolution=merge-duplicates"}

def upsert(table, data):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=H, json=data, timeout=15)
    if r.status_code not in (200,201): print(f"  Error: {r.status_code} {r.text[:300]}"); return False
    return True

def sync_all():
    print("\n[Supabase Sync]")
    cap = json.load(open(CAP_FILE)) if os.path.exists(CAP_FILE) else {"initial":500000,"available":500000,"invested":0,"total_pnl":0,"total_trades":0,"winning_trades":0}
    cap = {"id":1,"initial":cap.get("initial",500000),"available":cap.get("available",500000),"invested":cap.get("invested",0),"total_pnl":cap.get("total_pnl",0),"total_trades":cap.get("total_trades",0),"winning_trades":cap.get("winning_trades",0)}
    print("  Capital sync: "+("OK" if upsert("p15_capital",cap) else "FAILED"))
    trades = json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else []
    for i,t in enumerate(trades): t["id"]=i+1
    if trades: print("  Trades sync: "+("OK" if upsert("p15_trades",trades) else "FAILED")+f" ({len(trades)} trades)")
    else: print("  Trades sync: OK (0 trades)")
    print("  Done\n")

sync_all()
