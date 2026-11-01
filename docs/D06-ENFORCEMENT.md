# D06 — human approval enforcement (proven)

**Date:** 2026-11-01 · Reviewer: `ilbambinomx` (collaborator, write) · Owner: `albanc80`

## Configuration
- required approving reviews: 1
- enforce_admins: **true**
- required checks: `pilot-policy-tests`, `main-guard` (strict)
- linear history, no force-push, no deletions

## Observed on PR #10
```
reviewDecision: REVIEW_REQUIRED

$ gh pr merge --squash
X ... is not mergeable: the base branch policy prohibits the merge.

$ gh pr merge --squash --admin
GraphQL: At least 1 approving review is required by reviewers with write access.
         Required status check "main-guard" is expected.
```

**Conclusion:** no single account — including the owner administrator — can merge to `main` without an independent approval and green checks.
