#!/usr/bin/env python3
"""Simulate local dispatch in a JSON ledger. NO real connectors, transport or commitments.
Approval JSON is only a demonstration fixture; never a production authentication system.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile


class Denied(Exception):
    pass


def execute_mock(plan, approval, ledger):
    if plan.get('status') != 'AWAITING_HUMAN_MOCK_APPROVAL' or plan.get('mock_only') is not True or plan.get('live_execution_allowed') is not False:
        raise Denied('not an eligible mock-only plan')
    if approval.get('authorization') != 'HUMAN_APPROVED_MOCK_ONLY' or approval.get('scope') != 'MOCK_EXECUTE':
        raise Denied('missing mock execution approval fixture')
    if approval.get('plan_id') != plan['plan_id'] or approval.get('request_id') != plan['request_id']:
        raise Denied('approval scope mismatch')
    if not isinstance(approval.get('approved_by'), str) or not approval['approved_by'].strip():
        raise Denied('missing mock approver label')
    old = ledger.get('events', [])
    if any(ev['plan_id'] == plan['plan_id'] for ev in old):
        return {'status': 'ALREADY_SIMULATED', 'event_count': len(old)}, ledger
    event = {'event_type': 'MOCK_DISPATCH', 'plan_id': plan['plan_id'], 'request_id': plan['request_id'], 'depot_id': plan['selected_scenario']['depot_id'], 'approved_by_fixture': approval['approved_by'], 'notice': 'SIMULATION_ONLY_NO_REAL_FULFILLMENT'}
    result = {'status': 'MOCK_EXECUTED', 'event_count': len(old) + 1}
    return result, {'events': old + [event]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan', type=Path)
    ap.add_argument('--mock-approval', required=True, type=Path)
    ap.add_argument('--local-ledger', required=True, type=Path)
    args = ap.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf8'))
    approval = json.loads(args.mock_approval.read_text(encoding='utf8'))
    ledger = json.loads(args.local_ledger.read_text(encoding='utf8')) if args.local_ledger.exists() else {'events': []}
    try:
        outcome, next_ledger = execute_mock(plan, approval, ledger)
    except Denied as exc:
        print('DENIED:', exc)
        return 2
    if outcome['status'] == 'MOCK_EXECUTED':
        # Simple single-process synthetic ledger. No concurrent atomicity claim.
        args.local_ledger.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.mock-ledger-', dir=args.local_ledger.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf8') as f:
                json.dump(next_ledger, f, indent=2)
                f.write('\n')
            os.replace(temp, args.local_ledger)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print(json.dumps(outcome))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
