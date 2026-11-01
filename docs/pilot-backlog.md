# Pilot backlog — load these items into GitHub Issues/Project

| Issue | Owner | Depends on | Acceptance / evidence |
|---|---|---|---|
| FDU-01 Outcome hypothesis + customer journey | Outcome Lead + Domain Specialist | None | Measurable baseline plan, exceptions mapped |
| FDU-02 Canonical events / ontology | Data Designer + Domain Specialist | FDU-01 | Asset ID, SKU, site, time, unit, provenance, freshness and quality contracts |
| FDU-03 MVP architecture + risk | FDU Architect + AI Specialist + Engineering Architect | FDU-01/02 | ADR-001: deterministic execution, AI constrained to planner |
| FDU-04 Design readiness review | Outcome Lead + Pod Lead + Security | FDU-02/03 | Human-authorized v1 DeliveryContract; no unscoped live access |
| ENG-01 Mock telemetry / ERP / CMMS / MES / TMS adapters | Integration Engineer + Data Engineer | FDU-04 | Synthetic-only, no outbound network, signed fixtures |
| ENG-02 Eligibility and scenario service | Backend Engineer + Data Engineer | ENG-01 | Quality, stock, safety, route, trade checks; negative tests |
| ENG-03 Bounded planning orchestration | AI Specialist + Backend Engineer | ENG-02 | Structured, source-grounded scenarios; hallucination invalidates plan |
| ENG-04 Planner UI with evidence and approvals | Frontend Engineer | ENG-02/03 | Preview, blocked reasons, no hidden auto-dispatch |
| ENG-05 Mock execution controller and durable outbox | Backend Engineer + Integration Engineer | ENG-02 | Independent approval fixture for simulation; idempotency; deny live connector |
| ENG-06 CI + Sandbox + audit | DevSecOps Engineer + Security Engineer | ENG-01/05 | Protected PR, no direct push, isolated sandbox, evidence logs |
| ENG-07 Independent verification | QA Engineer + Security Engineer | ENG-03/06 | Positive/negative scenario matrix, threat review, QA non-self-review |
| FDU-05 Outcome acceptance | Outcome Lead + Domain Specialist | ENG-07 | Compare results with baseline, sign-off, residual risks, backlog decisions |

The planning agent is a runtime component implemented by Engineering, **not** a new OpenClaw team member by default.
