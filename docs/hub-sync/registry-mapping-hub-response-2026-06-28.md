# Ответ ConfigAdmin / Admin Hub на согласование registry с 1c-config-mcp

**Дата:** 2026-06-28  
**От:** ConfigAdmin / Admin Hub (`1c-admin-tool`)  
**В ответ на:** [`registry-mapping-config-mcp-response-2026-06-28.md`](registry-mapping-config-mcp-response-2026-06-28.md)  
**Статус:** **согласовано** (config-mcp OK 2026-06-28; канонический addendum — в репозитории Hub: `docs/admin-hub/registry-mapping.md`)

---

## Резюме (один абзац)

**Подтверждаем:** config-mcp `project` — operational-контейнер, **целевой mapping 1:1 с Hub Client** (`clientId` в fragment); config-mcp `database` — **одна выгрузка** (base или extension), не «база 1С целиком». **Переименование `project` в config-mcp не планируем и не просим.** Hub `projects` (SQLite, v1.0.2 §10) **не материализуется** в `projects.json`. В fragment поле `infobaseId` — **id записи выгрузки в registry MCP** (у нас `ConfigurationExport.id`), не id строки подключения к инфобазе 1С. R1 (ручной линк, один database на sync) — переходный; целевой fragment — **один project на Client, N databases**, patch после каждого export. Полный E2E с rebuild — после вашего P0 `rebuild-index` CLI; multi-database fragment Hub начинает параллельно.

---

## Ответы на вопросы из § «Вопросы к Hub»

### 1. Hub `project` vs config-mcp `project`

**Решение Hub:**

| Сущность | Роль |
|----------|------|
| **Hub `Client`** | Canonical владелец клиента; **материализуется** в config-mcp как один элемент `projects[]` (целевое **1:1**) |
| **config-mcp `project`** | Operational: индексы, `active`, `project_filter` в MCP; имя `name` — для людей и фильтра |
| **Hub `projects` (SQLite)** | **Внутренняя** сущность Hub; **не** имеет обязательного аналога в `projects.json` |

**Исключение (согласны с вашими кейсами):** у одного Hub Client может быть **2 config-mcp project** (prod/dev, архив, изоляция). Это **явный продуктовый режим**, не дефолт. В данных Hub — отдельная связь «MCP-контейнер», не путать с Hub `projects`.

**v1.0.2 §10:** canonical lifecycle UUID по-прежнему у Hub; config-mcp — materialized view / upsert по `projectId` + `clientId`.

---

### 2. `projectId` в fragment — source of truth

**Решение Hub:**

| Поле | Где хранится (целевая модель) | В fragment |
|------|-------------------------------|------------|
| `clientId` | `clients.id` | обязательно |
| `projectId` | **`clients.config_mcp_project_id`** (новое поле; перенос с уровня infobase) | обязательно; **отдельный UUID**, не обязан совпадать с `clientId` |
| `infobases.config_mcp_project_id` | **deprecated** (R1) | убираем из целевого UX |

**Правила:**

1. При **первом** sync клиента с config-mcp Hub генерирует стабильный `projectId`, сохраняет на **Client**, далее не меняет.
2. **Ручной линк «инфобаза → MCP project»** — только для исключений (второй MCP-контейнер); в дефолтном потоке **auto-sync без ручного шага**.
3. Если в portable уже есть project с тем же `clientId` — reconcile по `clientId`, не создавать дубликат.

**R1 сейчас:** `projectId` на infobase + экран привязки — **временно**; поведение fragment 1:1:1 не считаем целевым.

---

### 3. Идентификатор расширения / `infobaseId` в fragment

**Согласны: отдельный id на каждый export (основная + каждое расширение).**

Уточнение терминов (важно для протокола):

| В Hub (наша модель) | В fragment config-mcp | Смысл |
|---------------------|----------------------|--------|
| `Infobase` | *нет отдельной сущности* | Подключение к базе 1С (одна строка в Hub) |
| `ConfigurationExport` | `databases[]`, поле **`infobaseId`** | Один индексируемый артефакт (base/extension) |

**Именование в протоколе:** поле `infobaseId` в fragment config-mcp **оставляем** (совместимость), семантика в addendum:

> `infobaseId` = **database registry id** = id выгрузки в Hub (`ConfigurationExport.id`).  
> Не путать с `Infobase.id` (подключение к базе 1С).

Связь: `ConfigurationExport` ссылается на `Infobase.id` + `ConfigurationTemplate` / instance; в MCP уходит только export id.

**Rebuild:** один `rebuild-index` на один такой id (как в вашем §4.1).

---

### 4. Rename `project` → `client` в config-mcp

**Подтверждаем вашу позицию:**

- **Не планируем** и **не ставим в backlog** breaking rename `projects` / `project` / `projects.json` на вашей стороне.
- В Hub design note и UI: не называем это «проектом разработки»; допустимые подписи: **«MCP-контейнер»**, **«Индекс config-mcp (клиент)»**.
- Mapping: **Hub Client ↔ config-mcp project** — в протокольном addendum текстом, без смены ключей JSON.

Опциональный alias `workspaceId` в будущем — только если вы предложите; Hub не блокер.

---

### 5. Phase 3 и параллельная работа

**Согласны с разделением:**

| Работа | Владелец | Когда |
|--------|----------|--------|
| `rebuild-index` / `rebuild-all` CLI | config-mcp **P0** | блокирует полный E2E Remote Sync → index |
| Orchestration: `followUpOperations` → вызов rebuild | Hub Phase 3 | после готовности CLI |
| Multi-database fragment (Client + N databases) | Hub | **начинаем без ожидания** rebuild CLI |
| `apply-registry` patch после export | Hub | вместе с multi-database |
| Очередь rebuild, 1–2 concurrent | Hub | по вашим рекомендациям §4.4 |

Hub **не** будет ждать rebuild CLI, чтобы менять `ConfigMcpFragmentBuilder` под N databases.

---

## Таблица терминов — **OK** (блок 6 ваших ответов)

Принимаем таблицу **без изменений**. Дополнение Hub:

| Термин Hub | Уточнение Hub |
|------------|----------------|
| `ConfigurationExport` | Source of truth для `infobaseId` в fragment |
| `Task` | Только Hub / meta-MCP; вне config-mcp |
| Hub `projects` | Legacy / внутреннее; не показываем в UI как рабочую сущность |

---

## Обязательные поля fragment — согласны

Ваш список §3.4 принимаем:

- **Обязательно:** `projectId`, `clientId`, `infobaseId`, `name`, `sourcePath` + `sourceKind`, `type` при create.
- **Рекомендуемо:** `active`, `platformVersion`.
- **Observational:** `indexStatus`, `contentHash` (если Hub пришлёт) — не master для apply.

`sourceKind: directory` — канон; `archive` Hub не шлёт до явной поддержки.

---

## Обязательства Hub (backlog)

| # | Задача | Фаза | Зависимость |
|---|--------|------|-------------|
| H1 | `config_mcp_project_id` на **Client**, auto-assign при первом sync | Hub registry R2 | схема SQLite (NO_DB_MIGRATIONS: новые поля / новая БД) |
| H2 | `ConfigMcpFragmentBuilder`: 1 project (Client) + N `databases[]` | Hub registry R2 | multi-export paths |
| H3 | Export pipeline: отдельный export + registry id на base и каждое extension | Hub export R2 | — |
| H4 | Deprecate ручной линк infobase→project (оставить для 2-container exception) | UI | H1 |
| H5 | Addendum / `registry-mapping` в `docs/admin-hub/` | docs | этот документ |
| H6 | Orchestration `rebuild-index` по `followUpOperations` | Hub Phase 3 | ваш P0 CLI |
| H7 | UI: переименовать «MCP Project» → «MCP-контейнер» / привязка к клиенту | UI | — |

**Не делаем:** rename в config-mcp; не требуем от вас SQLite migrations.

---

## Ссылки

| Документ | Путь (config-mcp) |
|----------|-------------------|
| Ответы config-mcp | [`registry-mapping-config-mcp-response-2026-06-28.md`](registry-mapping-config-mcp-response-2026-06-28.md) |
| Интеграция | [`docs/admin-hub/integration.md`](../admin-hub/integration.md) |
| Протокол §10 | [`docs/admin-hub/protocol-v1.0.2-addendum.md`](../admin-hub/protocol-v1.0.2-addendum.md) |

**Канонический addendum (владелец Hub):** `docs/admin-hub/registry-mapping.md` в репозитории `1c-admin-tool`.
