---
name: process-group-inbox
description: >-
  Process pending sync packets in docs/group/inbox. Routes by kind to
  doc-librarian or group-sync-arbitrator. Use at session start or after relay.
---

# Process group inbox

1. List `docs/group/inbox/` (Head: also `docs/group/inbox/<sub-id>/`).
2. If empty — stop.
3. For each packet (oldest first), read **only** `kind` in frontmatter (do not load full packet body in parent chat):
   - `protocol_dispute` → invoke **group-sync-arbitrator** (Head), then **doc-librarian** for merge
   - `protocol_offer`, `protocol_merge`, `protocol_ack`, `protocol_ripple`, `sync_delta` → **doc-librarian**
   - missing `kind` → **doc-librarian** (legacy `sync_delta` rules)
4. Report summary; ensure packets deleted from inbox after processing.

See `docs/canons/group-sync.md` for packet kinds.

Relay deliver:

```powershell
python scripts/sync-relay.py --deliver --repo .
```
