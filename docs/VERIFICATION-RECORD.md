# Verification record — OFDL-PILOT-001

**Date:** 2026-11-01 · **Repo:** https://github.com/albanc80/pilot-agentic-orchestration (public)
**Disposition:** mock-only pilot; no live systems contacted; no credentials used.

## T01–T18 — functional negatives
`tests/test_t01_t18.py` — **18/18 pass** (stdlib unittest; also collected by pytest in CI).

```
Ran 18 tests in 0.874s
OK
```

Covered: eligible plan (T01), stale insight (T02), low confidence (T03), unknown asset (T04), stale/insufficient stock (T05), maintenance hold (T06), cert expiry vs ETA (T07), trade/route unclear (T08), ETA after need-by with alternative route (T09), manufacturing advisory fallback (T10), approval requirement incl. self-authored rejection (T11), duplicate suppression (T12), 8-way concurrent duplicate → one event (T13), prompt/URL injection (T14), unknown contract version (T15), connector unavailable fail-closed (T16), dashboard provenance/restrictions/human authority (T17), audit traceability by correlation ID (T18).

## End-to-end demonstration (live HTTP, mock only)
```
PLAN: ELIGIBLE D1 2026-11-05T19:25:45Z
EXEC1: created=True
EXEC2: created=False            # idempotent
FORGED: status=DENIED           # invalid approval
DASHBOARD_MOCK_ONLY: True  PROVENANCE: True
AUDIT: approval_issued, mock_executed, mock_duplicate_suppressed, execution_denied
```

## Gate evidence
- Gate 0: config revisions 62–65 accepted; backups present; policy matrix check passes 15/15 roles.
- Gate A: contract version 1.0 fixed; ADR-001 in `docs/`.
- Gate B: **approved 2026-11-01** by Beto (gateway owner), with residual risks accepted.

## Residual risks
1. GitHub admin bypass is enabled (solo owner cannot self-approve). Real enforcement needs GitHub Pro or a second human reviewer (D06).
2. D09 restart-recovery is untested (needs an owner-controlled restart). D07 and D10 are now proven.
3. Sandbox image is locally built and unpinned by digest.
4. Worktrees share one git remote via a single account; branch discipline is procedural.
5. No real connectors, by design.
