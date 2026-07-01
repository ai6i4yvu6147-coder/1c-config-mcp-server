---
name: run-protocol-reconciliation
description: >-
  Run one protocol reconciliation cycle (offer/dispute/merge/ack) for current
  repo until stable or defer_manual. Head or Sub.
disable-model-invocation: true
---

# Run protocol reconciliation

## Head

1. Pick target Sub (or continue current).
2. `export-group-protocol` for that Sub.
3. Wait for relay + Sub processing (user runs import in Sub repo).
4. Process inbox disputes with `arbitrate-protocol-dispute`.
5. On stable for Sub — ripple to others if epoch bumped (`export-group-protocol`).

## Sub

1. `import-group-protocol` on inbox offer.
2. If dispute path — `review-protocol-diff` after librarian comparison.

## Stop conditions

- `protocol_sync_state: stable` for current epoch
- `dispute_round >= 3` → `defer_manual`
- User interrupt

Report state via `python scripts/sync-status.py --repo .`
