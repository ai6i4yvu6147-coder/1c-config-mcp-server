# Каноны структуры проектов

Локальная копия стандартов Workspace improve (canon **2.2.0**). Источник обновлений: `C:\projects\Workspace improve\docs\canons\`.

## Порядок чтения

1. `project-structure.md` — S / H / Sub, базовый каркас
2. `documentation.md` — иерархия docs
3. `normalize-governance.md` — agent-first normalize
4. `normalize-merge.md` — слияние с существующим репо
5. `group-sync.md` — пакетная синхронизация, protocol reconcile

## Версионирование

| Версия | Дата | Изменение |
|--------|------|-----------|
| 2.0.0 | 2026-06-29 | Универсальная модель S / H / Sub |
| 2.1.0 | 2026-06-29 | Пакетная синхронизация inbox/outbox |
| 2.2.0 | 2026-06-30 | Agent-first normalize; protocol states; arbitrator; 2 субагента |

Отдельные файлы канона могут иметь собственный номер версии в заголовке; ориентир для репозитория — `canon_version` в `group.manifest.yaml` (2.2.0).

## Артефакты в этом репозитории

| Артефакт | Путь |
|----------|------|
| Манифест группы | `group.manifest.yaml` |
| Интеграция Sub | `docs/group/integration.md` |
| Запись normalize | `docs/normalize-record.md` |
| Проверка | `scripts/project-doctor.py` |
| Relay | `scripts/sync-relay.py` |
| Skills / agents | `.cursor/skills/` (9), `.cursor/agents/` (2: doc-librarian, group-sync-arbitrator) |

Шаблоны и initiators остаются в Workspace improve — в продуктовый репозиторий не копируются.
