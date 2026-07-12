# Canon: group documentation sync

Version: **2.6.0**

Star topology **Head ↔ Sub**. Group sync state lives in a single **`GROUP-HUB.md`** at the Head repo root; contract bodies live in git and are referenced from the hub by path + commit. The operator handles credentials and deploy only — no packet copying, no protocol snapshots.

---

## Principles

1. **Head** — owns `docs/group/shared/` (shared canon) and `GROUP-HUB.md`.
2. **Sub** — owns `integration.md`; reads `docs/group/shared/` at `head.path` directly (no local copy); reads/writes the hub at `<head.path>/GROUP-HUB.md` in its own `sub_id` sections only.
3. **Sub ↔ Sub** — only through Head.
4. **Each session acts in its own repo and does its own step.** From a Sub session the one file written in the Head repo is `GROUP-HUB.md` — the Sub's own registry row and its own thread; the Sub sets the thread's status to whoever acts next, and that completes its step. Head's other docs (`docs/todo.md`, `shared/`, `archive/`) are updated by the Head session when it later picks up the thread — a thread's `affects:` field is that to-do list for Head. (A Head session never edits inside a Sub repo.)
5. **Hub** — carries threads + registry (status metadata), **not** agent-cache tier; read when `docs/todo.md` has `## Hub pending` or the user invokes sync.
6. **Contracts** — committed under `docs/group/shared/` (Head only); the hub links them by path + commit, never inlines them, and Sub never mirrors them locally.
7. **Todo queue** — `## Hub pending` in `docs/todo.md` is the ~50-token signal the orchestrator checks before reading the full hub.

---

## Skills

| Skill | Role | Purpose |
|-------|------|---------|
| `sync-base` | Head | Onboard a Sub: registry row + intro thread |
| `sync` | Head, Sub | Negotiation cycle via hub threads |

Group sync is a **skill**, not a subagent. `doc-librarian` edits doc files *after* a step is decided.

---

## Protocol states

| state | Meaning |
|-------|---------|
| `negotiating` | A thread is in progress |
| `stable` | No open thread for this Sub |

There is no protocol-epoch/version tracking — `shared/` is the single live copy and Sub always reads it directly, so there is nothing to fall behind on between negotiations.

A **delivery notice** (Sub reporting tracked implementation work, no `shared/` contract change) does not renegotiate anything: the registry `state` stays `stable`, only `last_event` moves. Reserve `negotiating` for an actual contract change in flight.

---

## Thread lifecycle

```
sync_delta → (dispute) → merge → ack → closed → archive           (contract change)
sync_delta severity: info → awaiting_head → closed → archive      (Sub delivery notice)
```

Thread status: `awaiting_sub` | `awaiting_head` | `closed`.

**When a hub thread is needed:** a `shared/` contract change always opens one (Head-initiated). Sub-side implementation of an already-specified contract needs Sub-local docs only — open a delivery-notice thread (`severity: info`) only if Head's own backlog needs to be told and cleared. A one-off cross-team note that isn't group protocol state belongs in an ephemeral handoff file, not the hub.

Kinds (`kind`): `sync_delta` (covers both contract changes and delivery notices via `severity`).

A dispute on one thread is capped at `dispute_round` 3 → `defer_manual` (a human resolves it outside the hub); this is a per-thread circuit breaker, not a cluster-wide version concept.

---

## Who decides when

- **Orchestrator** — recognizes triggers (todo Hub pending, user `/sync`, contract edit in `shared/`) and invokes the skill.
- **Skill `sync` / `sync-base`** — runs the protocol steps and thread state.
- **`doc-librarian`** — edits doc files after a step is decided.

---

## GROUP-HUB.md

Committed at the Head repo root. Frontmatter carries `hub_version`, `group_id`. Body sections:

- **Registry** — `sub_id | state | last_event`
- **Active threads** — one block per open thread (see skill `sync` for the block shape)
- **Thread rules** — `THR-<NNN>` monotonic; a Sub edits only threads matching its manifest `id`; Head owns verdicts and new proposals; on `closed`, move the summary to `docs/group/archive/<sub-id>/` and clear the Active threads block.

---

## `## Hub pending` (todo signal)

A `## Hub pending` section in `docs/todo.md` lists open threads that need this repo's attention — the cheap signal read before the full hub. One line per open thread:

```
- [ ] THR-<id> <status> — <sub_id> — <topic> (<who> <date>)
```

`status` is `awaiting_sub` or `awaiting_head` (never `closed` — the line is deleted instead). Head writes a line for a proposal it opens; a Sub writes one when it replies (`awaiting_head`); the `sync` skill clears the line when its thread closes. `sync-status.py` parses these lines.

---

## Layout

### Head

```
GROUP-HUB.md                 # committed; registry + threads
docs/group/shared/           # shared canon (edited only here)
docs/group/README.md         # sub registry mirror
docs/group/archive/<sub-id>/ # closed-thread summaries
```

### Sub

```
docs/group/integration.md    # protocol state fields, link to Head
```

A Sub holds no local copy of the contract — it reads `docs/group/shared/...` at `head.path` directly when a thread references it. `integration.md` records only the sync-state fields, not a mirrored snapshot.

Hub access: `group.manifest.yaml` → `head.path` (or first resolvable entry in `head.paths`) + `/GROUP-HUB.md`.

---

## group.manifest.yaml

### Head

```yaml
group:
  id: <group-id>
  canon_version: "2.6.0"
role: head
subordinates:
  - id: <sub-id>
    path: C:/projects/<sub-repo>   # primary checkout on this machine
    paths:                         # optional — two-PC / multi-checkout
      - C:/projects/<sub-repo>
      - C:/repo/<sub-repo-alt-name>
```

### Sub

```yaml
id: <sub-module-id>
group:
  id: <group-id>
  canon_version: "2.6.0"
role: subordinate
head:
  id: <head-id>
  path: C:/projects/<head-repo>    # primary; hub at head.path/GROUP-HUB.md
  paths:                             # optional — two-PC / multi-checkout
    - C:/projects/<head-repo>
    - C:/repo/<head-repo-alt-name>
```

### Dual paths (optional)

When the same group spans machines with different checkout layouts (`C:/projects/...` vs `C:/repo/...`), keep a single canonical `path` plus an optional ordered `paths` list:

| Side | Field | Resolves |
|------|-------|----------|
| Sub `head` | `path` + optional `paths` | `<resolved>/GROUP-HUB.md` and `<resolved>/docs/group/shared/` |
| Head `subordinates[]` | `path` + optional `paths` | Sub repo root |

**Resolution:** walk `paths` in order when present; else use `path`. Pick the first entry where the target exists on disk (hub check: `GROUP-HUB.md` at Head root; sub check: repo root or `group.manifest.yaml`). Document both layouts in `docs/group/OPERATOR-HANDOFF.md`.

---

## Migrating 2.5 → 2.6 (drop protocol epochs and snapshots)

2.6 removes the epoch/dispute_round-at-registry-level model and the `protocol-ref/` / `exports/` snapshot mechanism. Sub reads `shared/` directly instead of installing a pinned copy. Cut a live group over only when it is **stable** (no open disputes) — finish any in-flight negotiation under the old model first.

**Order — Head first**, same reason as the 2.4→2.5 cutover: Sub's `sync` skill targets `<head.path>/GROUP-HUB.md`, so a schema change there must land before Subs re-normalize.

1. **Head:** re-normalize; `normalize.deprecations.yaml` removes `docs/group/exports/` and `scripts/protocol-snapshot.py`. Update `GROUP-HUB.md` frontmatter (drop `protocol_epoch`) and the Registry table (drop `epoch`, `dispute_round` columns) from the new template — carry over each Sub's current `state`/`last_event`.
2. **Each Sub, before deleting its local snapshot:** diff `docs/group/protocol-ref/epoch<N>/` against the Head's current `docs/group/shared/`. If they match, delete the snapshot on re-normalize — the deprecations file removes `docs/group/protocol-ref/`. If they **don't** match, that's real unsynced content, not waste: open a `sync_delta` thread with the diff before deleting anything.
3. **Sub:** re-normalize; re-template `integration.md` to drop `protocol_epoch`, `protocol_ref`, `open_disputes`, `dispute_round` persistent fields — keep any you still need under **Local deviations**.
4. No thread-history reconstruction — closed threads in `docs/group/archive/` stay as they are.

**Operator runbook:** refresh `docs/group/OPERATOR-HANDOFF.md` from `templates/operator/group-handoff-runbook.md` if it still references snapshot install steps, preserving any project-specific entries.

After cutover, all contract reads go straight to `shared/` at `head.path`; there is nothing left to install or pin.

---

## Tools

```powershell
python scripts/sync-status.py --repo .
```

---

## Example group

`../../examples/1c-cursor-group.manifest.yaml`
