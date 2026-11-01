# Verification record — 2026-10-31

## Locally observed (PASS)
- `python -m unittest discover -s tests -v`: **20 tests passed** on packaging container.
- Contract example consistency checker: **PASS**.
- Planner positive fixture yields a **MOCK-only** eligible scenario: Houston, TX → Brazil, SKU MWD-PULSER-100, synthetic ETA 2026-11-04 12:00 UTC, synthetic planning cost USD 3,500. These numbers are invented fixture values, NOT vendor/transport quotes.
- Policy negative cases include stale/low-confidence insights, incorrect asset identity, maintenance hold, expired cert, stale stock, uncleared route, missing/mismatched mock approval, idempotent repeated mock request, invalid contracts, and duplicate/missing agent-ID mappings.
- Rendered config route generator uses 15 unique IDs; both leads have cross-team `send` while all specialists have `send: []`. Leads are communication-only unsandboxed to avoid OpenClaw's sandbox session visibility clamp; specialist code workers are sandboxed.

## Not observed — still BLOCKED on live environment
- Installed OpenClaw version, real agent IDs, actual tool policy/schema, existing agent bindings and Windows paths: **NOT INSPECTED**.
- OpenClaw config dry-run, current Gateway health, Docker workspace behavior, communication restrictions and agent sandbox denial: **NOT RUN**.
- GitHub repo existence, protections, authorized human reviewer, required CI check and PR/merge blocks: **NOT CONFIGURED**.
- Production source systems, real telemetry/inventory data, supply chain/CMMS/MES/TMS adapter testing, compliance authority, shared deployment gate: **OUT OF SCOPE / NOT VERIFIED**.
- Gateway restart recovery, distributed race/idempotency under concurrency, real world inventory revalidation: **NOT TESTED**. The Python sample ledger is single-process only.

## Acceptance thresholds
Before declaring orchestration deployed: version-supported routing config; negative tool/session tests; independent QA/Security traceability; actual GitHub branch protection and PR; approved rollback tested; no unrestricted external action path. The pilot is COMPLETE only after deployed verification; code/test package alone is PARTIAL.
