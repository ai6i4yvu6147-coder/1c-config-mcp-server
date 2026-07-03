---
name: sync
description: >-
  Group sync via GROUP-HUB.md at Head root — proposals, dispute, merge, ack for
  Head or Sub. Use for /sync <sub-id> <topic> or when todo has Hub pending.
---

# Sync — negotiation via GROUP-HUB.md

**Head or Sub.** State lives in `GROUP-HUB.md` at the Head repo root; the hub carries thread status and the registry, while contract bodies live in git and are referenced by path + commit.

Hub path:

- **Head:** `GROUP-HUB.md` (repo root)
- **Sub:** `<head.path>/GROUP-HUB.md` from `group.manifest.yaml` — your `sub_id` sections only

---

## Determine mode

| Situation | Role | Action |
|-----------|------|--------|
| User describes a new contract | Head | New thread `sync_delta` or `protocol_offer` |
| Thread `awaiting_sub` for this sub | Sub | Compare refs; ack or dispute in the thread |
| Thread `awaiting_head` with a dispute | Head | Verdict in the thread; update `shared/` if needed |
| Thread ready for ack | Sub | Set `protocol_ack`; install `protocol-ref/` |
| Epoch bump in `shared/` | Head | `protocol_ripple` thread per lagging sub |

Process one thread at a time, oldest `awaiting_*` first.

---

## Head — outgoing proposal

1. Prepare the contract in `docs/group/shared/` and commit; the hub links it by path + commit.
2. Pre-flight: transport credentials stay out of agent context; normative mapping lives in `shared/`.
3. Append a thread to `GROUP-HUB.md` → `Active threads`:

```markdown
### THR-<NNN> — sync_delta — <sub-id>
- **status:** awaiting_sub
- **severity:** critical | info
- **affects:** paths
- **head_proposal:** summary + `docs/group/shared/...` @ commit
- **dispute_round:** 0/3
```

4. Set the registry row → `negotiating`.
5. Add a line to this repo `docs/todo.md` → `## Hub pending`.
6. Optional review snapshot: `protocol-snapshot.py --attach-review` — referenced by path in the thread.

---

## Sub — response (awaiting_sub)

1. Read the thread and the referenced files from Head `shared/` or local `protocol-ref/epoch<N>/`. A snapshot path in the thread resolves under `<head.path>/docs/group/exports/<sub-id>/`.
2. **Aligned:** install the snapshot if the thread points to one (`protocol-snapshot.py --install --from <that path>`); update `integration.md`; set the thread → `protocol_ack` / `closed`; registry → `stable`.
3. **Gaps:** fill `sub_response` with accepted items + D1, D2…; `status` → `awaiting_head`; increment `dispute_round` (max 3 → `defer_manual` in summary).
4. Update Sub `docs/todo.md` Hub pending → `awaiting_head` where applicable.
5. Doc file edits go through `doc-librarian` with explicit scope.

---

## Head — merge (awaiting_head)

1. Read the `sub_response` disputes.
2. Update `docs/group/shared/` per agreement.
3. Fill `verdict`; set `status` → `awaiting_sub` (for the Sub to ack) or `closed` if resolved.
4. On ack: update `docs/group/README.md` sub table; archive the thread summary to `docs/group/archive/<sub-id>/`.
5. Remove the Hub pending line from both repos' `todo.md` when `closed`.

---

## Ripple (epoch bump)

1. Bump `protocol_epoch` in the hub frontmatter.
2. For each Sub off the epoch: a new `protocol_ripple` thread + snapshot refs (as in `sync-base`).
3. Registry rows → `stale` until ack.

---

## Delegate doc edits

Once a step is decided, invoke `maintain-docs` → `doc-librarian` with task (one sentence), scope (explicit file list), and StateFields for `integration.md` / group README. The librarian edits files; timing stays here.

The hub holds pointers and status; contract bodies stay in git, and each sub edits only its own threads.

## Tools

```powershell
python scripts/sync-status.py --repo .
python scripts/protocol-snapshot.py --install --repo . --from <head.path>/docs/group/exports/<sub-id>/<snapshot-dir>
python scripts/protocol-snapshot.py --status --repo .
```
