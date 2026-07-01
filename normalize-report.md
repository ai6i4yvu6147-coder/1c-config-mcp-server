# Отчёт о нормализации: 1c-config-mcp

**Дата:** 2026-06-30  
**Роль:** Sub (subordinate)  
**Канон:** 2.2.0 (Workspace improve)  
**Метод:** agent-first (без `normalize-apply.py`)

---

## Идентификаторы

| Поле | Значение |
|------|----------|
| Модуль (sub id) | `1c-config-mcp` |
| Группа | `1c-cursor` |
| Head | `1c-admin-tool` |
| Путь к Head | `C:/projects/1c-admin-tool` |
| Состояние протокола | `negotiating`, epoch 0 |

Head в этом заходе **не изменялся** — только зафиксирован в manifest и docs.

---

## Что сделано

### Структура (канон Sub)

| Артефакт | Статус |
|----------|--------|
| `group.manifest.yaml` | Создан, заполнен |
| `docs/group/integration.md` | Создан, заполнен (локальные отклонения: `docs/admin-hub/`, Phase 3) |
| `docs/group/inbox/`, `outbox/` | Созданы (gitignored) |
| `docs/canons/` | Локальная копия WI (5 канонов + README) |
| `docs/normalize-record.md` | Создан |
| `scripts/` | `project-doctor`, `sync-relay`, `sync-status`, `protocol-snapshot` |
| `.cursor/skills/` | 9 skills |
| `.cursor/agents/` | 2 agents (`doc-librarian`, `group-sync-arbitrator`) |
| `README.md` | Создан (entry-point) |
| `readme.txt` | Удалён (FORBIDDEN project-doctor) |
| `requirements.txt` | merge: `mcp`, `pyinstaller`, `pyyaml>=6.0` |

### Документация

| Файл | Изменение |
|------|-----------|
| `AGENTS.md` | Роль Sub, skills/agents, project-doctor |
| `docs/README.md` | Секции group + canons |
| `docs/agent-onboarding.md` | Тип Sub, inbox |
| `CHANGELOG.md` | Запись 2026-06-30 |

### Сохранено без изменений

- `docs/admin-hub/` — локальный операционный канон Hub
- Продуктовый код (`admin_tool/`, `server/`, `shared/`)
- `.cursor/rules/` (включая `cross-team-handoff.mdc`)

---

## Что намеренно НЕ делали

| Артефакт | Причина |
|----------|---------|
| `templates/` в репо | Только в WI |
| `normalize.bundle.yaml`, `normalize-apply.py` | Legacy; agent-first |
| `protocol-ref/epoch<N>/` | После protocol reconcile |
| `.cursor/hooks.json` | Не в чеклисте Sub 2.2.0 |
| 4 agents (canon-align, inbox-processor, …) | В bundle только 2 agents |
| Перезапись `requirements.txt` | Урок инцидента 2026-06-30 (сломало MCP) |

---

## project-doctor

```
project-doctor: C:\projects\1c-config-mcp
  type: Sub (canon 2.2.0)

OK (0 warning(s))
```

## Тесты

`pytest tests/test_hub_rebuild.py tests/test_hub_protocol.py` — 14 passed.

---

## Следующие шаги

1. Protocol reconcile с Head → `docs/group/protocol-ref/epoch1/` (skill `run-protocol-reconciliation`).
2. После `stable` — дельты через inbox/outbox (`sync-relay.py`).
3. Head: разместить канон в `docs/group/shared/` (маппинг с локальным `docs/admin-hub/`).

---

## Урок (обратная связь WI)

Предыдущий заход через устаревший `normalize-apply.py --upgrade-wi` перезаписал `requirements.txt` и скопировал лишнее (`templates/`, `protocol-ref/`). Текущая нормализация — по `initiators/subordinate.md` и канону 2.2.0 agent-first.
