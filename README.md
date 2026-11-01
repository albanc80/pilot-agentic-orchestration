# OFDL-PILOT-001 — Oilfield Equipment Delivery Orchestrator

Mock-only pilot. No live ERP/CMMS/MES/TMS writes, no customer contact, no production release.

## Layout
- `contracts/` — TaskPacket / DeliveryContract / EvidencePacket JSON schemas + examples
- `docs/` — architecture, approval matrix, ADR-001, deployment runbook, backlog
- `pilot/` — deterministic planning + mock execution reference implementation
- `tests/` — pytest suite (pilot + negative cases)
- `config/` — role-policy matrix (canonical orchestration policy)
- `scripts/` — `validate_contracts.py`, `check_policy.py`, `ledger.py`

## Gates
- **Gate 0** — human approval of OpenClaw config changes (applied; see `../phase-a/CHANGE-RECORD.md`)
- **Gate A** — build authorization after FDU discovery + contract versioning
- **Gate B** — human merge approval after independent QA/Security verification

## Local commands
```bash
python3 scripts/validate_contracts.py
python3 -m pytest -q
python3 scripts/check_policy.py        # requires ~/.openclaw/openclaw.json
python3 scripts/ledger.py --summary    # gateway audit_events -> JSONL
```

## Status
Pilot complete (mock-only). T01–T18 pass; E2E demo verified; Gate B pending human sign-off. See `docs/CLOSEOUT.md` and `docs/VERIFICATION-RECORD.md`.
