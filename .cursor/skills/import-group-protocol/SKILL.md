---
name: import-group-protocol
description: >-
  Sub only: process protocol_offer from inbox — compare canon, ack or prepare
  dispute via doc-librarian and arbitrator.
disable-model-invocation: true
---

# Import group protocol

**Sub only.**

## Steps

1. List `docs/group/inbox/` for `protocol_offer` and snapshot subdirectory.
2. Invoke **doc-librarian** to compare offer vs local (`integration.md`, existing protocol docs).
3. If aligned: install via `python scripts/protocol-snapshot.py --install --repo .`; librarian sends `protocol_ack`.
4. If mismatches: invoke **group-sync-arbitrator** (gate) → dispute or local fix per verdict.
5. `sync-relay.py --deliver` if outbox changed.
6. Update `docs/group/integration.md` state fields.

## Do not

- Create duplicate `admin-hub` + `protocol-ref` without analysis
