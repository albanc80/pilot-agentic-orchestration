#!/usr/bin/env python3
"""Minimal zero-dependency contract semantic gate. Not a substitute for GitHub rules."""
import json
import sys
from pathlib import Path


class ContractError(ValueError):
    pass


def require(doc, keys, name):
    for k in keys:
        if k not in doc or doc[k] in (None, '', []):
            raise ContractError(f'{name}: missing/empty {k}')


def validate(contract, task, evidence):
    require(contract, ['type', 'schema_version', 'project_id', 'contract_version', 'owner_role', 'engineering_owner_role', 'requirements', 'scope', 'exclusions', 'authorized_actions', 'prohibited_actions'], 'delivery contract')
    require(task, ['type', 'schema_version', 'project_id', 'contract_version', 'task_id', 'assigned_role', 'source_requirements', 'acceptance', 'status'], 'task packet')
    require(evidence, ['type', 'schema_version', 'project_id', 'contract_version', 'task_id', 'ci_status', 'local_unit_test_status', 'qa_reviewer', 'security_reviewer', 'status'], 'evidence packet')
    if [contract['type'], task['type'], evidence['type']] != ['DeliveryContract', 'TaskPacket', 'EvidencePacket']:
        raise ContractError('invalid artifact type')
    if len({contract['project_id'], task['project_id'], evidence['project_id']}) != 1:
        raise ContractError('project mismatch')
    if len({contract['contract_version'], task['contract_version'], evidence['contract_version']}) != 1:
        raise ContractError('stale or mismatched contract_version')
    if task['task_id'] != evidence['task_id']:
        raise ContractError('task/evidence mismatch')
    reqs = [item['id'] for item in contract['requirements']]
    if len(reqs) != len(set(reqs)):
        raise ContractError('duplicate requirement ID')
    if not set(task['source_requirements']).issubset(reqs):
        raise ContractError('task references unknown requirement')
    if 'LIVE_TRANSACTION' not in contract['prohibited_actions']:
        raise ContractError('pilot contract must explicitly deny LIVE_TRANSACTION')
    return True


def main(argv):
    if len(argv) != 3:
        print('Usage: python scripts/validate_contracts.py CONTRACT TASK EVIDENCE', file=sys.stderr)
        return 2
    data = [json.loads(Path(p).read_text(encoding='utf8')) for p in argv]
    try:
        validate(*data)
    except (KeyError, ValueError) as exc:
        print('BLOCKED:', exc)
        return 1
    print('PASS: Artifact consistency valid. This is NOT merge, security, human or deployment authorization.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
