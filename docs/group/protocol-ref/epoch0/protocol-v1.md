# Unified 1C AI Admin Hub — Consolidated Protocol v1

## Статус документа

Этот документ — согласованная спецификация v1 для унификации инструментов экосистемы 1С AI tooling в единую административную модель. Он собран на основе ответов по `1c-config-mcp`, `1c-help-mcp`, `1c-data-mcp` и `ConfigAdmin` и фиксирует общий контракт, который должен считаться целевым для реализации.[file:167][file:168][file:170]

Документ предназначен для агентов, которые будут внедрять унификацию в конкретные репозитории. Он описывает только целевой протокол и не дублирует исследовательские рассуждения.[file:167][file:168][file:170]

## 1. Архитектурная модель

### 1.1. Базовая схема

Система строится по модели **Admin Hub + Managed Tools**. `Admin Hub` выступает как control plane и владеет общей административной моделью, а каждый инструмент остаётся автономным managed module со своей внутренней логикой, runtime и доменными данными.[file:169][file:167][file:168]

### 1.2. Роли

**Admin Hub** отвечает за:
- master registry клиентов, проектов, инфобаз и связей;
- inventory модулей;
- status aggregation и health view;
- config sync вниз в модули;
- orchestration headless-операций;
- единый журнал административных действий.[file:169][file:167][file:168]

**Managed Tool** отвечает за:
- собственный runtime и доменную логику;
- локальные данные и технические артефакты;
- реализацию manifest/inventory/status/CLI/sync contract;
- безопасное выполнение своих headless-операций.[file:169][file:167][file:168]

### 1.3. Принцип внедрения

Применяется принцип **minimum invasive unification**: переиспользование существующего core, thin CLI/adapters, сохранение portable layout и отказ от big bang rewrite. GUI не должен становиться центром интеграции.[file:169][file:167][file:168]

## 2. Обязательный контракт модуля

Каждый managed tool обязан поддерживать 5 обязательных компонентов:

1. `module.manifest.json`
2. `inventory --json`
3. `status --json`
4. `export-registry --json`
5. `apply-registry --input <file> --json`[file:169][file:167][file:168]

Дополнительно модуль должен поддерживать:
- structured exit codes;
- JSON stdout и diagnostics в stderr;
- readiness/locks model;
- append-only operations log или эквивалентную structured telemetry.[file:169][file:167][file:168]

## 3. Module manifest

Каждый managed tool должен содержать файл `module.manifest.json` в корне portable instance или в root-discoverable location, указываемой через packaging contract. Manifest является source of truth для обнаружения модуля и не должен угадываться по путям.[file:169][file:167][file:168]

### 3.1. Обязательная схема manifest

```json
{
  "schemaVersion": 1,
  "moduleType": "config-mcp",
  "moduleName": "1C Config MCP",
  "moduleId": "1c-config-mcp",
  "moduleVersion": "1.0.0",
  "runtime": {
    "kind": "python-exe",
    "entryExe": "Server/1c-config-server.exe",
    "adminExe": "Admin/1C-Config-Admin.exe",
    "cliExe": "Tools/1c-config-cli.exe"
  },
  "paths": {
    "root": ".",
    "config": "projects.json",
    "dataDir": "databases",
    "logsDir": "logs",
    "operationsLog": "logs/operations.log"
  },
  "capabilities": {
    "inventory": true,
    "status": true,
    "configSync": true,
    "headlessOps": true,
    "healthCheck": true
  }
}
```

### 3.2. Обязательные поля

- `schemaVersion`: версия схемы manifest.[file:169][file:167][file:168]
- `moduleType`: тип модуля (`config-mcp`, `help-mcp`, `data-mcp`, `config-admin`).[file:169][file:167][file:168]
- `moduleId`: стабильный машинный ID.[file:169][file:167][file:168]
- `moduleVersion`: версия релиза модуля.[file:169][file:167][file:168]
- `runtime.*`: реальные entrypoints runtime/admin/CLI.[file:169][file:167][file:168]
- `paths.*`: пути к конфигу, данным, логам и журналу операций.[file:169][file:167][file:168]
- `capabilities.*`: наличие функций контракта.[file:169][file:167][file:168]

### 3.3. Правило по путям

Admin Hub не должен хардкодить расположение CLI, runtime или data folders. Все пути должны резолвиться через manifest. Это специально важно, потому что в ответах по модулям CLI предлагался в разных местах: `Tools`, `Server` или reuse основного exe.[file:169][file:167][file:168]

## 4. Inventory contract

Каждый модуль должен поддерживать команду:

```bash
<cli> inventory --json
```

### 4.1. Минимальный inventory output

```json
{
  "moduleId": "1c-config-mcp",
  "moduleType": "config-mcp",
  "moduleVersion": "1.0.0",
  "rootPath": "C:/Tools/1c-config-mcpPortable",
  "manifestPath": "C:/Tools/1c-config-mcpPortable/module.manifest.json",
  "configPath": "C:/Tools/1c-config-mcpPortable/projects.json",
  "runtimePath": "C:/Tools/1c-config-mcpPortable/Server/1c-config-server.exe",
  "adminPath": "C:/Tools/1c-config-mcpPortable/Admin/1C-Config-Admin.exe",
  "cliPath": "C:/Tools/1c-config-mcpPortable/Tools/1c-config-cli.exe",
  "dataPaths": ["C:/Tools/1c-config-mcpPortable/databases"],
  "statusSupport": true,
  "syncSupport": true,
  "cliSupport": true
}
```

### 4.2. Назначение inventory

Inventory нужен для auto-discovery, привязки tool instance к hub, отображения путей и проверки того, что модуль совместим с унифицированным протоколом.[file:169][file:167][file:168]

## 5. Status and readiness contract

Каждый модуль должен поддерживать команду:

```bash
<cli> status --json
```

### 5.1. Минимальный формат status

```json
{
  "moduleId": "1c-config-mcp",
  "status": "ok",
  "readiness": "ready",
  "timestamp": "2026-06-28T10:00:00Z",
  "summary": "1 project, 2 databases, 0 active locks",
  "details": {
    "configReadable": true,
    "runtimeExists": true,
    "adminExists": true,
    "cliExists": true,
    "dataStoreReachable": true
  },
  "warnings": [],
  "errors": [],
  "locks": []
}
```

### 5.2. Стандартизованные значения

`status`:
- `ok`
- `warning`
- `error`[file:169][file:167][file:168]

`readiness`:
- `ready`
- `degraded`
- `busy`
- `offline`
- `misconfigured`[file:169][file:167][file:168]

### 5.3. Обязательное содержание status

Status обязан отражать:
- читаемость конфигов и manifest;[file:169][file:167][file:168]
- существование runtime/admin/CLI paths;[file:169][file:167][file:168]
- доступность локального data store или exchange backend;[file:169][file:167][file:168]
- состояние lock/build/import markers;[file:169][file:167][file:168]
- критичные version mismatches;[file:169][file:167][file:168]
- причину degraded/busy/misconfigured состояния.[file:169][file:167][file:168]

### 5.4. Примеры интерпретации

- `ready`: модуль читаем, пути существуют, активной блокировки нет.[file:169][file:167][file:168]
- `busy`: идёт rebuild/import/export/apply-registry, присутствует активный lock marker.[file:169][file:167][file:168]
- `degraded`: модуль работает, но есть stale markers, outdated index, locked vault или отсутствуют вторичные артефакты.[file:169][file:167][file:168]
- `misconfigured`: отсутствует обязательный config/manifest/runtime path или конфигурация невалидна.[file:169][file:167][file:168]
- `offline`: instance/path недоступен физически.[file:169][file:167][file:168]

## 6. Registry sync contract

Admin Hub является master source of truth для общей административной модели. Каждый managed tool получает только свой materialized fragment и экспортирует только свой локально релевантный snapshot.[file:169][file:167][file:168]

### 6.1. Обязательные команды

```bash
<cli> export-registry --json
<cli> apply-registry --input registry.json --json
```

### 6.2. Общие требования

`export-registry` должен:
- возвращать machine-readable JSON snapshot;[file:169][file:167][file:168]
- включать только sync-relevant сущности и поля;[file:169][file:167][file:168]
- не смешивать master-owned и purely local runtime state без явной маркировки.[file:169][file:167][file:168]

`apply-registry` должен:
- принимать JSON fragment или snapshot;[file:169][file:167][file:168]
- валидировать schema version;[file:169][file:167][file:168]
- работать атомарно при изменении persistent config;[file:169][file:167][file:168]
- возвращать structured diff/result;[file:169][file:167][file:168]
- не запускать тяжёлые операции по умолчанию, если это не запросили явно.[file:169][file:167][file:168]

### 6.3. Формат результата apply-registry

```json
{
  "success": true,
  "appliedAt": "2026-06-28T10:00:00Z",
  "changes": {
    "created": 1,
    "updated": 2,
    "removed": 0,
    "skipped": 3
  },
  "warnings": [],
  "errors": [],
  "postApplyActions": {
    "restartRequired": false,
    "reloadRequired": true,
    "followUpOperations": []
  }
}
```

### 6.4. Post-apply semantics

Итоговая v1-спецификация вводит обязательный блок `postApplyActions`, потому что отдельные модули могут требовать restart/reload/config rebind после sync. Это следует из ответов по `help-mcp` и `config-mcp`, где изменение конфигов влияет на runtime behaviour.[file:169]

## 7. Ownership matrix

Итоговый протокол v1 явно фиксирует разделение **master-owned** и **local-owned** полей. Это обязательно, чтобы не сломать модули чрезмерной централизацией.[file:169][file:167][file:168]

### 7.1. Master-owned поля

Эти поля должны управляться из Admin Hub и материализоваться в managed tools:
- `clientId`, `projectId`, `infobaseId`;[file:169][file:167][file:168]
- display names и человекочитаемые названия сущностей;[file:169][file:167][file:168]
- связи между инфобазой и config/help/data/export tool;[file:169][file:167][file:168]
- `databaseid` как логическая связка data-MCP с инфобазой;
- `defaultVersion` и version bindings для help-MCP;
- source XML path и activation metadata для config-MCP;
- export profile linkage и cross-module links для ConfigAdmin.

### 7.2. Local-owned поля

Эти поля остаются под управлением managed tool и не должны быть authoritative в Hub:
- runtime locks, `.building`, `.tmp`, import locks, export locks;[file:169][file:167][file:168]
- SQLite `userversion`, FTS/index internals, parser output, run history;[file:169][file:167][file:168]
- `dbfile`, derived file names, operational temp paths;
- `meta.created`, import timestamps, help DB physical artifacts;
- `credentials.local.json`, local credentials and deployment-specific tuning in data-MCP;
- vault runtime state, encrypted secrets blobs, per-machine platform paths and run artifacts in ConfigAdmin.

### 7.3. Секреты

Секреты не должны быть частью обычного registry sync v1. Для `data-mcp` credentials остаются локальными, а для `ConfigAdmin` парольная информация и vault state тоже остаются локальными или идут через отдельный secret bridge/pointer model, но не через обычный fragment payload.[file:170]

## 8. Headless CLI contract

Все административные операции должны вызываться через thin CLI facade поверх существующего core. Вызов GUI как интеграционного механизма считается недопустимым для v1, кроме ручного fallback.[file:169][file:167][file:168]

### 8.1. Общие правила CLI

- stdout: только machine-readable JSON.[file:169][file:167][file:168]
- stderr: diagnostics/log hints.[file:169][file:167][file:168]
- exit code `0`: только успешная операция.[file:169][file:167][file:168]
- модуль должен поддерживать headless-вызов из subprocess.[file:169][file:167][file:168]
- read-only и mutating operations должны быть различимы явно.[file:169][file:167][file:168]

### 8.2. Обязательные команды для всех

```bash
<cli> inventory --json
<cli> status --json
<cli> export-registry --json
<cli> apply-registry --input registry.json --json
```

### 8.3. Обязательные команды по типам модулей

#### config-mcp

```bash
<cli> rebuild-index --db-id <infobaseId> --json
<cli> rebuild-all --json
<cli> reconcile-markers --json
```

#### help-mcp

```bash
<cli> list-help-dbs --json
<cli> import-help --source <path> --version <ver> --json
<cli> set-default-version --version <ver> --json
```

#### data-mcp

```bash
<cli> validate-config --json
<cli> ping --database-id <id> --json
<cli> print-config --json
```

#### config-admin

```bash
<cli> list-bases --json
<cli> list-runs --json
<cli> test-connection --base <id> --json
<cli> export --base <id> --json
```

## 9. Unified identifiers

Во всей системе должна использоваться единая логическая модель идентификаторов. Это прямо следует из ответов, где каждый модуль уже имеет свои ID или просит их стабилизировать.[file:169][file:167][file:168]

### 9.1. Рекомендуемый набор IDs

- `clientId`
- `projectId`
- `infobaseId`
- `moduleId`
- `toolInstanceId`
- `dataConnectionId`
- `helpCatalogId`
- `operationRunId`[file:169][file:167][file:168]

### 9.2. Mapping rules

- `config-mcp`: `project.id` и `database.id` должны маппиться на `projectId` и `infobaseId`.
- `help-mcp`: help catalog должен иметь стабильный `helpCatalogId`, а binding должен привязываться к platform version или infobase binding.
- `data-mcp`: `databaseid` остаётся operational pairing ID, но должен быть привязан к `dataConnectionId` и `infobaseId`.
- `ConfigAdmin`: `ClientProfile.Id` и `InfobaseProfile.Id` должны использоваться как master-compatible IDs либо иметь стабильный mapping.

## 10. Locking and concurrency contract

Так как все модули работают с файлами, SQLite, import/export и временными артефактами, v1 вводит обязательную модель reporting по locks и busy state.[file:169][file:167][file:168]

### 10.1. Общие правила

- Любая mutating операция должна отражаться в `status` как `busy` или через lock marker.[file:169][file:167][file:168]
- Если модуль уже использует file/DB markers, они должны быть включены в status output.[file:169][file:167][file:168]
- stale markers должны детектироваться и явно помечаться.[file:169][file:167][file:168]
- Admin Hub не должен напрямую редактировать внутренние lock/temp файлы модулей.[file:169][file:167][file:168]

### 10.2. Формат lock entry

```json
{
  "type": "build-marker",
  "targetId": "infobase-123",
  "path": "databases/mydb.db.building",
  "startedAt": "2026-06-28T09:58:00Z",
  "pid": 12345,
  "stale": false,
  "reason": "rebuild-index"
}
```

### 10.3. Специфика по модулям

- `config-mcp`: `.building`, `.tmp`, single-writer policy для `projects.json`, outdated index state.
- `help-mcp`: import lock, SQLite write/read race, `defaultVersion` sync и import activity.
- `data-mcp`: config write races, S3 reachability degradation, потенциальный config-write lock для `apply-registry`.
- `ConfigAdmin`: export lock, registry lock, vault locked state, SQLite concurrent access.

## 11. Operations log contract

Каждый модуль должен вести append-only operations log или функционально эквивалентный structured audit trail.[file:169][file:167][file:168]

### 11.1. Минимальный формат записи

```json
{
  "timestamp": "2026-06-28T10:00:00Z",
  "operation": "rebuild-index",
  "targetId": "infobase-123",
  "operationRunId": "run-uuid",
  "result": "success",
  "message": "Index rebuilt",
  "durationMs": 4200
}
```

### 11.2. Назначение

Operations log нужен для:
- event feed в Admin Hub;[file:169][file:167][file:168]
- аудита автоматизированных действий;[file:169][file:167][file:168]
- анализа неудачных rebuild/import/export/ping/apply;[file:169][file:167][file:168]
- склейки истории по infobase и module instance.[file:169][file:167][file:168]

## 12. ConfigAdmin as host shell

Согласованная позиция v1: `ConfigAdmin` является лучшим кандидатом на роль host shell / primary Admin Hub foundation, но не должен поглощать внутреннюю доменную логику остальных MCP. Он должен развиваться как orchestration/UI/master-registry слой над managed tools.[file:169][file:167][file:168]

Это означает:
- ConfigAdmin расширяется до master registry и tool orchestration;
- MCP-модули остаются отдельными managed instances;[file:167][file:168]
- интеграция идёт через manifest + CLI + status + registry sync, а не через big merge codebase.[file:169][file:167][file:168]

## 13. Module-specific v1 requirements

### 13.1. 1C Config MCP

Обязательные доработки v1:
- `module.manifest.json`;
- thin CLI facade;
- `inventory --json`;
- `status --json` с `projects.json`, `.db`, `.building`, `INDEXERVERSION`;
- `export-registry` / `apply-registry`;
- `rebuild-index`, `rebuild-all`, `reconcile-markers`;
- operations log.

### 13.2. 1C Help MCP

Обязательные доработки v1:
- `module.manifest.json`;
- CLI entrypoint для list/status/import/default version;
- `inventory --json`;
- `status --json` с `defaultVersion`, catalog inventory, `meta.created`, `sourcePath`, `hasQueryHelp`;
- `export-registry` / `apply-registry`;
- `list-help-dbs`, `import-help`, `set-default-version`;
- import lock и operations log.

### 13.3. 1C Data MCP

Обязательные доработки v1:
- `module.manifest.json`;
- CLI facade;
- `inventory --json`;
- `status --json`;
- `validate-config`, `ping`, `print-config`;
- `export-registry` / `apply-registry` для sync `databaseid` / prefix / bucket metadata;
- local-secret policy и operations log.

### 13.4. ConfigAdmin

Обязательные доработки v1:
- `module.manifest.json`;
- JSON consistency для CLI;
- `inventory --json`;
- `status --json` по DB/runtime/vault/locks;
- `export-registry` / `apply-registry`;
- cross-module links в master model;
- операции `list-bases`, `list-runs`, `test-connection`, `export`;
- host-shell orchestration role.

## 14. Rollout plan v1

### Phase 1 — Discoverability and read-only protocol

Сначала все модули приводятся к discoverable виду:
- manifest;[file:169][file:167][file:168]
- inventory;[file:169][file:167][file:168]
- status;[file:169][file:167][file:168]
- read-only CLI discipline.[file:169][file:167][file:168]

На этом этапе Admin Hub уже может строить unified dashboard состояния среды.[file:169][file:167][file:168]

### Phase 2 — Registry sync

Затем добавляется controlled sync:
- `export-registry`;[file:169][file:167][file:168]
- `apply-registry`;[file:169][file:167][file:168]
- ownership matrix enforcement;[file:169][file:167][file:168]
- atomic writes и post-apply actions.[file:169][file:167][file:168]

### Phase 3 — Headless operations orchestration

Только после этого включаются module-specific control-plane operations:
- rebuild/import/ping/export/test-connection;[file:169][file:167][file:168]
- operations log aggregation;[file:169][file:167][file:168]
- cross-tool workflows в ConfigAdmin/Hub.[file:169][file:167][file:168]

## 15. Требование к реализации в репозиториях

Каждый агент, внедряющий v1 в конкретный модуль, должен:
- реализовать manifest и CLI без разрушения текущего runtime;[file:169][file:167][file:168]
- переиспользовать существующий core/service layer;[file:169][file:167][file:168]
- не переносить GUI-логику в интеграционный слой;[file:169][file:167][file:168]
- обеспечить JSON protocol compatibility;[file:169][file:167][file:168]
- явно зафиксировать master-owned и local-owned поля;[file:169][file:167][file:168]
- описать file/db races и status-модель для своего модуля.[file:169][file:167][file:168]

## 16. Итоговая директива

Этот документ считается базовой спецификацией v1 для унификации. Если в конкретном репозитории требуется отклонение от протокола, агент обязан описать его явно как `protocol deviation`, указать причину, влияние на Admin Hub и безопасный workaround.[file:169][file:167][file:168]

До появления спецификации v2 любые расширения должны быть обратно совместимы с v1-contract: manifest, inventory, status, registry sync, locks и structured CLI.[file:169][file:167][file:168]
