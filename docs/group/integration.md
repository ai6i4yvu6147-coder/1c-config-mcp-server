# Group integration

## Head project

- **group id:** `1c-cursor`
- **head id:** `1c-admin-tool`
- **path:** `C:/projects/1c-admin-tool`
- **protocol canon:** `C:/projects/1c-admin-tool/docs/group/shared/`
- **group map (Head):** `C:/projects/1c-admin-tool/docs/group/README.md`

## Protocol state

| Field | Value |
|-------|-------|
| protocol_epoch | 0 |
| protocol_sync_state | stable |
| stable_at | 2026-06-30T06:30:05Z |
| protocol_ref | `docs/group/protocol-ref/epoch0/` |
| last_offer_from_head | `20260630T062304-1c-admin-tool` (snapshot `protocol-snapshot-epoch0-20260630T062240`) |
| last_merge_from_head | `20260630T162902-1c-admin-tool` (verdict `accept_sub_addendum`, v1.0.3) |
| open_disputes | 0 |
| disputes_resolved | 1 |
| dispute_round | 0 |

`protocol_sync_state`: `negotiating` | `stable` | `stale`

## Sync (packets)

- **inbox:** `docs/group/inbox/` — packets from Head (gitignored, process and delete)
- **outbox:** `docs/group/outbox/` — after skill **`sync`**
- **operator:** copy between repos — [`OPERATOR-HANDOFF.md`](OPERATOR-HANDOFF.md)
- **protocol-ref:** `docs/group/protocol-ref/epoch<N>/` — fixed baseline from Head (commit after reconcile)

Before work: skill **`sync`** (when the operator reports inbox is ready).

## Sync versions (deltas after stable)

| Field | Value |
|-------|-------|
| last_sync_from_head | |
| last_sync_to_head | |

## Local deviations

- **Hub operational canon:** [`docs/admin-hub/`](../admin-hub/) — local managed tool adaptation (mapping to Head `docs/group/shared/`; see WI `examples/1c-cursor-group.manifest.yaml`).
- **Admin Hub Phase 3:** headless `rebuild-index` / `rebuild-all` / `reconcile-markers` implemented; contract in [`integration.md`](../admin-hub/integration.md) § Phase 3 CLI.
- **Ephemeral handoff:** reports for other teams — `HANDOFF-*.md` in repo root (gitignored); rule [`.cursor/rules/cross-team-handoff.mdc`](../../.cursor/rules/cross-team-handoff.mdc).
- **Code layout:** `admin_tool/`, `server/`, `shared/` (not `src/`).
- **protocol-ref:** `docs/group/protocol-ref/epoch0/` — Head baseline (epoch 0, v1.0.3); local pointers — `docs/admin-hub/`.

## Status

| Area | Status | Note |
|------|--------|------|
| Hub / group integration | stable | epoch 0 accepted; merge `20260630T162902`, v1.0.3 in protocol-ref |
| Admin Hub Phase 3 CLI | done | `shared/hub_rebuild.py`, `admin_tool/cli.py` |
| Portable MCP runtime | autonomous | Does not depend on Hub for query plane |
