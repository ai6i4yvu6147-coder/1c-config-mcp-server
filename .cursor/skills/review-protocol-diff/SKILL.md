---
name: review-protocol-diff
description: >-
  Sub only: gate protocol mismatches via group-sync-arbitrator before emitting
  dispute to Head.
disable-model-invocation: true
---

# Review protocol diff

**Sub only.**

## Steps

1. Ensure doc-librarian has comparison report (from `import-group-protocol`).
2. Invoke **group-sync-arbitrator** with mismatch list.
3. For each `project_local` → librarian fixes locally.
4. For each `escalate_to_head` → librarian creates `protocol_dispute` in outbox.
5. Check `dispute_round` in `integration.md` (max 3) — if exceeded, stop and note `defer_manual`.
6. `python scripts/sync-relay.py --deliver --repo .`

Template: `templates/protocol-dispute.example.md` (read from WI if not local).
