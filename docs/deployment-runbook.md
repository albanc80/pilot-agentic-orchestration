# Deployment runbook — exact operator sequence (Windows PowerShell)

**MUST NOT execute changes until explicit review/authorization.** Steps use the OpenClaw already running on your existing Windows machine; never install a duplicate service or set/unset `HOME`, `OPENCLAW_HOME`, `OPENCLAW_STATE_DIR` or `OPENCLAW_CONFIG_PATH` without first checking their currently effective values. Prior installations used custom paths. Exact workspace and agent IDs are unknown until inventory.

## Phase 0 — read-only inventory; safe to execute now

Open PowerShell **as your usual OpenClaw OS account**, not a different administrator or service account. Keep captures OUTSIDE the repo; they may contain account or path details. Run from the extracted package root:

```powershell
$auditDir = Join-Path $env:LOCALAPPDATA ("OpenClaw-Pilot-Inventory-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $auditDir | Out-Null
openclaw --version | Tee-Object (Join-Path $auditDir 'version.txt')
openclaw gateway status | Tee-Object (Join-Path $auditDir 'gateway-status.txt')
openclaw config file --json | Tee-Object (Join-Path $auditDir 'config-path.json')
openclaw agents list --json --bindings | Tee-Object (Join-Path $auditDir 'agents.json')
openclaw agents list --tree | Tee-Object (Join-Path $auditDir 'agent-tree.txt')
openclaw config validate --json | Tee-Object (Join-Path $auditDir 'config-validation.json')
openclaw doctor | Tee-Object (Join-Path $auditDir 'doctor.txt')
openclaw security audit --deep | Tee-Object (Join-Path $auditDir 'security-audit.txt')
docker version | Tee-Object (Join-Path $auditDir 'docker-version.txt')
gh auth status | Tee-Object (Join-Path $auditDir 'gh-status.txt')
Write-Host "Local-only inventory: $auditDir. Redact before sharing."
```

If `docker version` fails or the installed OpenClaw CLI does not recognize a command, **STOP that branch** and record the deviation. The packaging tests do not prove your Gateway supports the full overlay. Do not use `openclaw doctor --fix` by default.

## Phase 1 — map real agent IDs, render candidate patch (no writes to OpenClaw)

1. Read `agents.json`; map the 15 existing agent IDs into a local copy of `config/agent-ids.template.json`. Do not add agents or rename existing IDs.
2. Generate a review-only patch with real IDs:

```powershell
Copy-Item config/agent-ids.template.json .\config\agent-ids.local.json
# Edit config/agent-ids.local.json to match the actual agent IDs (never commit this local inventory unreviewed).
python scripts/render_agent_overlay.py config/agent-ids.local.json --output config/openclaw.review.patch.json5
openclaw config schema --json > (Join-Path $auditDir 'installed-schema.json')
openclaw config patch --file config/openclaw.review.patch.json5 --dry-run --json
```

3. Inspect the proposed **global** `tools.sessions.visibility` and `tools.agentToAgent.allow` impact. `allow` includes the fifteen IDs, but could deny collaboration for other existing agents. If unrelated agents rely on cross-agent sessions, redesign as a dedicated trusted Gateway or adjust policies only with approved impact. **No wildcard / omitted/empty global allowlist**: such values can reopen broad access.
4. Validate Docker sandbox backend with isolated **worker** sessions, network `none` and no host-workspace write access. Both coordinators are deliberately UNSANDBOXED communication-only (deny filesystem/shell/browser/Gateway tools) because default sandbox session clamps block lead-to-lead messages. Check all effective plugin tools for host execution/credential escapes. Inspect effective tool and sandbox policies with:

```powershell
openclaw sandbox explain --agent ACTUAL_FDU_OUTCOME_LEAD_ID
openclaw sandbox explain --agent ACTUAL_ENGINEERING_POD_LEAD_ID
```

5. Review actual tool inheritance, ability to spawn, cross-agent sends, GitHub transport, and channel bindings. `tools.github` managed credentials are excluded from sandbox by default; do not turn on `allowInSandbox` without security approval. Worktrees/PR publication need a controlled Gateway-brokered path or a human-run GitHub publishing step.

## Gate 1 — explicit approval for OpenClaw changes

Present: inventory, existing config baseline, redacted review-only patch and diff, compatibility validation, impact on unrelated agents, sandbox feasibility, GitHub permission model, exact rollback, expected downtime. **Await approval.** Agent instructions are not approval.

## Phase 2 — apply approved patch (operator only)

After Gate 1 approval, resolve active config file path and create a protected backup **outside GitHub**:

```powershell
$configPath = (openclaw config file --json | ConvertFrom-Json).path
$backupDir = Join-Path $env:LOCALAPPDATA ("OpenClaw-ProtectedBackup-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item -LiteralPath $configPath -Destination (Join-Path $backupDir 'openclaw.before-pilot.json')
# Restrict the directory ACL to the owner; backup may contain secrets. Store path privately.
openclaw config patch --file config/openclaw.review.patch.json5 --dry-run --json
# Only after approving the exact diff and successful dry-run:
openclaw config patch --file config/openclaw.review.patch.json5
openclaw config validate --json
openclaw security audit --deep
openclaw gateway status
```

Follow the CLI's own restart instruction; **do not restart/reinstall the gateway service gratuitously**. Older OpenClaw versions may automatically restart on patch. The config patch recursively merges objects and replaces arrays: inspect every existing per-agent `tools.deny`, `agentToAgent.send` and `subagents.allowAgents` entry for side effects. The generated overlay does not overwrite agent identities or existing workspace paths.

## Phase 3 — GitHub private repository and enforcement (separate authorization)

Choose `OWNER/REPO` (not provided yet). Use an existing properly secured private repo if available; otherwise, **only after explicit approval to create one**:

```powershell
# Run from extracted package root; verify no secrets, backups, .local files, logs or live config are staged.
git init
git switch -c main
git add .
git status --short
git commit -m "Bootstrap governed FDU/Engineering equipment-delivery pilot"
gh repo create OWNER/oilfield-equipment-orchestrator-pilot --private --source . --remote origin --push
```

Before first commit: populate `.gitignore`, review `git status`, then use `gh secret scan` or equivalent secret scanning where supported. If not supported, inspect with approved scanner. A repo-creation command is NOT to be executed by an autonomous agent without authorization.

In **GitHub repository Settings → Rules / Rulesets or Branches**, protect `main`:
- Require PR; block direct force push and deletion; no bypass for bot/agent identity.
- Require passing `pilot-policy-tests`; require conversation resolution; restrict merge to human maintainers.
- Require at least one independent human review (two for security-sensitive changes), dismiss stale approvals on new commits and require Code Owner review where supported.
- Replace the placeholders in `.github/CODEOWNERS.template` and install as `.github/CODEOWNERS` on the protected base branch; require an actual human GitHub owner (not an agent or a repo bot).
- Keep `GITHUB_TOKEN` `contents: read` by default; issue narrowly scoped short-lived GitHub publication credentials through an approved broker. Agents can propose draft PRs but cannot merge.
- For shared environment deployment, use a trusted independent approval gate. **Verify private-repo environment protection entitlement**; GitHub's reviewer rules vary by plan and visibility. Do not treat an unavailable plan feature as enforced.

**No live ERP/CMMS/MES/TMS credentials or customer data in the pilot GitHub repository.**

## Phase 4 — functional and negative tests

```powershell
python -m unittest discover -s tests -v
python scripts/validate_contracts.py contracts/examples/delivery-contract.json contracts/examples/task-packet.json contracts/examples/evidence-packet.json
python pilot/plan_delivery.py pilot/fixtures/sample-worldwide-request.json --as-of 2026-10-31T12:00:00Z --output local-plan.json
```

The generated `local-plan.json` is an example proposal requiring approval. Mock dispatch can be tested with a **manually created, synthetic-only fixture** of this form (not real authorization):

```json
{"authorization":"HUMAN_APPROVED_MOCK_ONLY","scope":"MOCK_EXECUTE","approved_by":"human-test-operator","request_id":"DEMAND-BR-0001","plan_id":"COPY_FROM_GENERATED_PLAN"}
```

Then `python pilot/mock_execute.py local-plan.json --mock-approval local-mock-approval.json --local-ledger local-ledger.json`; run twice to prove one mocked event. Do **not** use this fixture to authorize any external action or claim a real approval integration.

In a disposable OpenClaw session, run integration tests and capture actual evidence of:

1. Outcome Lead delegates to exactly the 5 FDU targets; Engineering Pod Lead to exactly the 8 Engineering targets. Check 3 simultaneous child limit and bounded retries.
2. Outcome Lead ↔ Pod Lead allowed, specialist ordinary cross-agent send denied; conversation/history leakage denied beyond allowed tree.
3. FDU DeliveryContract v1 → Pod Lead task packets → pull requests → QA/Security evidence → FDU acceptance; contract change v2 invalidates stale task packets.
4. Agent attempts to alter Gateway config, access secrets, bypass sandbox, create agent or push `main` are denied.
5. Unapproved PR cannot merge; failed test/security check blocks; shared deployment approval is independently enforced.
6. Operational mock planner denies stale, low confidence, hold, invalid cert, uncleared trade; repeated approved **mock** execute is idempotent.
7. Kill a task and restart Gateway only in approved window; recover from GitHub issues/contracts without duplicate external side effects.

Record Gateway logs, test screenshots/results, GitHub rule state and issue/PR references in an EvidencePacket. Local unit tests do not substitute for any of these integration proofs.

## Gate 2 — progression decision

Success criteria: one human-facing Outcome Lead, bounded two-lead interaction, restricted 15-role registry, no unapproved communication or tool escalation, versioned contracts, immutable CI/test evidence, human-protected merge, separate operational action control, mock-only execution, protected existing Gateway, proven rollback. If any fail: `PARTIAL`/`BLOCKED`; do not widen privileges to force success.

## Rollback

1. Stop the pilot work sessions and revoke pilot-specific GitHub permissions / ephemeral tokens. Leave unrelated jobs running where possible.
2. Record any in-flight PR/branch and mock-ledger state. Cancel/disable pilot-only GitHub workflows or permissions as necessary.
3. Restore the **original** configuration through your approved Gateway-config recovery procedure using the protected backup; do not blindly overwrite while Gateway owns the state. Confirm config hash/current writing owner first. Use Gateway shutdown/start only if required and explicitly approved.
4. Rerun `openclaw config validate --json`, `openclaw security audit --deep`, `openclaw agents list --bindings` and `openclaw gateway status`.
5. Confirm unrelated agent routes, credentials and scheduled tasks are unchanged. Preserve incident evidence without exposing secrets.

## Information needed before exact production installation

- Actual 15 OpenClaw agent IDs, installed version, tool policy and Gateway path.
- GitHub organization/user and repository slug; GitHub plan/ruleset ability; human reviewers.
- Whether Docker Desktop/approved container runtime is present and compatible.
- Authorization for approved GitHub read/write PR publication, and the operating connector owners.
- Real ERP/CMMS/MES/TMS vendors and source systems **for later stages only**.
