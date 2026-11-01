# Approval / autonomy policy (deny-by-default)

## Development workflow

| Action | Autonomous | Enforcing control |
|---|---|---|
| Read synthetic pilot fixtures, design, document | Yes | Dedicated workspace, scoped context |
| Code and unit-test in disposable sandbox | Yes | Filesystem/process sandbox, tool ACL |
| Open draft PR after approved GitHub connector is installed | Conditional | Fine-grained repo identity, no `main` push |
| Change approved delivery contract scope | No | Human product owner for material changes; versioned ADR |
| Change agent identities, global Gateway configuration, runtime tool permissions | No | Human approval, backup, diff, audit, rollback |
| Merge to `main` | No | Protected branch / human reviewer + required CI |
| Release to shared sandbox/staging | Human approval if external/shared | GitHub environment rules/enterprise deploy gate |
| Release to production | No | Human, independent security and QA, change/release authorization |

## Pilot logistics workflow

| Action | Pilot policy | Production implication |
|---|---|---|
| Consume synthetic telemetry / stock / CMMS / MES | Read-only simulation | Later service-account scoped reads, owner/quality verification |
| Rank eligible shipping options | Autonomous in test | Subject to real compliance and inventory validation |
| Create delivery plan / recommendation | Autonomous in test | Non-binding recommendation only |
| Mock reservation and dispatch | Human-approved **mock only** | Cannot be used as authorization for live writes |
| Reserve physical inventory / create transport order / authorize repair / production order / send customer commitment | **DENIED** | Needs separate business approvals and connector safeguards |
| Export controlled items / sanctions / customs classification decisions | **DENIED** | Human compliance review and legally validated policy |
| Change well-control / safety-critical equipment disposition | **DENIED** | Validated engineering controls and accountable human authority |

## Enforcing independence

- Security reviewer cannot approve a risk they introduced as sole implementer.
- QA cannot be sole author and sole acceptor of the same acceptance evidence.
- GitHub PR approvals require a real authorized human account; agent labels/comments/JSON approval objects are *advisory records*, not merge permissions.
- A release gate must sit **outside** agent-controlled repo state. GitHub private-repo environment reviewer rules have plan limitations: verify actual plan and enforcement; use an enterprise CI/CD approval system if the feature is unavailable.
- An operational action gate must sit behind a separately administered API authorization service, not inside agent prompts or a source file the agent can edit.
- Prevent a delegated agent from escalating through shell, GitHub credentials, browser, plug-in tools or Gateway functions.
- Stop or escalate immediately if data cannot be verified, a required system is down, compliance isn't cleared, or a customer commitment exceeds authorized parameters.
