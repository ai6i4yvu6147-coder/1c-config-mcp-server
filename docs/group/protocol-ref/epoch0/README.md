# Protocol reference — epoch 0

Head baseline snapshot for group `1c-cursor` (installed from Head `docs/group/shared/` @ `cf3336a`).

| Document | Contents |
|----------|----------|
| [`protocol-v1.md`](protocol-v1.md) | Consolidated Protocol v1 |
| [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) | schemas, discovery, exit codes |
| [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md) | Hub persistence, reconcile, IDs |
| [`protocol-v1.0.3-addendum.md`](protocol-v1.0.3-addendum.md) | UTF-8 JSON CLI encoding (no BOM) |
| [`protocol-v1.0.4-addendum.md`](protocol-v1.0.4-addendum.md) | data-mcp sealed credentials |
| [`protocol-v1.0.5-addendum.md`](protocol-v1.0.5-addendum.md) | data-mcp canonical CLI write surface |
| [`protocol-v1.0.6-addendum.md`](protocol-v1.0.6-addendum.md) | passive Hub + agent `unlock_credentials` |
| [`registry-mapping.md`](registry-mapping.md) | Hub ↔ config-mcp mapping (agreed 2026-06-28) |
| [`registry-mapping-data-mcp.md`](registry-mapping-data-mcp.md) | Hub ↔ data-mcp mapping (agreed 2026-07-01) |

On protocol version conflict: **v1.0.6 > v1.0.5 > v1.0.4 > v1.0.3 > v1.0.2 > v1.0.1 > v1**.

Canon edits — Head only (`docs/group/shared/`); Sub installs updates via hub threads and `protocol-snapshot.py`.

Local managed-tool adaptation — [`../../admin-hub-integration.md`](../../admin-hub-integration.md).
