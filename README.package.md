# FDU + Engineering — OpenClaw Orchestration & Oilfield Equipment Logistics Pilot

**Status:** DEPLOYMENT-READY ARTIFACTS / NOT INSTALLED. Prepared 2026-10-31. No running OpenClaw Gateway, GitHub repo, real ERP, CMMS, MES, TMS, or external systems were accessed or changed.

## Decisions
- Reuse all 15 existing OpenClaw agents. FDU Outcome Lead is the single human interface and accountable product owner; Engineering Pod Lead owns execution.
- GitHub is authoritative for contracts, issues, PRs, code, tests, and traceable evidence. Use a **private repo**. GitHub's protected branch / human reviewer, not agent-written attestations, controls merge.
- The two leads are **communication-only without host shell/filesystem/browser tools** so cross-lead messaging works under the default sandbox session clamp; specialist engineers may write/test in isolated disposable sandboxes. **No unsupervised merges, real deployments or operational transactions.**
- The runtime pilot uses **one bounded planning agent** plus deterministic policy, eligibility, approval and execution logic; do not turn the 15 delivery agents into a 15-agent operational swarm.
- Operate on synthetic data and mock systems only; the pilot may simulate reservations/transfers/dispatch with an explicit mock-only approval. Real transactions remain prohibited pending separate authorization and controls.

## Read in order

**Important routing correction:** OpenClaw’s sandbox session-tools clamp can block cross-lead `sessions_send` from a sandboxed session. Use the package’s review-only policy with the two leads restricted, non-executing and unsandboxed, and all 13 specialists in isolated sandboxes. Verify both directions and specialist denies live before claiming orchestration works.
1. `OPENCLAW_FDU_ENGINEERING_MVP_HANDOFF.md`: **authoritative single-file handoff to existing OpenClaw Outcome Lead**, including setup, permissions, GitHub workflow, MVP build and acceptance tests.
2. `docs/deployment-runbook.md`: read-only inventory, approvals, exact sequence, rollback.
3. `docs/architecture.md`: delivery-agent interaction and pilot runtime architecture.
4. `docs/approval-matrix.md`: enforced decision rights and stages.
5. `config/openclaw-overlay.example.json5`: **illustrative overlay, not a complete config; do not paste directly** until actual IDs are mapped, version/schema checked, security assessed and user approves.
6. `OPENCLAW_SETUP_PROMPT.md`: paste into the existing OpenClaw main/Outcome Lead after review.
7. `contracts/examples/`: versioned contract and task/evidence specimens.
8. `pilot/`: offline deterministic proof of the operations workflow.

## Run the offline validation

```powershell
# Run from this extracted package root; does not need OpenClaw or network.
python -m unittest discover -s tests -v
python scripts/validate_contracts.py contracts/examples/delivery-contract.json contracts/examples/task-packet.json contracts/examples/evidence-packet.json
python pilot/plan_delivery.py pilot/fixtures/sample-worldwide-request.json --as-of 2026-10-31T12:00:00Z
```

## Design assumptions pending field validation
- First use case: one tool family, one demand signal, one cross-border customer, two mock depots and one manufacturing fallback.
- 30-minute insight freshness threshold, 0.75 confidence threshold, and arrival-before-required-date are **illustrative pilot policy**, not production engineering limits.
- No optimization of real fleet dispatch, purchases, customs clearance, maintenance safety certification, transport reservations or delivery commitments in this MVP.
- Real-world adapters require system ownership, authoritative APIs, data contracts, permissions, security and human-approved release.

## Critical boundaries
1. An LLM may explain or suggest a plan, but cannot override the policy engine or submit a real order/shipment.
2. Operational telemetry is untrusted input; refuse stale, low-confidence, mismatched units, or uncertain asset identity.
3. Serviceability, certification, export/trade restrictions, sanctions, inventory reservations, maintenance, transport and customer commitments require authoritative validation. On ambiguity, block and escalate.
4. An agent-authored `approval.json` is not authorization. GitHub authenticated reviewers / environment protection or an independently controlled enterprise approval service must enforce live gates.
5. Use `openclaw config validate --json`, `openclaw security audit --deep`, and an end-to-end negative test before declaring deployment complete.

## Sources
- OpenClaw docs: https://docs.openclaw.ai/gateway/config-tools/sessions-and-subagents
- OpenClaw docs: https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent
- OpenClaw docs: https://docs.openclaw.ai/gateway/config-agents/sandbox
- OpenClaw docs: https://docs.openclaw.ai/cli/config
- OpenClaw docs: https://docs.openclaw.ai/gateway/config-tools/github-identity
- GitHub branch protections: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub environments: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
