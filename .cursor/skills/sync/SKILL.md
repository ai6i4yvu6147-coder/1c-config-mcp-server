---
name: sync
description: >-
  Group sync for Head and Sub: proposals, inbox processing, dispute, merge,
  ack. Use for /sync <sub-id> <topic> or when operator says inbox is ready.
---

# Sync — negotiation and inbox

**Head or Sub.** Invoke: `/sync <sub-id> <topic>` or "process inbox".

Operator copies outbox → neighbor repo inbox; paths — `docs/group/OPERATOR-HANDOFF.md`.

---

## Determine mode

| Situation | Role | Action |
|-----------|------|--------|
| User describes new contract / plans | Head | Outgoing proposal (`sync_delta`) |
| Inbox has packet from Head | Sub | Dispute or ack |
| Inbox has `protocol_dispute` | Head | Merge |
| Inbox has `protocol_ack` | Head | Close cycle |

Read frontmatter `kind` in inbox. Process packets one at a time, oldest first.

---

## Head — outgoing proposal

1. Prepare or update documents (contracts — in `docs/group/shared/`).
2. Pre-flight for contract:
   - transport credentials not exposed to agent;
   - context tools read only local stores;
   - mapping in `shared/` if normative.
3. Create `sync_delta` in `docs/group/outbox/<sub-id>/<ts>-<head-id>.md` (template: `docs/group/templates/sync-packet.example.md` or `templates/sync-packet.example.md`).
4. Copy files for review into `review-snapshot-<ts>/`:

```powershell
python scripts/protocol-snapshot.py --attach-review --repo . --sub <sub-id> --files docs/group/shared/registry-mapping-foo.md ...
```

5. List outbox files for operator.

---

## Sub — inbox (offer / merge / sync_delta)

1. Read `docs/group/inbox/` — packet and `review-snapshot-*` / `protocol-snapshot-*` if present.
2. Compare with `docs/group/protocol-ref/epoch<N>/`, `integration.md`, local specs.
3. **After merge / aligned offer:**
   - install files in `protocol-ref/` (`protocol-snapshot.py --install` for snapshot);
   - update `integration.md` → `stable`, `dispute_round`, `open_disputes`;
   - `protocol_ack` in outbox.
4. **On discrepancies:**
   - `protocol_dispute` per template — first "Accepted without dispute", then D1, D2, …;
   - `integration.md` → `negotiating`, increment `dispute_round` (max 3 → `defer_manual` in summary).
5. Delete processed packet from inbox.
6. List outbox files for operator.

---

## Head — inbox (dispute)

1. Read dispute; update `docs/group/shared/` per agreement.
2. `protocol_merge` in `outbox/<sub-id>/` — verdict table by same IDs (D1, D2, …).
3. Optional: archive in `docs/group/archive/<sub-id>/<date>-<topic>.md` (template `negotiation-archive.example.md`).
4. Delete dispute from inbox.
5. List outbox for operator.

---

## Head — inbox (ack)

1. Update `docs/group/README.md` (`last_ack`, state).
2. Append **Merge record** to mapping doc if needed.
3. Delete ack from inbox.

---

## Packet naming

- Head → Sub: `docs/group/outbox/<sub-id>/<YYYYMMDDTHHMMSS>-<from-id>.md`
- Sub → Head: `docs/group/outbox/<YYYYMMDDTHHMMSS>-<from-id>.md`
