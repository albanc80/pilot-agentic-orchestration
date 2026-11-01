"""Offline tests only; no OpenClaw, GitHub or third-party calls."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pilot'))
sys.path.insert(0, str(ROOT / 'scripts'))
from plan_delivery import plan
from mock_execute import execute_mock, Denied
from validate_contracts import validate, ContractError
from render_agent_overlay import make_overlay, ROLES

CASE = json.loads((ROOT / 'pilot/fixtures/sample-worldwide-request.json').read_text())
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


class DeliveryTests(unittest.TestCase):
    def test_happy_path_chooses_serviceable_depot(self):
        result = plan(CASE, NOW)
        self.assertEqual(result['status'], 'AWAITING_HUMAN_MOCK_APPROVAL')
        self.assertEqual(result['selected_scenario']['depot_id'], 'HOUSTON-TX')
        self.assertFalse(result['live_execution_allowed'])

    def test_stale_insight_blocks(self):
        c = deepcopy(CASE)
        c['insight']['observed_at'] = '2026-10-30T11:00:00Z'
        self.assertEqual(plan(c, NOW)['reason'], 'STALE_OR_FUTURE_INSIGHT')

    def test_low_confidence_blocks(self):
        c = deepcopy(CASE)
        c['insight']['confidence'] = 0.5
        self.assertEqual(plan(c, NOW)['reason'], 'LOW_CONFIDENCE_INSIGHT')

    def test_bad_asset_identity_blocks(self):
        c = deepcopy(CASE)
        c['insight']['asset_identity_verified'] = False
        self.assertEqual(plan(c, NOW)['reason'], 'UNTRUSTED_IDENTITY_OR_UNITS')

    def test_hold_blocks_even_with_stock(self):
        c = deepcopy(CASE)
        c['depots'][0]['inventory'][0]['maintenance_hold'] = True
        self.assertEqual(plan(c, NOW)['status'], 'BLOCKED')

    def test_trade_not_cleared_blocks(self):
        c = deepcopy(CASE)
        c['depots'][0]['routes'][0]['mock_trade_clearance'] = False
        result = plan(c, NOW)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIn('MOCK_TRADE_OR_ROUTE_NOT_CLEARED', result['reason'])

    def test_cert_expired_blocks(self):
        c = deepcopy(CASE)
        c['depots'][0]['inventory'][0]['cert_valid_until'] = '2026-11-01T00:00:00Z'
        self.assertEqual(plan(c, NOW)['status'], 'BLOCKED')

    def test_inventory_stale_blocks(self):
        c = deepcopy(CASE)
        c['depots'][0]['stock_as_of'] = '2026-10-30T10:00:00Z'
        self.assertEqual(plan(c, NOW)['status'], 'BLOCKED')

    def test_manufacturing_fallback_is_advisory_only(self):
        c = deepcopy(CASE)
        c['depots'] = []
        res = plan(c, NOW)
        self.assertEqual(res['status'], 'BLOCKED')
        self.assertTrue(res['manufacturing_fallback']['advisory_only'])

    def test_no_real_data_accepted(self):
        c = deepcopy(CASE)
        c['synthetic'] = False
        self.assertEqual(plan(c, NOW)['reason'], 'ONLY_SYNTHETIC_DATA_ALLOWED')

    def test_missing_approval_denied(self):
        p = plan(CASE, NOW)
        with self.assertRaises(Denied):
            execute_mock(p, {}, {'events': []})

    def test_mismatched_approval_denied(self):
        p = plan(CASE, NOW)
        approval = {'authorization': 'HUMAN_APPROVED_MOCK_ONLY', 'scope': 'MOCK_EXECUTE', 'approved_by': 'human-simulator', 'plan_id': 'WRONG', 'request_id': p['request_id']}
        with self.assertRaises(Denied):
            execute_mock(p, approval, {'events': []})

    def test_mock_idempotent_single_event(self):
        p = plan(CASE, NOW)
        approval = {'authorization': 'HUMAN_APPROVED_MOCK_ONLY', 'scope': 'MOCK_EXECUTE', 'approved_by': 'human-simulator', 'plan_id': p['plan_id'], 'request_id': p['request_id']}
        first, ledger = execute_mock(p, approval, {'events': []})
        second, again = execute_mock(p, approval, ledger)
        self.assertEqual(first['status'], 'MOCK_EXECUTED')
        self.assertEqual(second['status'], 'ALREADY_SIMULATED')
        self.assertEqual(len(again['events']), 1)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.docs = [json.loads((ROOT / f'contracts/examples/{s}.json').read_text()) for s in ['delivery-contract', 'task-packet', 'evidence-packet']]

    def test_consistent_contracts(self):
        self.assertTrue(validate(*self.docs))

    def test_stale_contract_packet_denied(self):
        self.docs[1]['contract_version'] = 99
        with self.assertRaises(ContractError):
            validate(*self.docs)

    def test_unlisted_requirement_denied(self):
        self.docs[1]['source_requirements'].append('REQ-NOT-APPROVED')
        with self.assertRaises(ContractError):
            validate(*self.docs)

    def test_unapproved_live_action_denied(self):
        self.docs[0]['prohibited_actions'].remove('LIVE_TRANSACTION')
        with self.assertRaises(ContractError):
            validate(*self.docs)


class RouteTests(unittest.TestCase):
    def test_unique_allowlisted_fifteen_roles(self):
        ids = {r: r.replace('_', '-') for r in ROLES}
        overlay = make_overlay(ids)
        self.assertEqual(len(overlay['tools']['agentToAgent']['allow']), 15)
        self.assertEqual(overlay['agents']['entries'][ids['security_engineer']]['tools']['agentToAgent']['send'], [])
        self.assertEqual(overlay['agents']['entries'][ids['pod_lead']]['tools']['agentToAgent']['send'], [ids['fdu_outcome_lead']])
        self.assertEqual(overlay['agents']['entries'][ids['fdu_outcome_lead']]['subagents']['maxConcurrent'], 3)
        self.assertEqual(overlay['agents']['entries'][ids['fdu_outcome_lead']]['sandbox']['mode'], 'off')
        self.assertEqual(overlay['agents']['entries'][ids['pod_lead']]['sandbox']['mode'], 'off')
        self.assertIn('exec', overlay['agents']['entries'][ids['pod_lead']]['tools']['deny'])
        self.assertEqual(overlay['agents']['entries'][ids['backend_engineer']]['sandbox']['mode'], 'all')
        self.assertEqual(overlay['agents']['entries'][ids['fdu_outcome_lead']]['sandbox']['mode'], 'off')
        self.assertIn('exec', overlay['agents']['entries'][ids['fdu_outcome_lead']]['tools']['deny'])
        self.assertEqual(overlay['agents']['entries'][ids['backend_engineer']]['sandbox']['mode'], 'all')

    def test_missing_role_mapping_denied(self):
        with self.assertRaises(ValueError):
            make_overlay({'fdu_outcome_lead': 'my-id'})

    def test_duplicate_ids_denied(self):
        ids = {r: 'same-id' for r in ROLES}
        with self.assertRaises(ValueError):
            make_overlay(ids)


if __name__ == '__main__':
    unittest.main()
