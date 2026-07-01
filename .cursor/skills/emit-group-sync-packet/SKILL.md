---
name: emit-group-sync-packet
description: >-
  Create a sync packet in docs/group/outbox after a critical group-affecting
  documentation or protocol change in Head or Sub. Use when contract, CLI,
  mapping, moduleId, or shared protocol changes and the other side must update specs.
---

# Emit group sync packet

## When to use

After a **critical** change (see `docs/canons/group-sync.md`):

- Head: changed `docs/group/shared/` affecting a Sub
- Sub: change affects the **common path** — notify Head only (never other Subs)

Do **not** emit for local-only implementation details.

## Steps

1. Read `templates/sync-packet.example.md` (or canon `group-sync.md`) for format.
2. Create file with YAML frontmatter + body:
   - `kind: sync_delta`
   - `from`, `to`, `direction` (`head_to_sub` | `sub_to_head`)
   - `severity: critical`
   - `affects:` list of docs to update at recipient
   - `summary:` 3–10 sentences
3. **Path:**
   - **Head → Sub:** `docs/group/outbox/<sub-id>/<timestamp>-<from-id>.md`
   - **Sub → Head:** `docs/group/outbox/<timestamp>-<from-id>.md`
4. Timestamp: `YYYYMMDDTHHMMSS` (UTC or local, be consistent).
5. Tell user to run relay:

```powershell
python scripts/sync-relay.py --deliver --repo .
```

Optional: `--dry-run` first.

## Do not

- Commit the packet to git (inbox/outbox are gitignored)
- Copy entire `shared/` into the packet — only delta and instructions
- Send Sub → Sub
