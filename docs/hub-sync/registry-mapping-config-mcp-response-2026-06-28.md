# Ответы команды 1c-config-mcp на опросник: `project`, registry и Admin Hub

**Дата ответа:** 2026-06-28  
**Статус:** **согласовано** с ConfigAdmin / Admin Hub (2026-06-28, async)

Ответы основаны на текущем коде (`shared/project_manager.py`, `shared/registry_apply.py`, `shared/source_path.py`), документации [`docs/admin-hub/integration.md`](../admin-hub/integration.md) и backlog [`docs/todo.md`](../todo.md).

**Ответ Hub:** [`registry-mapping-hub-response-2026-06-28.md`](registry-mapping-hub-response-2026-06-28.md)

---

## Блок 1. Семантика `project` в config-mcp

### 1.1. Что для вас означает `project` в реальной работе?

**Контейнер видимости для MCP и группировка индексов**, а не «проект разработки» в смысле задачи/спринта.

На практике:

- В `projects.json` — верхний уровень: имя, флаг `active`, список `databases[]`.
- Только базы **активных** проектов попадают в MCP (`active_databases` → `project_filter` в остальных tools).
- Один portable-экземпляр config-mcp может обслуживать несколько таких контейнеров; пользователь переключает «что сейчас видит агент в IDE».
- В standalone-режиме проект создаётся вручную в Admin GUI; в managed — материализуется Hub через `apply-registry`.

Исторически проект часто называют по **клиенту** («Трансгаз», «Ромашка»), но в модели это **группа баз с общим переключателем active**, а не обязательно 1:1 с юридическим клиентом Hub.

### 1.2. Насколько часто один `project` = один клиент (1:1)?

- [x] **Часто 1:1, но бывают исключения**

**Исключения:** один клиент → несколько project (prod/dev, архив); один project → несколько клиентов — редко, путает `project_filter`.

### 1.3. Бывают ли осмысленные кейсы «два project на одного клиента»?

**Да** — prod/dev, тяжёлые конфигурации, исторический снимок, разграничение доступа через `active`.

### 1.4. Как вы сегодня называете `project` пользователям?

**GUI:** «Проект». **MCP:** `project_filter` по имени из `active_databases`. Для Hub — mapping в протоколе, без переименования UI.

### 1.5. Готовность к переименованию

- [x] **Alias / документация**, не rename. `clientId` уже в `apply-registry`.

---

## Блок 2. Семантика `database` и выгрузки

### 2.1. Одна запись `database`

- [x] **Одна выгрузка (основная конфа или одно расширение)** → один `*.db`.

### 2.2. Несколько расширений

**Один project → N databases.** `apply-registry` уже поддерживает; Hub R1 builder — только основная.

### 2.3. `sourceKind`

`directory` — стабильно; `archive` — skip до Phase 3+.

### 2.4. Отдельный id выгрузки

Достаточно `infobaseId` + `type` + `sourcePath`; Hub может слать `exportId` observational.

---

## Блок 3. Registry и authoritative IDs

### 3.1. v1.0.2 §10

**Согласовано с Hub:** lifecycle UUID у Hub; config-mcp — materialized view. Client → config-mcp project; Hub `projects` не материализуется.

### 3.2. Гранулярность fragment

Patch на export; batch на Client допустим. Default `patch`.

### 3.3–3.5

См. таблицу терминов и [`integration.md`](../admin-hub/integration.md) § «Согласованный mapping».

---

## Блок 4. Индексация

Hub orchestration: `apply-registry` → `followUpOperations` → `rebuild-index` per id. **P0:** headless `rebuild-index` CLI (`hub-protocol-phase-3`).

---

## Блок 5. Roadmap

P0: `rebuild-index`; P1: status readiness, `gui-bulk-update`. Rename `project` — не планируется.

---

## Блок 6. Таблица терминов

| Термин Hub | Термин config-mcp | Соотношение | Примечание |
|------------|-------------------|-------------|------------|
| **Client** | `projects[]` | **1:1** | `clientId`, `name` для `project_filter` |
| **Infobase** | — | 1:N | → N databases |
| **ConfigurationExport** | `database` | **1:1** | `infobaseId` = export id |
| **ConfigurationTemplate** | `type` + `name` | N:1 | |
| **Hub `projects`** | нет | — | внутреннее |
| **Task** | нет | — | вне scope |

---

## Ответ Hub (2026-06-28) — **OK**

Полный текст: [`registry-mapping-hub-response-2026-06-28.md`](registry-mapping-hub-response-2026-06-28.md).

**P0 `rebuild-index`:** `hub-protocol-phase-3`, статус `ready`; ориентир — следующая рабочая итерация; Hub H6 после CLI в portable.

Операционный канон в репозитории config-mcp: [`integration.md`](../admin-hub/integration.md) § «Согласованный mapping». Канонический addendum — `docs/admin-hub/registry-mapping.md` в репозитории Hub (`1c-admin-tool`).
