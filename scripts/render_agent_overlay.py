#!/usr/bin/env python3
"""Generate a REVIEW-ONLY OpenClaw config patch from 15 verified agent IDs.
Does not contact OpenClaw or modify any configuration.
"""
import argparse
import json
from pathlib import Path

FDU = ['fdu_engineer', 'domain_specialist', 'data_designer', 'fdu_architect', 'ai_specialist']
ENG = ['security_engineer', 'qa_engineer', 'integration_engineer', 'frontend_engineer', 'data_engineer', 'devsecops_engineer', 'backend_engineer', 'engineering_architect']
ROLES = ['fdu_outcome_lead', *FDU, 'pod_lead', *ENG]


def make_overlay(roles):
    if set(roles) != set(ROLES):
        raise ValueError('Role mapping must have exactly the 15 canonical role keys')
    ids = list(roles.values())
    if any(not isinstance(i, str) or not i.strip() or 'REPLACE_' in i or i.startswith('<') for i in ids):
        raise ValueError('Replace every placeholder with an actual OpenClaw agent ID')
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate agent IDs would violate routing isolation')
    if any(not all(c.isalnum() or c in '._-' for c in agent_id) for agent_id in ids):
        raise ValueError('Agent IDs contain unsupported characters; verify against actual agent registry')
    entries = {}
    for role in ROLES:
        aid = roles[role]
        target_roles = FDU if role == 'fdu_outcome_lead' else ENG if role == 'pod_lead' else []
        cross_team = [roles['pod_lead']] if role == 'fdu_outcome_lead' else [roles['fdu_outcome_lead']] if role == 'pod_lead' else []
        # Leads must be able to send to the OTHER lead. A sandboxed session's
        # default spawned-only session clamp can block that route even with
        # agentToAgent.send allowed. Leads run communication-only UNSANDBOXED
        # with local file/shell/browser/gateway tools denied; workers are sandboxed.
        worker_sandbox = {
            'mode': 'all', 'backend': 'docker', 'scope': 'session', 'workspaceAccess': 'none',
            'docker': {'network': 'none'}
        }
        lead_sandbox = {'mode': 'off'}
        e = {
            'sandbox': lead_sandbox if target_roles else worker_sandbox,
            'subagents': {
                'requireAgentId': True,
                'allowAgents': [roles[r] for r in target_roles],
                'maxConcurrent': 3 if target_roles else 1,
                'maxChildrenPerAgent': 3 if target_roles else 1,
                'maxSpawnDepth': 1,
                'runTimeoutSeconds': 900,
            },
            'tools': {
                'agentToAgent': {'send': cross_team},
                'elevated': {'enabled': False},
                'deny': (['gateway', 'nodes', 'cron', 'browser',
                          'exec', 'process', 'write', 'edit', 'apply_patch']
                         if target_roles else
                         ['gateway', 'nodes', 'cron', 'browser']),
            },
        }
        if target_roles:
            # Coordination only: no host shell, filesystem, browser or gateway tools.
            e['tools']['allow'] = ['agents_list', 'sessions_spawn', 'sessions_send', 'sessions_list', 'sessions_history', 'session_status']
            e['tools']['deny'] += ['read', 'write', 'edit', 'apply_patch', 'exec', 'process']
        # Specialist roles cannot initiate spawn or ordinary cross-agent sends.
        # Delegator leads need sessions_spawn and sessions_send available from inherited tool policy.
        if not target_roles:
            e['tools']['deny'].append('sessions_spawn')
            e['tools']['deny'].append('sessions_send')
        entries[aid] = e
    return {
        'tools': {
            'sessions': {'visibility': 'tree'},
            'agentToAgent': {'enabled': True, 'allow': ids},
        },
        'agents': {'entries': entries},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mapping', type=Path, help='local copy of config/agent-ids.template.json with actual IDs')
    ap.add_argument('--output', type=Path, default=Path('openclaw.review.patch.json5'))
    args = ap.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding='utf8'))
    patch = make_overlay(mapping)
    args.output.write_text(json.dumps(patch, indent=2, sort_keys=False) + '\n', encoding='utf8')
    print('Wrote review-only config overlay:', args.output)
    print('CAUTION: global sessions visibility and agentToAgent allow may affect other OpenClaw agents.')
    print('Next: inspect diff, dry-run against installed schema, request approval; DO NOT APPLY AUTOMATICALLY.')


if __name__ == '__main__':
    main()
