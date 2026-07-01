# Интеграция с группой

## Головной проект

- **group id:** `1c-cursor`
- **head id:** `1c-admin-tool`
- **путь:** `C:/projects/1c-admin-tool`
- **канон протокола:** `C:/projects/1c-admin-tool/docs/group/shared/`
- **карта группы (Head):** `C:/projects/1c-admin-tool/docs/group/README.md`

## Состояние протокола

| Поле | Значение |
|------|----------|
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

## Синхронизация (пакеты)

- **inbox:** `docs/group/inbox/` — пакеты от Head (gitignored, обработать и удалить)
- **outbox:** `docs/group/outbox/` — пакеты для Head → `sync-relay.py --deliver`
- **protocol-ref:** `docs/group/protocol-ref/epoch<N>/` — зафиксированный baseline от Head (коммитить после reconcile)

Перед работой: skill `process-group-inbox` или doc-librarian.

## Версии синхронизации (дельты после stable)

| Поле | Значение |
|------|----------|
| last_sync_from_head | |
| last_sync_to_head | |

## Локальные отклонения

- **Операционный канон Hub:** [`docs/admin-hub/`](../admin-hub/) — локальная адаптация managed tool (маппинг на `docs/group/shared/` у Head; см. WI `examples/1c-cursor-group.manifest.yaml`).
- **Admin Hub Phase 3:** headless `rebuild-index` / `rebuild-all` / `reconcile-markers` реализованы; контракт в [`integration.md`](../admin-hub/integration.md) § Phase 3 CLI.
- **Ephemeral handoff:** отчёты для других команд — `HANDOFF-*.md` в корне (gitignored); правило [`.cursor/rules/cross-team-handoff.mdc`](../../.cursor/rules/cross-team-handoff.mdc).
- **Структура кода:** `admin_tool/`, `server/`, `shared/` (не `src/`).
- **protocol-ref:** `docs/group/protocol-ref/epoch0/` — Head baseline (epoch 0, v1.0.3); локальные указатели — `docs/admin-hub/`.

## Статус

| Область | Статус | Примечание |
|---------|--------|------------|
| Hub / group integration | stable | epoch 0 принят; merge `20260630T162902`, v1.0.3 в protocol-ref |
| Admin Hub Phase 3 CLI | готово | `shared/hub_rebuild.py`, `admin_tool/cli.py` |
| Portable MCP runtime | автономен | Не зависит от Hub для query plane |
