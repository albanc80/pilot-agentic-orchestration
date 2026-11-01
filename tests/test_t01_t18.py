import json, threading, tempfile, unittest
from datetime import datetime, timedelta, timezone

from src.core import evaluate, plan_hash, CONTRACT_VERSION
from src.store import Store

NOW = datetime.now(timezone.utc)

def iso(dt): return dt.replace(microsecond=0).isoformat()

def world(**over):
    w = {
        "assets": {"ASSET-1": {"sku": "PUMP-SEAL-42", "unit": "ea"}},
        "stock": [
            {"depot_id": "D1", "sku": "PUMP-SEAL-42", "quantity": 10, "observed_at": iso(NOW - timedelta(minutes=10)), "serviceable": True, "maintenance_hold": False},
            {"depot_id": "D2", "sku": "PUMP-SEAL-42", "quantity": 3, "observed_at": iso(NOW - timedelta(minutes=5)), "serviceable": True, "maintenance_hold": False},
        ],
        "certifications": {"ASSET-1": iso(NOW + timedelta(days=90))},
        "routes": [
            {"depot_id": "D1", "destination": "ROTTERDAM", "transit_days": 4, "mock_trade_clearance": True, "mock_route_eligible": True},
            {"depot_id": "D2", "destination": "ROTTERDAM", "transit_days": 3, "mock_trade_clearance": True, "mock_route_eligible": True},
        ],
        "manufacturing": {"PUMP-SEAL-42": {"available": True, "lead_days": 21, "advisory_only": True}},
        "connector_status": {"erp": "ok"},
    }
    w.update(over); return w

def req(**over):
    r = {
        "contract_version": CONTRACT_VERSION,
        "request_id": "REQ-1",
        "insight": {"asset_id": "ASSET-1", "observed_at": iso(NOW - timedelta(minutes=5)), "confidence": 0.9},
        "demand": {"sku": "PUMP-SEAL-42", "quantity": 5, "need_by": iso(NOW + timedelta(days=30)), "destination": "ROTTERDAM"},
    }
    for k, v in over.items():
        r[k] = {**r[k], **v} if k in ("insight", "demand") else v
    return r

class TSuite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_01_eligible(self):
        out = evaluate(req(), world(), now=NOW)
        self.assertEqual(out["status"], "ELIGIBLE")
        p = out["plan"]
        self.assertIn(p["depot_id"], {"D1", "D2"})
        self.assertTrue(p["provenance"]); self.assertTrue(p["restrictions"])
        self.assertFalse(p["live_execution_allowed"])
        self.assertEqual(out["plan_hash"], plan_hash(p))

    def test_02_stale_insight(self):
        out = evaluate(req(insight={"observed_at": iso(NOW - timedelta(minutes=45))}), world(), now=NOW)
        self.assertEqual(out["status"], "BLOCKED"); self.assertTrue(out["reason"].startswith("STALE"))

    def test_03_low_confidence(self):
        out = evaluate(req(insight={"confidence": 0.5}), world(), now=NOW)
        self.assertEqual(out["reason"], "LOW_CONFIDENCE")

    def test_04_unknown_asset(self):
        out = evaluate(req(insight={"asset_id": "ASSET-UNKNOWN"}), world(), now=NOW)
        self.assertEqual(out["reason"], "UNKNOWN_ASSET")

    def test_05_bad_stock(self):
        stale = [{"depot_id": "D1", "sku": "PUMP-SEAL-42", "quantity": 99, "observed_at": iso(NOW - timedelta(hours=3)), "serviceable": True}]
        short = [{"depot_id": "D1", "sku": "PUMP-SEAL-42", "quantity": 1, "observed_at": iso(NOW - timedelta(minutes=5)), "serviceable": True}]
        for stock in (stale, short):
            out = evaluate(req(), world(stock=stock), now=NOW)
            self.assertEqual(out["status"], "BLOCKED"); self.assertFalse(out["live_execution_allowed"])

    def test_06_maintenance_hold(self):
        stock = [{"depot_id": "D1", "sku": "PUMP-SEAL-42", "quantity": 10, "observed_at": iso(NOW - timedelta(minutes=5)), "serviceable": True, "maintenance_hold": True}]
        self.assertEqual(evaluate(req(), world(stock=stock), now=NOW)["status"], "BLOCKED")

    def test_07_cert_before_eta(self):
        out = evaluate(req(), world(certifications={"ASSET-1": iso(NOW + timedelta(days=2))}), now=NOW)
        self.assertEqual(out["status"], "BLOCKED"); self.assertIn("CERTIFICATION", json.dumps(out))

    def test_08_trade_unclear(self):
        routes = [{"depot_id": "D1", "destination": "ROTTERDAM", "transit_days": 4, "mock_trade_clearance": False, "mock_route_eligible": True}]
        out = evaluate(req(), world(routes=routes), now=NOW)
        self.assertEqual(out["status"], "BLOCKED"); self.assertIn("TRADE", json.dumps(out))

    def test_09_eta_after_need_by(self):
        out = evaluate(req(demand={"need_by": iso(NOW + timedelta(days=2))}), world(), now=NOW)
        self.assertEqual(out["status"], "BLOCKED"); self.assertIn("ETA_AFTER_NEED_BY", json.dumps(out))
        fast = world(routes=[{"depot_id": "D1", "destination": "ROTTERDAM", "transit_days": 1, "mock_trade_clearance": True, "mock_route_eligible": True}])
        self.assertEqual(evaluate(req(demand={"need_by": iso(NOW + timedelta(days=2))}), fast, now=NOW)["status"], "ELIGIBLE")

    def test_10_manufacturing_fallback(self):
        out = evaluate(req(), world(stock=[]), now=NOW)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(out["manufacturing_fallback"]["advisory_only"])

    def test_11_approval_required(self):
        st = Store(self.tmp + "/p.db")
        out = evaluate(req(), world(), now=NOW)
        self.assertEqual(st.execute_mock("REQ-1", out["plan_hash"], "forged")["status"], "DENIED")
        with self.assertRaises(ValueError):
            st.issue_approval("REQ-1", out["plan_hash"], "agent-self")
        tok = st.issue_approval("REQ-1", out["plan_hash"], "human:beto")
        self.assertTrue(st.execute_mock("REQ-1", out["plan_hash"], tok)["created"])

    def test_12_duplicate_suppressed(self):
        st = Store(self.tmp + "/p.db")
        out = evaluate(req(), world(), now=NOW)
        tok = st.issue_approval("REQ-1", out["plan_hash"], "human:beto")
        self.assertTrue(st.execute_mock("REQ-1", out["plan_hash"], tok)["created"])
        self.assertFalse(st.execute_mock("REQ-1", out["plan_hash"], tok)["created"])
        self.assertEqual(st.outbox_count(), 1)

    def test_13_concurrent_duplicates(self):
        st = Store(self.tmp + "/p.db")
        out = evaluate(req(), world(), now=NOW)
        tok = st.issue_approval("REQ-1", out["plan_hash"], "human:beto")
        res = []
        def w(): res.append(st.execute_mock("REQ-1", out["plan_hash"], tok)["created"])
        ts = [threading.Thread(target=w) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(res.count(True), 1); self.assertEqual(st.outbox_count(), 1)

    def test_14_prompt_injection(self):
        out = evaluate(req(demand={"sku": "PUMP-SEAL-42 https://evil.example"}), world(), now=NOW)
        self.assertEqual(out["reason"], "PROHIBITED_INPUT")

    def test_15_unknown_contract(self):
        self.assertEqual(evaluate(req(contract_version="9.9"), world(), now=NOW)["reason"], "UNKNOWN_CONTRACT_VERSION")

    def test_16_connector_unavailable(self):
        out = evaluate(req(), world(connector_status={"erp": "unavailable"}), now=NOW)
        self.assertEqual(out["reason"], "CONNECTOR_UNAVAILABLE"); self.assertFalse(out["live_execution_allowed"])

    def test_17_dashboard_visibility(self):
        from src.api import render_dashboard
        out = evaluate(req(), world(), now=NOW)
        html = render_dashboard([{"request_id": "REQ-1", "status": "ELIGIBLE", "plan": out["plan"]}])
        for token in ("mock only", "provenance", "observed_at", "restrictions", "human authority", "uncertainty"):
            self.assertIn(token, html.lower())

    def test_18_audit_traceable(self):
        st = Store(self.tmp + "/p.db")
        out = evaluate(req(), world(), now=NOW)
        tok = st.issue_approval("REQ-1", out["plan_hash"], "human:beto")
        st.execute_mock("REQ-1", out["plan_hash"], tok)
        ev = st.audit_events("REQ-1")
        self.assertTrue({"approval_issued", "mock_executed"} <= {e["kind"] for e in ev})
        self.assertTrue(all(e["correlation_id"] == "REQ-1" for e in ev))

if __name__ == "__main__":
    unittest.main()
