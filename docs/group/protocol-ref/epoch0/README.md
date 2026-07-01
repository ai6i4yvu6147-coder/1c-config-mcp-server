# Shared — канон группы 1c-cursor

Общие спецификации для Head и Sub (`1c-config-mcp`, `1c-data-mcp`, `1c-help-mcp`).

| Документ | Содержание |
|----------|------------|
| [`protocol-v1.md`](protocol-v1.md) | Consolidated Protocol v1 |
| [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) | schemas, discovery, exit codes |
| [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md) | Hub persistence, reconcile, IDs |
| [`protocol-v1.0.3-addendum.md`](protocol-v1.0.3-addendum.md) | UTF-8 JSON I/O для CLI stdout/input |
| [`registry-mapping.md`](registry-mapping.md) | Hub ↔ config-mcp mapping (agreed 2026-06-28) |

При конфликте версий протокола: **v1.0.3 > v1.0.2 > v1.0.1 > v1**.

Редактирование канона — только на Head; доставка Sub — пакеты через `docs/group/outbox/` и `sync-relay.py`.

Hub-специфика реализации (integration, архив переговоров) — [`../admin-hub/`](../admin-hub/).
