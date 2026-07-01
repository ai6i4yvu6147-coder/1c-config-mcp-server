---
packet_version: 1
kind: protocol_dispute
from: <sub-module-id>
to: <head-module-id>
direction: sub_to_head
protocol_epoch: <N>
dispute_round: 1
summary: |
  Brief: what does not match Head proposal and what Sub proposes.
---

## Accepted without dispute

<What Sub accepts as-is — before discrepancy table.>

## Discrepancies

| ID | Local path | Head / snapshot | Summary | severity |
|----|------------|-----------------|----------|----------|
| D1 | docs/... | shared/... | ... | critical |

## Sub proposal

<What to merge into Head canon, or what Sub considers project-local.>

## Expected Head actions

- [ ] `protocol_merge` with verdict table by ID (D1, D2, …)

## Operator

Copy outbox → Head inbox (see `docs/group/OPERATOR-HANDOFF.md`).
