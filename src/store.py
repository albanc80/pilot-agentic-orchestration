"""Approvals and the idempotent mock outbox. SQLite, local only."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, sqlite3, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path

SECRET_FILE = Path(os.environ.get("PILOT_STATE_DIR", Path.home() / ".openclaw/workspace/fdu/pilot-state")) / "approval.key"


def _secret():
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    key = os.urandom(32)
    SECRET_FILE.write_bytes(key)
    SECRET_FILE.chmod(0o600)
    return key


class Store:
    def __init__(self, path=None):
        path = path or str(Path(os.environ.get("PILOT_STATE_DIR", Path.home() / ".openclaw/workspace/fdu/pilot-state")) / "pilot.db")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS approvals(
              token TEXT PRIMARY KEY, request_id TEXT, plan_hash TEXT, approver TEXT, scope TEXT, issued_at TEXT);
            CREATE TABLE IF NOT EXISTS outbox(
              idempotency_key TEXT PRIMARY KEY, request_id TEXT, plan_hash TEXT, created_at TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS audit(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, kind TEXT, correlation_id TEXT, detail TEXT);
            """)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def _audit(self, kind, correlation_id, detail):
        with self._conn() as c:
            c.execute("INSERT INTO audit(at,kind,correlation_id,detail) VALUES(?,?,?,?)",
                      (datetime.now(timezone.utc).isoformat(), kind, correlation_id, json.dumps(detail)))

    def issue_approval(self, request_id, plan_hash, approver, scope="mock_execute"):
        if not approver or approver.startswith("agent") or approver == "model":
            raise ValueError("approval must be an authorized human identity")
        if scope != "mock_execute":
            raise ValueError("scope must be mock_execute")
        msg = f"{request_id}|{plan_hash}|{approver}|{scope}".encode()
        token = base64.urlsafe_b64encode(hmac.new(_secret(), msg, hashlib.sha256).digest()).decode()
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO approvals VALUES(?,?,?,?,?,?)",
                      (token, request_id, plan_hash, approver, scope, datetime.now(timezone.utc).isoformat()))
        self._audit("approval_issued", request_id, {"approver": approver, "plan_hash": plan_hash})
        return token

    def verify_approval(self, token, request_id, plan_hash):
        row = None
        with self._conn() as c:
            row = c.execute("SELECT request_id,plan_hash,approver,scope FROM approvals WHERE token=?", (token,)).fetchone()
        if not row:
            return False
        rid, ph, approver, scope = row
        msg = f"{rid}|{ph}|{approver}|{scope}".encode()
        want = base64.urlsafe_b64encode(hmac.new(_secret(), msg, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(want, token) and rid == request_id and ph == plan_hash and scope == "mock_execute"

    def execute_mock(self, request_id, plan_hash, token, payload=None):
        """Exactly-once mock side effect. Returns dict with created flag."""
        if not self.verify_approval(token, request_id, plan_hash):
            self._audit("execution_denied", request_id, {"reason": "invalid_or_missing_approval"})
            return {"status": "DENIED", "reason": "INVALID_OR_MISSING_APPROVAL", "created": False}
        key = f"{request_id}:{plan_hash}"
        with self._lock:
            c = self._conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                event_id = str(uuid.uuid4())
                c.execute("INSERT OR IGNORE INTO outbox(idempotency_key,request_id,plan_hash,created_at,payload) VALUES(?,?,?,?,?)",
                          (key, request_id, plan_hash, datetime.now(timezone.utc).isoformat(), json.dumps(payload or {})))
                created = c.total_changes > 0
                row = c.execute("SELECT idempotency_key,created_at FROM outbox WHERE idempotency_key=?", (key,)).fetchone()
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
            finally:
                c.close()
        self._audit("mock_executed" if created else "mock_duplicate_suppressed", request_id, {"key": key})
        return {"status": "OK", "created": created, "event_key": row[0], "created_at": row[1]}

    def outbox_count(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def audit_events(self, correlation_id=None):
        q = "SELECT at,kind,correlation_id,detail FROM audit"
        args = ()
        if correlation_id:
            q += " WHERE correlation_id=?"
            args = (correlation_id,)
        with self._conn() as c:
            return [{"at": r[0], "kind": r[1], "correlation_id": r[2], "detail": json.loads(r[3])} for r in c.execute(q, args)]
