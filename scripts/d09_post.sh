#!/usr/bin/env bash
# D09 post-restart verification. Run AFTER the gateway is back.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PRE="$REPO/evidence/d09-pre.json"
OUT="$REPO/evidence/d09-post.json"
DB="$HOME/.openclaw/workspace/fdu/pilot-state/pilot.db"
python3 - "$REPO" "$PRE" "$OUT" "$DB" <<'PY'
import json, subprocess, sys, hashlib, os, datetime, sqlite3
repo, pre, out, db = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""
before = json.load(open(pre))
after = {
  "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "git_head": sh("git -C %s rev-parse HEAD" % repo),
  "config_sha256": hashlib.sha256(open(os.path.expanduser("~/.openclaw/openclaw.json"),"rb").read()).hexdigest(),
  "gateway_pid": sh("pgrep -f 'openclaw.*gateway' | head -1"),
  "version": sh("openclaw --version"),
  "sandbox_containers": len([l for l in sh("docker ps --format '{{.Names}}'").splitlines() if "openclaw-sbx" in l]),
  "outbox_count": None,
}
if os.path.exists(db):
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    after["outbox_count"] = c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    c.close()
checks = {
  "gateway_restarted": bool(after["gateway_pid"]) and after["gateway_pid"] != before["gateway_pid"],
  "config_unchanged": after["config_sha256"] == before["config_sha256"],
  "git_head_unchanged": after["git_head"] == before["git_head"],
  "outbox_unchanged": after["outbox_count"] == before["outbox_count"],
}
json.dump({"before": before, "after": after, "checks": checks, "pass": all(checks.values())}, open(out,"w"), indent=2)
print(json.dumps({"checks": checks, "pass": all(checks.values())}, indent=2))
print("Evidence: "+out)
PY
