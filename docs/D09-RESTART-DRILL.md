# D09 — restart recovery drill (owner-run)

The gateway restart must be performed by the human owner.

```bash
cd ~/.openclaw/workspace/fdu/pilot-repo
bash scripts/d09_pre.sh          # 1. snapshot: git head, config hash, pid, outbox count
systemctl --user restart openclaw-gateway   # 2. the actual restart
sleep 20
bash scripts/d09_post.sh         # 3. verify: new pid, identical config/head, outbox unchanged
```

Pass criteria: `pass: true` — gateway came back on a new pid, config hash unchanged, git head unchanged, outbox count identical (no duplicated mock side effects).

Then confirm the agent layer manually: ask the assistant to run the lead→specialist probe again; expected result is a child reply, not a policy error.
