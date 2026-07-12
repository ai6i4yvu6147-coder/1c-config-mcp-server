---
name: sync
description: >-
  Group sync via GROUP-HUB.md at Head root — proposals, dispute, merge, ack for
  Head or Sub. Use for /sync <sub-id> <topic> or when todo has Hub pending.
---

# Sync — negotiation via GROUP-HUB.md

**Head or Sub.** State lives in `GROUP-HUB.md` at the Head repo root; the hub carries thread status and the registry, while contract bodies live in git under Head `docs/group/shared/` and are referenced by path + commit. Sub never mirrors `shared/` locally — it reads it at `head.path` when a thread references it.

Hub path:

- **Head:** `GROUP-HUB.md` (repo root)
- **Sub:** resolve hub from `group.manifest.yaml` — walk `head.paths` when present (first existing `<path>/GROUP-HUB.md`), else `head.path`; edit your `sub_id` sections only

---

## Determine mode

| Situation | Role | Action |
|-----------|------|--------|
| User describes a new contract | Head | New thread `sync_delta` |
| Thread `awaiting_sub` for this sub | Sub | Compare against `shared/` at `head.path`; ack or dispute in the thread |
| Thread `awaiting_head` with a dispute | Head | Verdict in the thread; update `shared/` if needed |
| Sub finished work Head's backlog tracks (no `shared/` change) | Sub | Delivery notice — open thread, set `awaiting_head`, hand off (see below) |
| A delivery-notice thread is `awaiting_head` | Head | Update Head's own backlog docs, verdict, close, archive |

Process one thread at a time, oldest `awaiting_*` first. In the Head repo a Sub session writes one file — `GROUP-HUB.md` (its own registry row and its own thread) — and sets the thread's status to whoever acts next. That is the Sub's step; Head's merge, close, archive, and any other Head-doc update run later, in the Head session.

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

---

## Sub — response (awaiting_sub)

1. Read the thread and the referenced files directly from Head `shared/` at `head.path` (or `head.paths`) — no local install step.
2. **Aligned:** update `integration.md`; set the thread → `closed`; registry → `stable`.
3. **Gaps:** fill `sub_response` with accepted items + D1, D2…; `status` → `awaiting_head`; increment `dispute_round` (max 3 → `defer_manual` in summary).
4. Update Sub `docs/todo.md` Hub pending → `awaiting_head` where applicable.
5. Doc file edits go through `doc-librarian` with explicit scope.
6. Setting the status is your final action here: `closed` on an aligned ack (your own ack closes the cycle Head started), or `awaiting_head` when you hand it back with gaps. Either way the Sub side is complete — Head's steps run later, in the Head session.

---

## Sub — delivery notice (implementation done, no contract change)

For work Head's own backlog tracks — no `docs/group/shared/` change involved:

1. Open a thread: `sync_delta`, `severity: info`, `status: awaiting_head`, `sub_response` = what was delivered and what you want Head to do with it (e.g. "mark `operations.log` done in your backlog").
2. Registry row: bump `last_event`; leave `state: stable` (this is not a renegotiation).
3. Update your own `integration.md` and `docs/todo.md` Hub pending (`awaiting_head`).
4. The thread now waits at `awaiting_head` — that is the whole Sub step. Head updates its backlog doc, records the verdict, closes, and archives, later in the Head session (see *Head — merge*).

---

## Head — merge (awaiting_head)

Runs in the **Head session** — this is where a thread's write surface widens beyond `GROUP-HUB.md` to the rest of the Head repo.

1. Read `sub_response` — a dispute, or a delivery notice's summary.
2. **Dispute:** update `docs/group/shared/` per agreement. **Delivery notice:** update whatever Head backlog doc it names (`docs/todo.md`, `docs/admin-hub/integration.md`, `docs/group/shared/registry-mapping*.md`, etc.).
3. Fill `verdict`; set `status` → `awaiting_sub` (for the Sub to ack) or `closed` if resolved.
4. On close: update `docs/group/README.md` sub table; archive the thread summary to `docs/group/archive/<sub-id>/`.
5. Remove the Hub pending line from both repos' `todo.md` when `closed`.

---

## Delegate doc edits

Once a step is decided, invoke `maintain-docs` → `doc-librarian` with task (one sentence), scope (explicit file list), and StateFields for `integration.md` / group README. The librarian edits files; timing stays here.

The hub holds pointers and status; contract bodies stay in git under `shared/`, and each Sub edits only its own threads.

## Tools

```powershell
python scripts/sync-status.py --repo .
```
