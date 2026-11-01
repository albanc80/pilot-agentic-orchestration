#!/usr/bin/env python3
"""OFFLINE mock-only oilfield-equipment delivery planner. NEVER calls live systems."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

MAX_INSIGHT_AGE_MINUTES = 30  # illustrative: must be validated by business owner
MAX_STOCK_AGE_MINUTES = 60    # illustrative: stale ERP snapshots fail closed
MIN_CONFIDENCE = 0.75        # illustrative: NOT an approved engineering threshold


def instant(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be a string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('timestamp must have an explicit timezone')
    return parsed.astimezone(timezone.utc)


def blocked(request_id, reason, fallback=None):
    result = {'status': 'BLOCKED', 'request_id': request_id, 'reason': reason, 'live_execution_allowed': False}
    if fallback:
        result['manufacturing_fallback'] = {'advisory_only': True, **fallback}
    return result


def plan(case, as_of):
    if not case.get('synthetic'):
        return blocked(case.get('demand', {}).get('request_id'), 'ONLY_SYNTHETIC_DATA_ALLOWED')
    ins = case['insight']
    dem = case['demand']
    req_id = dem['request_id']
    if not ins.get('asset_identity_verified') or not ins.get('unit_normalized'):
        return blocked(req_id, 'UNTRUSTED_IDENTITY_OR_UNITS')
    if float(ins.get('confidence', -1)) < MIN_CONFIDENCE:
        return blocked(req_id, 'LOW_CONFIDENCE_INSIGHT')
    age = as_of - instant(ins['observed_at'])
    if age < timedelta(0) or age > timedelta(minutes=MAX_INSIGHT_AGE_MINUTES):
        return blocked(req_id, 'STALE_OR_FUTURE_INSIGHT')
    if not isinstance(dem['quantity'], int) or dem['quantity'] <= 0:
        return blocked(req_id, 'INVALID_DEMAND_QUANTITY')
    need_by = instant(dem['need_by'])
    if need_by <= as_of:
        return blocked(req_id, 'DEMAND_DEADLINE_IN_PAST')
    eligible = []
    reasons = []
    for depot in case.get('depots', []):
        stock_age = as_of - instant(depot['stock_as_of'])
        if stock_age < timedelta(0) or stock_age > timedelta(minutes=MAX_STOCK_AGE_MINUTES):
            reasons.append(f"{depot['depot_id']}:STALE_INVENTORY")
            continue
        for stock in depot.get('inventory', []):
            if stock['sku'] != dem['sku']:
                continue
            if stock['quantity_available'] < dem['quantity'] or not stock.get('serviceable', False) or stock.get('maintenance_hold', True):
                reasons.append(f"{depot['depot_id']}:UNAVAILABLE_OR_UNSERVICEABLE")
                continue
            for route in depot.get('routes', []):
                if route['destination_region'] != dem['destination_region']:
                    continue
                if not route.get('mock_trade_clearance', False) or not route.get('mock_route_eligible', False):
                    reasons.append(f"{depot['depot_id']}:MOCK_TRADE_OR_ROUTE_NOT_CLEARED")
                    continue
                eta = as_of + timedelta(days=route['transit_days'])
                if eta > need_by:
                    reasons.append(f"{depot['depot_id']}:ARRIVAL_AFTER_REQUIRED_DATE")
                    continue
                if instant(stock['cert_valid_until']) < eta:
                    reasons.append(f"{depot['depot_id']}:CERTIFICATION_EXPIRES_BEFORE_DELIVERY")
                    continue
                eligible.append({'depot_id': depot['depot_id'], 'destination_region': dem['destination_region'], 'sku': dem['sku'], 'quantity': dem['quantity'], 'eta': eta.isoformat(), 'cost_usd': route['cost_usd']})
    if not eligible:
        fallback = case.get('manufacturing', {})
        return blocked(req_id, 'NO_POLICY_ELIGIBLE_ROUTE:' + ','.join(sorted(set(reasons))), fallback if fallback.get('fallback_possible') else None)
    eligible.sort(key=lambda c: (c['eta'], c['cost_usd'], c['depot_id']))
    choice = eligible[0]
    fingerprint = json.dumps({'request_id': req_id, 'choice': choice, 'observed_at': ins['observed_at']}, sort_keys=True)
    plan_id = 'MOCKPLAN-' + hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return {
        'status': 'AWAITING_HUMAN_MOCK_APPROVAL', 'mock_only': True,
        'live_execution_allowed': False, 'request_id': req_id, 'plan_id': plan_id,
        'selected_scenario': choice, 'eligible_scenario_count': len(eligible),
        'policy': {'max_insight_age_minutes': MAX_INSIGHT_AGE_MINUTES, 'min_confidence': MIN_CONFIDENCE, 'max_stock_age_minutes': MAX_STOCK_AGE_MINUTES},
        'provenance': {'insight_source': ins['source'], 'asset_id': ins['asset_id'], 'insight_observed_at': ins['observed_at']},
        'next_action': 'HUMAN_APPROVAL_OF_MOCK_EXECUTION_ONLY'
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case', type=Path)
    p.add_argument('--as-of', required=True, help='ISO8601 timezone-aware timestamp')
    p.add_argument('--output', type=Path)
    opts = p.parse_args()
    result = plan(json.loads(opts.case.read_text(encoding='utf8')), instant(opts.as_of))
    serialized = json.dumps(result, indent=2) + '\n'
    if opts.output:
        opts.output.write_text(serialized, encoding='utf8')
        print('Wrote mock-only plan:', opts.output)
    else:
        print(serialized)
    return 0 if result['status'] == 'AWAITING_HUMAN_MOCK_APPROVAL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
