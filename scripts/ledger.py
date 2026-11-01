#!/usr/bin/env python3
"""Run ledger: export gateway audit_events to JSONL + summary.
Read-only. Usage: ledger.py [--since ISO] [--out PATH] [--summary]
"""
import argparse, json, sqlite3, sys, pathlib, collections, datetime

DB="file:/home/alberto/.openclaw/state/openclaw.sqlite?mode=ro"
COLS=["occurred_at","kind","action","status","error_code","agent_id","session_key","run_id","tool_name","duration_ms"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--since",default="1970-01-01T00:00:00")
    ap.add_argument("--out",default=str(pathlib.Path(__file__).resolve().parent.parent/"ledger"/"ledger.jsonl"))
    ap.add_argument("--summary",action="store_true")
    a=ap.parse_args()
    since_ms=0
    try:
        since_ms=int(datetime.datetime.fromisoformat(a.since).timestamp()*1000)
    except Exception:
        pass
    con=sqlite3.connect(DB,uri=True)
    q=f"select {','.join(COLS)} from audit_events where occurred_at>=? order by sequence"
    rows=con.execute(q,(since_ms,)).fetchall()
    out=pathlib.Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(dict(zip(COLS,r)),separators=(",",":"))+"\n")
    print(f"wrote {len(rows)} events -> {out}")
    if a.summary:
        by=collections.Counter((r[1],r[2],r[3]) for r in rows)
        print("\nkind/action/status:")
        for k,v in by.most_common(15): print(f"  {k[0]} {k[1]} {k[2]}: {v}")
        errs=collections.Counter(r[4] for r in rows if r[4])
        if errs:
            print("\nerror codes:")
            for k,v in errs.most_common(10): print(f"  {k}: {v}")
        agents=collections.Counter(r[5] for r in rows if r[5])
        print("\nagents:",dict(agents.most_common(10)))

if __name__=="__main__": main()
