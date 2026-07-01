# Protocol reference — epoch 0

Head baseline snapshot for group `1c-cursor` (Sub: `1c-config-mcp`, `1c-data-mcp`, `1c-help-mcp`).

| Document | Contents |
|----------|----------|
| [`protocol-v1.md`](protocol-v1.md) | Consolidated Protocol v1 |
| [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) | schemas, discovery, exit codes |
| [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md) | Hub persistence, reconcile, IDs |
| [`protocol-v1.0.3-addendum.md`](protocol-v1.0.3-addendum.md) | UTF-8 JSON I/O for CLI stdout/input |
| [`registry-mapping.md`](registry-mapping.md) | Hub ↔ config-mcp mapping (agreed 2026-06-28) |

On protocol version conflict: **v1.0.3 > v1.0.2 > v1.0.1 > v1**.

Canon edits — Head only; delivery to Sub — packets via `docs/group/outbox/` and operator copy per [`../../OPERATOR-HANDOFF.md`](../../OPERATOR-HANDOFF.md).

Hub implementation specifics (integration, negotiation archive) — [`../../../admin-hub/`](../../../admin-hub/).
