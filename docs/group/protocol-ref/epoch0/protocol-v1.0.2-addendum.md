# Unified 1C AI Admin Hub — Protocol v1.0.2 Addendum

## Статус документа

Этот документ является дополнением к `Unified 1C AI Admin Hub — Consolidated Protocol v1` и `Protocol v1.0.1 Addendum`. Версия 1.0.2 закрывает оставшиеся архитектурные и operational gaps, необходимые для уверенной реализации `Phase 2` и подготовки к `Phase 3`: Hub persistence и reconcile, строгие правила идентификаторов, scoping для `platformPath`, семантику `sourcePath`, schema для `followUpOperations`, а также retention policy для orphaned данных.[file:169][file:167][file:168]

Если между v1/v1.0.1 и этим документом возникает конфликт, приоритет имеет v1.0.2 как более поздняя нормативная версия.[file:169][file:167][file:168]

## 1. Admin Hub implementation

В этой системе `Admin Hub` реализован через **ConfigAdmin**. Canonical Hub model физически хранится в SQLite-базе `configadmin.db`, а ConfigAdmin выступает одновременно как:
- canonical registry storage;
- orchestration layer;
- UI host shell;
- control plane для managed tools.

Это означает, что отдельный `hub.db` или отдельный внешний Hub-компонент в протоколе v1.x не вводится. Все canonical сущности и связи должны персиститься в storage ConfigAdmin, расширенном под Hub-модель.

## 2. Hub persistence and reconcile

### 2.1. Canonical storage

Canonical Hub model хранится в `configadmin.db` и является authoritative source of truth для:
- `clients`;
- `projects`;
- `infobases`;
- `toolInstances`;
- cross-module links (`configMcpProjectId`, `configMcpDatabaseId`, `dataConnectionId`, `helpCatalogId`).[file:169][file:167][file:168]

### 2.2. Reconcile direction

Нормативное направление sync следующее:

1. **Hub -> tools** через `apply-registry` является основным control-plane каналом.[file:169][file:167][file:168]
2. **Tools -> Hub** через `export-registry` используется для:
   - inventory и inspection;[file:169][file:167][file:168]
   - read-back observational state;[file:169][file:167][file:168]
   - reconcile локально вычисляемых/наблюдаемых полей;[file:169][file:167][file:168]
   - drift detection.[file:169][file:167][file:168]

### 2.3. Conflict resolution

При расхождении между canonical Hub model и fragment, экспортированным модулем, действуют следующие правила:

- Для **master-owned** полей authoritative является Hub.[file:169][file:167][file:168]
- Для **local-owned** полей authoritative является managed tool.[file:169][file:167][file:168]
- Для **observational/export-only** полей Hub может хранить их как read-back metadata, но не должен использовать их как основание для silent overwrite master-owned полей.[file:170]

### 2.4. Reconcile modes

В v1.0.2 вводятся два логических reconcile режима:
- `authoritative-apply`: Hub materializes canonical state вниз в managed tool.[file:169][file:167][file:168]
- `observational-reconcile`: Hub читает fragment и обновляет только разрешённые read-back поля (`lastExportAt`, `lastExportStatus`, `indexStatus`, health metadata и т.п.).[file:169][file:167][file:168]

## 3. Identifier rules

### 3.1. Hub-owned IDs

Следующие ID должны быть **strict UUID v4**, lowercase, с дефисами:
- `clientId`
- `projectId`
- `infobaseId`
- `toolInstanceId`
- `dataConnectionId`
- `operationRunId`[file:169][file:168]

Нормативный regex:

```text
^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
```

### 3.2. Domain-specific slugs

Следующие поля могут использовать **domain slug**, а не UUID:
- `helpCatalogId`

Нормативный regex для help catalog slug:

```text
^help-\d+-\d+-\d+$
```

Пример допустимого значения:
- `help-8-3-27`

### 3.3. ID generation rules

- Hub-owned IDs генерируются в ConfigAdmin как в Admin Hub implementation.
- Managed tools не должны самовольно заменять canonical IDs своими локальными ID.[file:169][file:168]
- Локальные operational IDs допускаются только как secondary mapping fields. Для `data-mcp` это относится к `databaseid`, который не заменяет `dataConnectionId` и `infobaseId`.

## 4. `platformVersion` and `platformPath`

### 4.1. Canonical rule

`platformVersion` является canonical Hub field на уровне `infobase`.[file:167]

`platformPath` является **per-infobase operational property**, используемой ConfigAdmin для запуска платформы, экспорта и connection tests.

### 4.2. Ownership rule

- `platformVersion` — master-owned canonical поле Hub.[file:167]
- `platformPath` — ConfigAdmin-owned infobase setting, materialized и используемое в ConfigAdmin.

### 4.3. Scope rule

В рамках v1.0.2 `platformPath` считается свойством конкретной `infobase` в ConfigAdmin storage, а не глобальным путём уровня machine registry. Это отражает реальный сценарий, где разные базы в системе могут использовать разные платформы 1С.

Это поле может экспортироваться ConfigAdmin fragment’ом, но не должно трактоваться как machine-global property для всех tool instances сразу.

## 5. `sourcePath` semantics for configuration exports

### 5.1. Canonical replacement

Поле `sourceXml` из ранних черновиков заменяется на **`sourcePath`** как более точное и общее.[file:170]

### 5.2. Допустимые значения

`sourcePath` может указывать на:
- каталог с иерархической XML-выгрузкой конфигурации;[file:170]
- архивный файл, содержащий выгрузку конфигурации.

### 5.3. Source kind rule

В v1.0.2 вводится обязательное поле:

```json
{
  "sourcePath": "D:/Exports/ClientA/BaseERP/config-export.zip",
  "sourceKind": "archive"
}
```

Допустимые значения `sourceKind`:
- `directory`
- `archive`[file:170]

### 5.4. Processing rule

- Если `sourceKind=directory`, `config-mcp` должен индексировать выгрузку из каталога.
- Если `sourceKind=archive`, `config-mcp` должен использовать архивный input workflow, определённый его реализацией.[file:170]

## 6. ConfigAdmin role and in-process rule

ConfigAdmin выполняет **двойную роль**:
- как managed tool (`inventory/status/export-registry/apply-registry/list-bases/export/...`);
- как concrete Admin Hub implementation.

### 6.1. In-process execution rule

Если Hub orchestration инициирует операцию самого ConfigAdmin, допустимо **in-process** выполнение через внутренние application services ConfigAdmin, без self-subprocess запуска `configadmin.exe`.

### 6.2. External module execution rule

Для всех остальных managed tools (`config-mcp`, `help-mcp`, `data-mcp`) orchestration должна выполняться через manifest-resolved CLI subprocess contract.[file:169][file:167][file:168]

Это правило вводится, чтобы избежать бессмысленного self-subprocess pattern для ConfigAdmin и одновременно сохранить единый headless protocol для внешних модулей.

## 7. `followUpOperations` schema

### 7.1. Назначение

`followUpOperations` используется для того, чтобы `apply-registry` или другая control-plane операция могла вернуть Hub структурированный список рекомендуемых последующих действий. Это особенно важно для `config-mcp` rebuild-сценариев и для последующих orchestration workflows.[file:167][file:170]

### 7.2. Нормативная схема

```json
{
  "moduleId": "1c-config-mcp",
  "command": "rebuild-index",
  "args": {
    "db-id": "2d90d4c4-4f2c-4c57-8d28-83c0c60db117"
  },
  "reason": "sourcePath changed after apply-registry",
  "blocking": false
}
```

### 7.3. Правила

- `moduleId` — module target, к которому относится операция.[file:169][file:167][file:168]
- `command` — CLI-команда, понятная module contract.[file:169][file:167][file:168]
- `args` — flat JSON object с аргументами команды.[file:169][file:167][file:168]
- `reason` — человекочитаемое пояснение причины follow-up.[file:169][file:167][file:168]
- `blocking` — если `true`, Hub должен считать операцию обязательной для приведения состояния в согласованный вид.[file:169][file:167][file:168]

### 7.4. Hub handling

Hub может:
- выполнить `followUpOperations` автоматически по policy;[file:169][file:167][file:168]
- показать их пользователю на подтверждение;[file:169][file:167][file:168]
- отложить их, сохранив как pending admin actions.[file:169][file:167][file:168]

## 8. Stale lock thresholds

В v1.0.2 вводится рекомендованный, но нормативно допустимый уровень stale thresholds по умолчанию. Это нужно, потому что ConfigAdmin export, Help import и Config MCP rebuild могут работать долго, а без порогов Hub не сможет корректно интерпретировать stale markers.[file:169][file:167]

### 8.1. Default thresholds

| Lock reason | Default staleAfterMs |
|---|---:|
| `rebuild-index` | 3600000 |
| `rebuild-all` | 14400000 |
| `import-help` | 14400000 |
| `export` | 14400000 |
| `apply-registry` | 900000 |
| `config-write` | 900000 |

Значения выше означают 1 час для одиночного rebuild и 4 часа для тяжёлых import/export batch операций. Это согласуется с тем, что Help import и ConfigAdmin export уже рассматриваются как потенциально долгие операции.[file:170][file:169]

### 8.2. Lock payload extension

Рекомендуемое расширение lock entry:

```json
{
  "type": "export-lock",
  "targetId": "infobase-uuid",
  "path": "C:/Tools/config-admin/AppData/locks/export.lock",
  "startedAt": "2026-06-28T09:58:00Z",
  "pid": 12345,
  "stale": false,
  "reason": "export",
  "staleAfterMs": 14400000
}
```

## 9. Delete side-effects and retention policy

### 9.1. Logical delete only

`apply-registry` в v1.0.2 выполняет **только логическое изменение** canonical/admin state. Он не должен автоматически удалять физические артефакты, такие как:
- XML/архивы выгрузок;[file:169]
- `.db` индексы config/help;[file:167]
- run history;
- локальные кэши и временные файлы.[file:169][file:167][file:168]

### 9.2. Orphan retention

После логического удаления данные считаются **orphaned**, но сохраняются до отдельной cleanup operation.[file:169]

### 9.3. Cleanup commands

Физическая очистка должна выполняться отдельными командами, например:
- `cleanup-orphans`
- `prune-exports`
- `prune-indexes`
- `cleanup-runs`[file:169]

Конкретный набор команд зависит от модуля, но их semantics должны быть explicit и не должны смешиваться с `apply-registry`.[file:169][file:167][file:168]

## 10. ConfigAdmin and project authority

`project` является **Hub-only canonical entity**.[file:169]

Это означает:
- ConfigAdmin fragment не обязан экспортировать `projects[]` как первичную сущность.
- ConfigAdmin может ссылаться на project через `links.configMcpProjectId` и `projectId`-related fields, если они есть.[file:169]
- authoritative создание и lifecycle `projectId` выполняется в ConfigAdmin как Admin Hub implementation.[file:169]

## 11. JSON Schema deliverables

v1.0.2 вводит требование наличия machine-validatable JSON Schema артефактов как части протокольного пакета. Эти схемы должны существовать как отдельные файлы в пакете спецификации или в репозитории Admin Hub.[file:169][file:167][file:168]

Минимальный набор:
- `schemas/manifest-v1.schema.json`
- `schemas/inventory-v1.schema.json`
- `schemas/status-v1.schema.json`
- `schemas/apply-result-v1.schema.json`
- `schemas/registry-fragment-config-mcp-v1.schema.json`
- `schemas/registry-fragment-help-mcp-v1.schema.json`
- `schemas/registry-fragment-data-mcp-v1.schema.json`
- `schemas/registry-fragment-config-admin-v1.schema.json`[file:169][file:167][file:168]

Содержимое схем в этом документе не встраивается полностью, но их наличие становится нормативным требованием.[file:169][file:167][file:168]

## 12. Environment variable naming

Для ConfigAdmin закрепляется нормативное имя env variable:

```text
CONFIGADMIN_DATA_DIR
```

`CONFIGADMINDATADIR` допускается только как legacy alias на переходный период и должен документироваться как deprecated alias. Это закрывает inconsistency между ранними текстами и делает naming предсказуемым.

## 13. Reference workflow

### 13.1. Export -> Config sync -> Rebuild

Нормативный reference workflow для связки ConfigAdmin и Config MCP:

1. ConfigAdmin выполняет экспорт конфигурации базы.
2. ConfigAdmin обновляет canonical infobase metadata, включая `sourcePath` и `sourceKind`, если это требуется workflow’ем.[file:169]
3. ConfigAdmin materializes fragment для `config-mcp` и вызывает `apply-registry`.[file:169]
4. `config-mcp` обновляет `projects.json` и возвращает `followUpOperations` с `rebuild-index` при необходимости.
5. Hub/ConfigAdmin выполняет `rebuild-index` либо автоматически, либо после подтверждения пользователя.[file:169]

### 13.2. Help binding update

1. Hub обновляет `platformVersion` или `defaultHelpVersion` на уровне `infobase`.
2. ConfigAdmin materializes fragment для `help-mcp` и вызывает `apply-registry`.[file:167]
3. `help-mcp` обновляет config и может вернуть `restartRequired=true` или `followUpOperations` для import/refresh scenario.

### 13.3. Data connection reconcile

1. Hub/ConfigAdmin обновляет `infobaseId <-> dataConnectionId <-> databaseid` mapping или S3 metadata.
2. ConfigAdmin вызывает `apply-registry` для `data-mcp`.[file:168]
3. `data-mcp` применяет `config.local.json` и Hub может выполнить `validate-config` или `ping --database-id ...` как post-apply verification.

## 14. Implementation directive

С этого момента протокол v1.x считается достаточно определённым для:
- немедленной реализации `Phase 1`;
- controlled реализации `Phase 2`;[file:169][file:167][file:168]
- подготовки orchestration сценариев `Phase 3`.[file:169][file:167][file:168]

Каждый агент, реализующий поддержку протокола, должен опираться на:
- v1;
- v1.0.1 addendum;
- этот v1.0.2 addendum.[file:169][file:167][file:168]

Если модуль не может сразу выполнить часть требований v1.0.2, необходимо вернуть explicit `protocol deviation` с планом закрытия.[file:169][file:167][file:168]
