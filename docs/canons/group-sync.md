# Canon: group documentation sync

Version: **2.3.0**

Packet sync **Head ↔ Sub** (star topology). Protocol baseline + deltas after `stable`. Operator manually copies files between repositories.

---

## Principles

1. **Head** — canon keeper (`docs/group/shared/`).
2. **Sub** — local specs + `integration.md` + `protocol-ref/epoch<N>/`.
3. **Sub ↔ Sub** — only via Head.
4. **Inbox/outbox** — ephemeral, not in git; operator copies sender outbox → recipient inbox.
5. **Review-snapshot** — on contract proposals, `review-snapshot-<ts>/` next to packet with doc copies for review.
6. **Durable canon** — `shared/`, `protocol-ref/epoch<N>/`, `docs/group/archive/` after ack.
7. **Mapping** — integration contracts in `docs/group/shared/` (e.g. `registry-mapping.md` in config-mcp).

---

## Skills

| Skill | Role | Purpose |
|-------|------|---------|
| `sync-base` | Head | Sub onboarding: full snapshot + `protocol_offer` in outbox |
| `sync` | Head, Sub | Negotiation cycle + inbox processing |

Packet templates: `docs/group/templates/` (after normalize) or `../../templates/` in WI.

Operator: `docs/group/OPERATOR-HANDOFF.md` — copy paths (filled on normalize). Human-tier — Russian OK.

---

## Protocol states

| state | Meaning |
|-------|---------|
| `negotiating` | offer / dispute / merge in progress |
| `stable` | Sub accepted current `protocol_epoch` |
| `stale` | Head raised epoch; Sub has not accepted ripple yet |

Fields: `protocol_epoch`, `protocol_sync_state`, `stable_at`, `open_disputes`, `dispute_round` (max 3 → `defer_manual`).

Head maintains Sub table in `docs/group/README.md`: `sub_id | epoch | state | last_ack`.

---

## Sync modes

| Mode | When | Skill |
|------|------|-------|
| **Baseline** | First alignment, new Sub | `sync-base` |
| **`sync_delta`** | Contract / delta after `stable` | `sync` |
| **Ripple** | Epoch bump in `shared/` | `sync` + snapshot (see below) |

### Negotiation cascade

```
sync_delta (proposal) → protocol_dispute → protocol_merge → protocol_ack → stable
```

or on onboarding:

```
protocol_offer → protocol_ack → stable
```

Critical change from Sub A reaches Sub B **only through Head**.

---

## Head: when to ripple

| Situation | Action |
|-----------|--------|
| **Epoch bump** in `shared/`, affects all Subs | `protocol_ripple` + snapshot in outbox of each lagging Sub (`sync-base` style) |
| **Single Sub contract** (mapping, addendum) | `sync` / `sync_delta` only to that Sub; no ripple if epoch unchanged |
| **One Sub ack changed shared norm** others already installed | Optional ripple to affected Subs |

---

## Packet types (`kind`)

| kind | direction | Content |
|------|-----------|---------|
| `protocol_offer` | H→Sub | Snapshot catalog + summary |
| `protocol_dispute` | Sub→H | Accepted without dispute + gaps (D1, D2, …) |
| `protocol_merge` | H→Sub | Verdict table by ID + shared changes |
| `protocol_ack` | Sub→H | epoch accepted → stable |
| `protocol_ripple` | H→Sub | Canon changed; new offer |
| `sync_delta` | H→Sub | Delta / contract after stable |

Dispute template: `protocol-dispute.example.md`  
Delta template: `sync-packet.example.md`

After processing: delete packet from inbox.

---

## Topology and directories

### Head

```
docs/group/outbox/<sub-id>/<packet>.md
docs/group/outbox/<sub-id>/protocol-snapshot-epoch<N>-<ts>/
docs/group/outbox/<sub-id>/review-snapshot-<ts>/
docs/group/inbox/<sub-id>/<packet>.md
docs/group/archive/<sub-id>/          # committed, after ack
```

### Sub

```
docs/group/inbox/<packet>.md
docs/group/inbox/protocol-snapshot-epoch<N>-<ts>/
docs/group/inbox/review-snapshot-<ts>/
docs/group/outbox/<packet>.md
docs/group/protocol-ref/epoch<N>/    # stable copy, in git
docs/group/templates/                 # packet templates
```

---

## Packet format (common)

```yaml
---
packet_version: 1
kind: sync_delta
from: <module-id>
to: <module-id>
direction: head_to_sub | sub_to_head
severity: critical | info
protocol_epoch: <N>
affects:
  - docs/group/integration.md
summary: |
  ...
---
```

---

## group.manifest.yaml

### Head

```yaml
group:
  id: <group-id>
  canon_version: "2.4.0"
role: head
subordinates:
  - id: <sub-id>
    path: C:/projects/<sub-repo>   # for OPERATOR-HANDOFF.md
```

### Sub

```yaml
id: <sub-module-id>
group:
  id: <group-id>
role: subordinate
head:
  id: <head-id>
  path: C:/projects/<head-repo>    # for OPERATOR-HANDOFF.md
```

---

## Tools

```powershell
python scripts/protocol-snapshot.py --export --repo . --sub <id>
python scripts/protocol-snapshot.py --attach-review --repo . --sub <id> --files <paths...>
python scripts/protocol-snapshot.py --install --repo .
python scripts/sync-status.py --repo .
python scripts/sync-status.py --operator-check --repo .
```

---

## Subagents

| Agent | Roles |
|-------|-------|
| `doc-librarian` | S, H, Sub — bulk doc edits (`maintain-docs`) |

Group sync — skill `sync` / `sync-base`, not a separate subagent.

Templates: `../../templates/skills/`, `../../templates/agents/`

---

## Example group

`../../examples/1c-cursor-group.manifest.yaml`
