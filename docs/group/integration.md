# Group integration

## Head project

- **group id:** `1c-cursor`
- **head id:** `1c-admin-tool`
- **hub:** `C:/projects/1c-admin-tool/GROUP-HUB.md` · `C:/repo/1c-config-admin-tool/GROUP-HUB.md`

## Protocol state

| Field | Value |
|-------|-------|
| protocol_epoch | 0 |
| protocol_sync_state | stable (THR-009 proposed — role block ripple to data-mcp) |
| stable_at | 2026-07-03T11:15:00Z |
| protocol_ref | `docs/group/protocol-ref/epoch0/` |
| open_disputes | 0 |
| dispute_round | 0 |

## Sync (hub)

State lives in the Head hub (`head.paths` in `group.manifest.yaml`): `C:/projects/1c-admin-tool/GROUP-HUB.md` · `C:/repo/1c-config-admin-tool/GROUP-HUB.md`. This project edits only its own `sub_id` (`1c-config-mcp`) registry row and threads.

Session start: if `docs/todo.md` has `## Hub pending`, run skill **`sync`**.

## Local deviations

- **Hub operational canon:** [`docs/admin-hub-integration.md`](../admin-hub-integration.md) — local managed-tool adaptation (mapping to Head `docs/group/shared/`).
- **Admin Hub Phase 3:** headless `rebuild-index` / `rebuild-all` / `reconcile-markers` implemented; contract in admin-hub-integration § Phase 3 CLI.
- **Admin Hub Phase 2 ops:** `operations.log` JSONL audit — **done** on Sub (`shared/operations_log.py`); **THR-008** open `awaiting_head` (Head backlog update pending).
- **Ephemeral handoff:** reports for other teams — `HANDOFF-*.md` in repo root (gitignored); rule `.cursor/rules/cross-team-handoff.mdc`.
- **Code layout:** `admin_tool/`, `server/`, `shared/` (not `src/`).
- **Role block (phase 4 + UX polish):** implemented on Sub; cross-MCP contract in [`roles-layer.md`](../roles-layer.md). **THR-009** proposed to Head (`awaiting_head`) — ripple to `1c-data-mcp` pending Head `docs/group/shared/roles-cross-mcp.md`.
- **protocol-ref:** `docs/group/protocol-ref/epoch0/` — Head baseline @ `cf3336a` (v1.0.6 + registry-mapping-data-mcp); local operational detail — `admin-hub-integration.md`.

## Status

| Area | Status | Note |
|------|--------|------|
| Hub / group integration | stable | THR-008 open (`awaiting_head`) — operations.log delivery |
| Admin Hub Phase 3 CLI | done | `shared/hub_rebuild.py`, `admin_tool/cli.py` |
| Admin Hub Phase 2 ops | done (Sub) | `shared/operations_log.py`; Head ack via THR-008 |
| Portable MCP runtime | autonomous | Does not depend on Hub for query plane |
