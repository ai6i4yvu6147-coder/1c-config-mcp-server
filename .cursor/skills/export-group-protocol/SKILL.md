---
name: export-group-protocol
description: >-
  Head only: export protocol snapshot and protocol_offer packet to a Sub outbox.
  Use to start baseline sync or ripple after epoch bump.
disable-model-invocation: true
---

# Export group protocol

**Head only.**

## Steps

1. Confirm target `sub-id` in `group.manifest.yaml`.
2. Run:

```powershell
python scripts/protocol-snapshot.py --export --repo . --sub <sub-id>
```

3. Delegate **doc-librarian** to create `protocol_offer` packet in `docs/group/outbox/<sub-id>/` referencing snapshot dir.
4. Deliver:

```powershell
python scripts/sync-relay.py --deliver --repo .
```

## Do not

- Copy `templates/` to Sub
- Create `protocol-ref/` in Head
