---
packet_version: 1
kind: sync_delta
from: <sender-module-id>
to: <recipient-module-id>
direction: head_to_sub
severity: critical
protocol_epoch: <N>
protocol_ref: docs/group/shared/<spec>.md
affects:
  - docs/architecture.md
  - docs/group/integration.md
summary: |
  Brief summary for recipient agent (3–10 sentences).
---

## Details

<Decision context.>

## Expected recipient actions

- [ ] Update affected specs in `affects`
- [ ] Update `last_sync_from_head` / `last_sync_to_head`
- [ ] Delete this file after processing

## Operator

Copy outbox → Sub inbox (see `docs/group/OPERATOR-HANDOFF.md`).
