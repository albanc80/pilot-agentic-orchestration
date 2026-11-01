#!/usr/bin/env bash
# D09 pre-restart snapshot. Run BEFORE restarting the gateway.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/evidence/d09-pre.json"
DB="$HOME/.openclaw/workspace/fdu/pilot-state/pilot.db"
python3 - "$REPO" "$OUT" "$DB" <<'PY'
import json, subprocess, sys, hashlib, os, datetime, sqlite3
repo, out, db = sys.argv[1], sys.argv[2], sys.argv[3]
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""
snap = {
  "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "git_head": sh("git -C %s rev-parse HEAD" % repo),
  "config_sha256": hashlib.sha256(open(os.path.expanduser("~/.openclaw/openclaw.json"),"rb").read()).hexdigest(),
  "gateway_pid": sh("pgrep -f 'openclaw.*gateway' | head -1"),
  "sandbox_containers": len([l for l in sh("docker ps --format '{{.Names}}'").splitlines() if "openclaw-sbx" in l]),
  "outbox_count": None,
}
if os.path.exists(db):
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    snap["outbox_count"] = c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    c.close()
json.dump(snap, open(out,"w"), indent=2)
print(json.dumps(snap, indent=2))
print("\nNow run:  systemctl --user restart openclaw-gateway")
PY
