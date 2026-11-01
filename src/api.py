"""Mock-only HTTP API and dashboard. Standard library only."""
from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .core import evaluate, expand_world
from .store import Store

WORLD = expand_world(json.loads((Path(__file__).resolve().parent.parent / "fixtures" / "world.json").read_text()))
STORE = Store()
RECENT = []


def render_dashboard(entries):
    rows = []
    for e in entries:
        plan = e.get("plan") or {}
        prov = "<br>".join(f"{p['source']} @ {p['observed_at']}" for p in plan.get("provenance", [])) or "&mdash;"
        rows.append(f"""<tr><td>{e.get('request_id')}</td><td>{e.get('status')}</td>
<td>{plan.get('depot_id','')}</td><td>{plan.get('eta','')}</td>
<td>{', '.join(plan.get('restrictions', [])) or '&mdash;'}</td>
<td>{json.dumps(plan.get('uncertainty', {}))}</td><td>{plan.get('human_authority','')}</td>
<td class="prov">{prov}</td><td>{e.get('reason','')}</td></tr>""")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>OFDL Pilot — mock only</title>
<style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:6px;font-size:13px;vertical-align:top}}.prov{{font-size:11px;color:#444}}
.badge{{background:#111;color:#fff;padding:2px 6px;border-radius:4px}}</style></head><body>
<h2>Oilfield Delivery Orchestrator <span class="badge">MOCK ONLY — NO PHYSICAL MOVEMENT</span></h2>
<p>Human authority is required before any execution. Every plan shows source, age, restrictions and uncertainty.</p>
<table><thead><tr><th>Request</th><th>Status</th><th>Depot</th><th>ETA</th><th>Restrictions</th>
<th>Uncertainty</th><th>Human authority</th><th>Provenance (source @ observed_at)</th><th>Reason</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan=9>No plans yet</td></tr>'}</tbody></table></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._html(render_dashboard(RECENT[-50:]))
        if u.path == "/status":
            rid = (parse_qs(u.query).get("request_id") or [""])[0]
            return self._json(200, {"request_id": rid, "events": STORE.audit_events(rid or None)[-50:], "outbox": STORE.outbox_count()})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "invalid json"})
        if u.path == "/plan":
            req = body.get("request", body)
            out = evaluate(req, WORLD)
            RECENT.append({"request_id": req.get("request_id"), "status": out["status"], **out})
            return self._json(200, out)
        if u.path == "/approve":
            try:
                tok = STORE.issue_approval(body["request_id"], body["plan_hash"], body.get("approver", ""))
            except Exception as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(200, {"token": tok})
        if u.path == "/execute":
            return self._json(200, STORE.execute_mock(body.get("request_id"), body.get("plan_hash"), body.get("token")))
        self._json(404, {"error": "not found"})


def main():
    port = int(os.environ.get("PILOT_PORT", "8787"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
