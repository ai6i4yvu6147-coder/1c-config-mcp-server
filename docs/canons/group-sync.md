# Canon: group documentation sync

Version: **2.5.1**

Star topology **Head ↔ Sub**. Group sync state lives in a single **`GROUP-HUB.md`** at the Head repo root; contract bodies live in git and are referenced from the hub by path + commit. The operator handles credentials and deploy only — no packet copying.

---

## Principles

1. **Head** — owns `docs/group/shared/` (shared canon) and `GROUP-HUB.md`.
2. **Sub** — owns `integration.md` + `protocol-ref/epoch<N>/`; reads/writes the hub at `<head.path>/GROUP-HUB.md` in its own `sub_id` sections only.
3. **Sub ↔ Sub** — only through Head.
4. **Each session acts in its own repo and does its own step.** From a Sub session the one file written in the Head repo is `GROUP-HUB.md` — the Sub's own registry row and its own thread; the Sub sets the thread's status to whoever acts next, and that completes its step. Head's other docs (`docs/todo.md`, `shared/`, `archive/`) are updated by the Head session when it later picks up the thread — a thread's `affects:` field is that to-do list for Head. (A Head session writes in a Sub only to install a snapshot a thread calls for.)
5. **Hub** — carries threads + registry (status metadata), **not** agent-cache tier; read when `docs/todo.md` has `## Hub pending` or the user invokes sync.
6. **Contracts** — committed under `docs/group/shared/` (Head) or `protocol-ref/epoch<N>/` (Sub); the hub links them, never inlines them.
7. **Todo queue** — `## Hub pending` in `docs/todo.md` is the ~50-token signal the orchestrator checks before reading the full hub.

---

## Skills

| Skill | Role | Purpose |
|-------|------|---------|
| `sync-base` | Head | Onboard a Sub: snapshot export + `protocol_offer` thread |
| `sync` | Head, Sub | Negotiation cycle via hub threads |

Group sync is a **skill**, not a subagent. `doc-librarian` edits doc files *after* a step is decided.

---

## Protocol states

| state | Meaning |
|-------|---------|
| `negotiating` | A thread is in progress |
| `stable` | Sub accepted the current `protocol_epoch` |
| `stale` | Head bumped the epoch; Sub has not accepted the ripple yet |

Fields: `protocol_epoch`, `dispute_round` (max 3 → `defer_manual`). Head keeps the registry table in `GROUP-HUB.md` and mirrors the sub summary in `docs/group/README.md`.

A **delivery notice** (Sub reporting tracked implementation work, no `shared/` contract change) does not renegotiate the protocol: the registry `state` stays `stable`, only `last_event` moves. Reserve `negotiating` for an actual contract change in flight.

---

## Thread lifecycle

```
sync_delta → (dispute) → merge → ack → closed → archive           (contract change)
sync_delta severity: info → awaiting_head → closed → archive      (Sub delivery notice)
protocol_offer → ack → stable      (onboarding)
protocol_ripple → ack → stable     (epoch bump)
```

Thread status: `awaiting_sub` | `awaiting_head` | `closed`.

**When a hub thread is needed:** a `shared/` contract change always opens one (Head-initiated). Sub-side implementation of an already-specified protocol needs Sub-local docs only — open a delivery-notice thread (`severity: info`) only if Head's own backlog needs to be told and cleared. A one-off cross-team note that isn't group protocol state belongs in an ephemeral handoff file, not the hub.

Kinds (`kind`): `protocol_offer` | `protocol_dispute` | `protocol_merge` | `protocol_ack` | `protocol_ripple` | `sync_delta`.

---

## Who decides when

- **Orchestrator** — recognizes triggers (todo Hub pending, user `/sync`, registry `stale`, contract edit in `shared/`) and invokes the skill.
- **Skill `sync` / `sync-base`** — runs the protocol steps and thread state.
- **`doc-librarian`** — edits doc files after a step is decided.

---

## GROUP-HUB.md

Committed at the Head repo root. Frontmatter carries `hub_version`, `group_id`, `protocol_epoch`. Body sections:

- **Registry** — `sub_id | state | epoch | dispute_round | last_event`
- **Active threads** — one block per open thread (see skill `sync` for the block shape)
- **Thread rules** — `THR-<NNN>` monotonic; a Sub edits only threads matching its manifest `id`; Head owns epoch bumps, verdicts, and new proposals; on `closed`, move the summary to `docs/group/archive/<sub-id>/` and clear the Active threads block.

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
docs/group/exports/<sub-id>/ # snapshot staging (ephemeral, gitignored)
docs/group/archive/<sub-id>/ # closed-thread summaries
```

A snapshot the hub thread references lives under `exports/<sub-id>/`; the Sub reads it via `head.path` and installs into its own `protocol-ref/`.

### Sub

```
docs/group/integration.md        # protocol state fields, link to Head
docs/group/protocol-ref/epoch<N>/ # stable snapshot, in git
```

Hub access: `group.manifest.yaml` → `head.path` + `/GROUP-HUB.md`.

---

## group.manifest.yaml

### Head

```yaml
group:
  id: <group-id>
  canon_version: "2.5.0"
role: head
subordinates:
  - id: <sub-id>
    path: C:/projects/<sub-repo>   # for hub-path resolution
```

### Sub

```yaml
id: <sub-module-id>
group:
  id: <group-id>
  canon_version: "2.5.0"
role: subordinate
head:
  id: <head-id>
  path: C:/projects/<head-repo>    # hub lives at head.path/GROUP-HUB.md
```

---

## Migrating 2.4 → 2.5 (packet → hub)

The 2.5 deprecations remove inbox/outbox and packet templates. Cut a live group over only when it is **stable** (no open disputes) — finish any in-flight packet negotiation under the old model first.

**Order — Head first.** The hub file lives at the Head; a Sub's `sync` skill targets `<head.path>/GROUP-HUB.md`. Normalize the Head to 2.5 (creating `GROUP-HUB.md`) before the Subs, or a Sub's sync points at a file that does not exist.

**Seed the hub from current state** — no thread-history reconstruction:

1. Create `GROUP-HUB.md` from `templates/head/GROUP-HUB.md`; set frontmatter `protocol_epoch` from `docs/group/README.md`.
2. Add one Registry row per Sub from the `docs/group/README.md` sub table: `state`, `epoch`, `dispute_round: 0`, `last_event` = last ack date. A stable group starts with **no Active threads**.
3. Leave `docs/group/archive/` and `protocol-ref/` as they are — closed packet-era negotiations stay archived, not re-threaded.

**Operator runbook:** its packet-copy content is obsolete under the hub — refresh `docs/group/OPERATOR-HANDOFF.md` from `templates/operator/group-handoff-runbook.md` (credentials/deploy only), preserving any project-specific entries. It stays human-tier (Russian OK, not auto-translated).

**Sub `integration.md`:** re-template to the hub form; packet-era fields (`last_offer_from_head`, `last_merge_from_head`, `disputes_resolved`, sync-version table) are dropped — keep any you still need under **Local deviations**.

After cutover, future changes flow through hub threads via `sync`.

---

## Tools

```powershell
python scripts/protocol-snapshot.py --export --repo . --sub <id>
python scripts/protocol-snapshot.py --attach-review --repo . --sub <id> --files <paths...>
python scripts/protocol-snapshot.py --install --repo . --from <head.path>/docs/group/exports/<sub-id>/<snapshot-dir>
python scripts/sync-status.py --repo .
```

---

## Example group

`../../examples/1c-cursor-group.manifest.yaml`
