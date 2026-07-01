# Отчёт о нормализации: 1c-config-mcp

> **Current state (2026-07-02):** canon **2.4.0** · Sub · 1 agent (`doc-librarian`) · 4 skills · agent-cache docs English (`agent_docs_lang: en`). Authoritative metadata: [`docs/normalize-record.md`](docs/normalize-record.md). Sections below are historical normalize passes.

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

1. Дельты после `stable` — skill **`sync`** + оператор по `OPERATOR-HANDOFF.md`.
2. Head: поддерживать канон в `docs/group/shared/` (маппинг с локальным `docs/admin-hub/`).

---

## Урок (обратная связь WI)

Предыдущий заход через устаревший `normalize-apply.py --upgrade-wi` перезаписал `requirements.txt` и скопировал лишнее (`templates/`, `protocol-ref/`). Первая нормализация — по `initiators/subordinate.md` и канону 2.2.0 agent-first.

---

## Re-normalize 2.3.0

**Дата:** 2026-07-01  
**Канон:** WI **2.3.0** (operator handoff, unified skill `sync`)

### Изменения layout

| Было (2.2.0) | Стало (2.3.0) |
|--------------|---------------|
| 9 skills, 2 agents | 4 skills, 1 agent (`doc-librarian`) |
| `scripts/sync-relay.py` | **Удалён** — оператор копирует outbox→inbox по `docs/group/OPERATOR-HANDOFF.md` |
| 6 legacy group-sync skills | Единый skill **`sync`** |
| `group-sync-arbitrator` agent | **Удалён** |
| — | `docs/group/OPERATOR-HANDOFF.md`, `docs/group/templates/` |

### Сохранено без изменений

- `protocol_sync_state: stable`, epoch 0, `protocol-ref/epoch0/`
- `docs/admin-hub/`, продуктовый код, `cross-team-handoff.mdc`
- `requirements.txt` (merge, не overwrite)

### project-doctor (2.3.0)

```
project-doctor: C:\projects\1c-config-mcp
  type: Sub (canon 2.3.0)

OK (0 warning(s))
```

### Entry-point docs

Обновлены: `AGENTS.md`, `docs/README.md`, `docs/agent-onboarding.md`, `docs/todo.md`, `README_AI.md`, `CHANGELOG.md`.

---

## Re-normalize 2.4.0

**Дата:** 2026-07-02  
**Канон:** WI **2.4.0** (agent-cache tier English, language migration)

### Removed (deprecations)

Блок `2.3.0` из `normalize.deprecations.yaml` (local 2.3.0 → target 2.4.0):

| Путь | Статус |
|------|--------|
| `scripts/sync-relay.py` | удалён (ранее 2.3.0) |
| `.cursor/agents/group-sync-arbitrator.md` | удалён |
| `.cursor/skills/emit-group-sync-packet` | удалён |
| `.cursor/skills/process-group-inbox` | удалён |
| `.cursor/skills/export-group-protocol` | удалён |
| `.cursor/skills/import-group-protocol` | удалён |
| `.cursor/skills/run-protocol-reconciliation` | удалён |
| `.cursor/skills/review-protocol-diff` | удалён (subordinate) |

### Изменения layout

| Область | Действие |
|---------|----------|
| `docs/canons/` | Скопированы из WI (English, canon 2.4.0) |
| `.cursor/skills/` | Обновлены из WI templates (English) |
| `.cursor/agents/doc-librarian.md` | Обновлён (секция Language migration) |
| `group.manifest.yaml` | `canon_version: 2.4.0` |
| `scripts/project-doctor.py` | Обновлён (canon 2.4.0) |
| Agent-cache tier docs | Переведены на English (`agent_docs_lang: en`) |

### Сохранено без изменений

- `protocol_sync_state: stable`, epoch 0, `protocol-ref/epoch0/` (значения полей)
- `docs/admin-hub/`, продуктовый код, `cross-team-handoff.mdc`
- `CHANGELOG.md`, `docs/group/OPERATOR-HANDOFF.md` (human tier)
- `requirements.txt` (merge, не overwrite)
- `protocol-ref/epoch0/protocol-v1*.md`, `registry-mapping.md` (технический контент)

### project-doctor (2.4.0)

```
project-doctor: C:\projects\1c-config-mcp
  type: Sub (canon 2.4.0)

OK (0 warning(s))
```

