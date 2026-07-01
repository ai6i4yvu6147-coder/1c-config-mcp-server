# Unified 1C AI Admin Hub — Protocol v1.0.1 Addendum

## Статус документа

Этот документ является обязательным дополнением к `Unified 1C AI Admin Hub — Consolidated Protocol v1`. Его цель — убрать неоднозначность перед параллельной реализацией в нескольких репозиториях и формализовать те части протокола, которые в v1 были описаны концептуально: JSON schemas, discovery/path rules, delete policy, canonical Hub model, exit codes и runtime modes.[file:169][file:167][file:168]

Если между v1 и этим addendum возникает конфликт, приоритет имеет этот addendum как более формальный и поздний документ уровня v1.0.1.[file:169][file:167][file:168]

## 1. Canonical Hub model

Admin Hub использует единую каноническую модель, от которой вниз материализуются registry fragments отдельных модулей. Это нужно, чтобы `config-mcp`, `help-mcp`, `data-mcp` и `ConfigAdmin` не изобретали собственные несовместимые структуры связей.[file:169][file:167][file:168]

### 1.1. Базовые сущности

```json
{
  "schemaVersion": 1,
  "clients": [
    {
      "clientId": "client-uuid",
      "name": "Client A",
      "comment": null
    }
  ],
  "projects": [
    {
      "projectId": "project-uuid",
      "clientId": "client-uuid",
      "name": "ERP Project",
      "active": true,
      "configMcpProjectId": "project-uuid"
    }
  ],
  "infobases": [
    {
      "infobaseId": "infobase-uuid",
      "clientId": "client-uuid",
      "projectId": "project-uuid",
      "name": "Base ERP",
      "platformVersion": "8.3.27.1688",
      "configKind": "base",
      "defaultHelpVersion": "8.3.27",
      "links": {
        "configMcpProjectId": "project-uuid",
        "configMcpDatabaseId": "infobase-uuid",
        "dataConnectionId": "data-conn-uuid",
        "helpCatalogId": "help-8-3-27"
      }
    }
  ],
  "toolInstances": [
    {
      "toolInstanceId": "tool-uuid",
      "moduleId": "1c-config-mcp",
      "moduleType": "config-mcp",
      "rootPath": "C:/Tools/1c-config-mcpPortable",
      "mode": "managed"
    }
  ]
}
```

### 1.2. Нормативные ID

Во всех модулях обязательны следующие стабильные ID:
- `clientId`
- `projectId`
- `infobaseId`
- `toolInstanceId`
- `moduleId`
- `dataConnectionId`
- `helpCatalogId`
- `operationRunId`[file:169][file:167][file:168]

### 1.3. Общие правила ID

- Все hub-owned IDs должны быть стабильными UUID-подобными строками, а не display names.[file:169][file:167][file:168]
- Upsert запрещено делать только по имени; минимум — по явному ID.[file:169]
- Если модуль исторически использует локальный operational ID, он обязан маппить его на canonical ID, а не подменять canonical ID. Для `data-mcp` это особенно касается `databaseid`, который должен быть привязан к `dataConnectionId` и `infobaseId`.

## 2. Runtime modes

Каждый managed tool должен поддерживать два логических режима:
- `standalone`
- `managed`[file:170]

### 2.1. Manifest mode field

`module.manifest.json` должен содержать поле:

```json
{
  "mode": "standalone"
}
```

Допустимые значения:
- `standalone`: модуль работает без Hub, локальные конфиги являются primary source.[file:170]
- `managed`: модуль работает под Admin Hub, а его syncable config рассматривается как materialized view канонической модели Hub.[file:170]

### 2.2. Поведение режимов

В `standalone`-режиме модуль может продолжать работу со своими текущими GUI/локальными сценариями и не обязан ожидать, что кто-то будет вызывать `apply-registry`. В `managed`-режиме модуль обязан считать `apply-registry` допустимым административным каналом и соблюдать ownership rules.[file:170]

### 2.3. Переход между режимами

Смена `mode` разрешена только явным обновлением manifest или через future admin action, но не должна происходить автоматически при первом обнаружении Hub.[file:170]

## 3. Discovery and path resolution

Manifest является единственным source of truth для обнаружения executable paths, config paths и data paths. Hub не должен выводить их эвристически из имени папки или имени exe.[file:169][file:167][file:168]

### 3.1. Discovery order

Нормативный порядок discovery:

1. Явно переданный root path.
2. Явно переданный manifest path.
3. Скан известных tool roots на наличие `module.manifest.json`.
4. Опционально future registry cache Hub.[file:169][file:167][file:168]

Если manifest не найден, экземпляр не считается discoverable по протоколу v1.0.1.[file:169][file:167][file:168]

### 3.2. Path rules

- Все пути в manifest могут быть относительными к `paths.root` или абсолютными.[file:169][file:167][file:168]
- Hub обязан нормализовать пути до абсолютных перед запуском subprocess.[file:169][file:167][file:168]
- Relative path resolution всегда идёт от `manifest` root, а не от current working directory.[file:169][file:167][file:168]
- CLI команды могут принимать `--root`, `--manifest`, `--data-dir`, но приоритет резолюции должен быть формально определён.[file:169]

### 3.3. Path precedence

Порядок приоритета:
1. explicit CLI argument;
2. environment variable;
3. manifest field;
4. module internal default.[file:169][file:167][file:168]

### 3.4. Environment variables

Разрешены env overrides только если они задокументированы модулем. Минимально допустимые примеры:
- `CONFIGADMINDATADIR` для ConfigAdmin-style dataDir override.
- модульные аналоги для dev/test окружений, если они не ломают manifest contract.[file:169][file:167][file:168]

## 4. Manifest schema

### 4.1. Нормативная схема manifest

```json
{
  "schemaVersion": 1,
  "moduleType": "config-mcp",
  "moduleName": "1C Config MCP",
  "moduleId": "1c-config-mcp",
  "moduleVersion": "1.0.0",
  "mode": "managed",
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
  },
  "registry": {
    "fragmentSchemaVersion": 1,
    "exportCommand": "export-registry",
    "applyCommand": "apply-registry"
  }
}
```

### 4.2. Module-specific optional fields

Допускаются дополнительные поля типа:
- `indexerVersion` для `config-mcp`;
- `registryLocal` / `configAdmin` secondary config path для `help-mcp`;
- `credentialsPath` или equivalent inventory-only field для `data-mcp`;
- `runsDir`, `locksDir` для `ConfigAdmin`.

Но такие поля не должны ломать базовую совместимость manifest.[file:169][file:167][file:168]

## 5. Inventory schema

### 5.1. Нормативная схема inventory result

```json
{
  "moduleId": "1c-config-mcp",
  "moduleType": "config-mcp",
  "moduleVersion": "1.0.0",
  "schemaVersion": 1,
  "mode": "managed",
  "rootPath": "C:/Tools/1c-config-mcpPortable",
  "manifestPath": "C:/Tools/1c-config-mcpPortable/module.manifest.json",
  "configPath": "C:/Tools/1c-config-mcpPortable/projects.json",
  "runtimePath": "C:/Tools/1c-config-mcpPortable/Server/1c-config-server.exe",
  "adminPath": "C:/Tools/1c-config-mcpPortable/Admin/1C-Config-Admin.exe",
  "cliPath": "C:/Tools/1c-config-mcpPortable/Tools/1c-config-cli.exe",
  "dataPaths": [
    "C:/Tools/1c-config-mcpPortable/databases"
  ],
  "statusSupport": true,
  "syncSupport": true,
  "cliSupport": true
}
```

### 5.2. Inventory rules

- Все пути в output должны быть абсолютными.[file:169][file:167][file:168]
- `inventory` не должен выполнять mutating operations.[file:169][file:167][file:168]
- Если `adminExe` отсутствует, поле допускается как `null`. Это особенно актуально для `data-mcp`.

## 6. Status schema

### 6.1. Нормативная схема status result

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

### 6.2. Normative enums

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

### 6.3. Lock entry schema

```json
{
  "type": "build-marker",
  "targetId": "infobase-uuid",
  "path": "C:/Tools/.../databases/base.db.building",
  "startedAt": "2026-06-28T09:58:00Z",
  "pid": 12345,
  "stale": false,
  "reason": "rebuild-index"
}
```

### 6.4. Status rules

- Любая активная mutating операция должна отражаться либо через `readiness=busy`, либо через `locks[]`, либо и тем и другим.[file:169][file:167][file:168]
- `warning + ready` допустимы одновременно, если модуль работоспособен, но есть outdated index, stale lock или secondary degradation.[file:170][file:167][file:168]
- `error + misconfigured` используются для отсутствующих/битых mandatory артефактов.[file:169][file:167][file:168]

## 7. CLI behavior and exit codes

Все CLI команды должны соблюдать единые правила I/O. Это особенно важно, потому что модули реализуются на разных языках и с разными рантаймами.[file:169][file:167][file:168]

### 7.1. CLI output rules

- stdout: только JSON-объект или JSON-массив.[file:169][file:167][file:168]
- stderr: diagnostics, human-readable traces, warnings.[file:169][file:167][file:168]
- Никакого mixed human text в stdout при `--json`.[file:169][file:167][file:168]

### 7.2. Unified exit codes

Нормативная таблица exit codes:

| Code | Meaning |
|---|---|
| 0 | Success[file:169][file:167][file:168] |
| 1 | Validation error: invalid args, schema mismatch, bad input[file:169] |
| 2 | I/O or environment error: unreadable file, missing path, access denied[file:170] |
| 3 | Dependency/runtime error: missing executable, failed subprocess bootstrap, DB backend unavailable[file:169][file:168] |
| 4 | Protocol error: unsupported command/capability, incompatible manifest/schema version[file:170] |
| 409 | Busy/lock conflict: import lock, export lock, config write lock, active build[file:170][file:169][file:168] |
| 500 | Unhandled internal error[file:169][file:167][file:168] |

### 7.3. Exit code rules

- `409` должен использоваться для lock/busy конфликтов, а не маскироваться под generic failure. Это уже явно предложено в `help-mcp` и логически совместимо с остальными модулями.[file:170][file:169][file:168]
- `status --json` желательно возвращать `0`, даже если сам статус=`warning` или `error`, если команда смогла корректно сформировать status payload. Non-zero нужен, только если сам CLI вызов не смог завершиться по протоколу.[file:169][file:167][file:168]

## 8. Registry fragment schemas

### 8.1. Общие правила fragment

Каждый `export-registry --json` должен возвращать:
- `schemaVersion`
- `moduleId`
- `moduleType`
- `exportedAt`
- `registryFragment` или эквивалентный top-level payload[file:169][file:167][file:168]

Обязательное правило: fragment отражает только syncable administrative state, а не весь локальный runtime/internal state.[file:169][file:167][file:168]

### 8.2. Config MCP fragment

```json
{
  "schemaVersion": 1,
  "moduleId": "1c-config-mcp",
  "moduleType": "config-mcp",
  "exportedAt": "2026-06-28T10:00:00Z",
  "registryFragment": {
    "projects": [
      {
        "projectId": "project-uuid",
        "clientId": "client-uuid",
        "name": "ERP Project",
        "active": true,
        "databases": [
          {
            "infobaseId": "infobase-uuid",
            "name": "Base ERP",
            "type": "base",
            "sourceXml": "D:/exports/Configuration.xml",
            "platformVersion": "8.3.27.1688",
            "indexStatus": {
              "userVersion": 10,
              "expectedVersion": 10,
              "isOutdated": false,
              "isBuilding": false
            }
          }
        ]
      }
    ]
  }
}
```

`dbFile`, `.db`, `.tmp`, `.building` и иные runtime-поля не являются Hub-authoritative и не должны записываться Hub обратно как master-owned поля. Они могут присутствовать только как export-only observational metadata.

### 8.3. Help MCP fragment

```json
{
  "schemaVersion": 1,
  "moduleId": "1c-help-mcp",
  "moduleType": "help-mcp",
  "exportedAt": "2026-06-28T10:00:00Z",
  "registryFragment": {
    "defaultVersion": "8.3.27",
    "catalogs": [
      {
        "helpCatalogId": "help-8-3-27",
        "platformVersion": "8.3.27",
        "sourcePath": "D:/1C/8.3.27/bin",
        "hasQueryHelp": true,
        "queryTopicsCount": 118
      }
    ],
    "infobaseBindings": [
      {
        "infobaseId": "infobase-uuid",
        "platformVersion": "8.3.27.1688",
        "resolvedHelpVersion": "8.3.27",
        "helpCatalogId": "help-8-3-27"
      }
    ]
  }
}
```

Физические `.db` файлы, import timestamps и parser internals остаются local-owned.

### 8.4. Data MCP fragment

```json
{
  "schemaVersion": 1,
  "moduleId": "1c-data-mcp",
  "moduleType": "data-mcp",
  "exportedAt": "2026-06-28T10:00:00Z",
  "registryFragment": {
    "yandex": {
      "endpoint": "https://storage.yandexcloud.net",
      "region": "ru-central1",
      "bucket": "1c-mcp-exchange",
      "defaultPrefix": "exchange"
    },
    "connections": [
      {
        "dataConnectionId": "data-conn-uuid",
        "infobaseId": "infobase-uuid",
        "databaseid": "a1b2c3d4",
        "displayName": "Base ERP"
      }
    ]
  }
}
```

`credentials.local.json`, access keys и deployment-specific tuning не являются частью обычного sync fragment v1.0.1.

### 8.5. ConfigAdmin fragment

```json
{
  "schemaVersion": 1,
  "moduleId": "config-admin",
  "moduleType": "config-admin",
  "exportedAt": "2026-06-28T10:00:00Z",
  "registryFragment": {
    "clients": [
      {
        "clientId": "client-uuid",
        "name": "Client A",
        "exportRootPath": "D:/Exports"
      }
    ],
    "infobases": [
      {
        "infobaseId": "infobase-uuid",
        "clientId": "client-uuid",
        "name": "Base ERP",
        "platformPath": "C:/Program Files/1cv8/8.3.24.0/bin/1cv8.exe",
        "connectionType": "server",
        "connectionString": "srv01",
        "username": "Admin",
        "exportConfiguration": true,
        "exportAllExtensions": true,
        "selectedExtensions": [],
        "exportFormat": "hierarchical",
        "links": {
          "configMcpProjectId": "project-uuid",
          "dataConnectionId": "data-conn-uuid",
          "helpCatalogId": "help-8-3-27"
        }
      }
    ],
    "secretsPolicy": "hub-managed-refs"
  }
}
```

Пароли не должны экспортироваться в открытом виде. Допускаются только secret refs или локальные encrypted blobs, если они не трактуются Hub как plain-text secret payload.

## 9. Apply-registry semantics

### 9.1. Общие правила apply

`apply-registry` обязан:
- валидировать schema version;[file:169][file:167][file:168]
- валидировать `moduleId`/`moduleType`;[file:169][file:167][file:168]
- работать атомарно для persistent config updates;[file:169][file:167][file:168]
- возвращать structured result JSON;[file:169][file:167][file:168]
- не запускать тяжёлую побочную операцию, если это не оговорено отдельным флагом.[file:167][file:168][file:170]

### 9.2. Apply result schema

```json
{
  "success": true,
  "appliedAt": "2026-06-28T10:00:00Z",
  "changes": {
    "created": 0,
    "updated": 2,
    "removed": 0,
    "skipped": 1
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

### 9.3. Delete policy

Delete policy фиксируется жёстко, чтобы четыре модуля не реализовали четыре разных трактовки удаления.[file:170]

Нормативные правила:
- По умолчанию `apply-registry` работает как **upsert-only**.[file:169]
- Удаление сущностей допускается только при одном из двух условий:
  1. в payload есть явное поле `removedIds`; или
  2. передан explicit flag `--apply-mode snapshot`.[file:169]
- `--apply-mode patch` является default.[file:169]
- Silent delete по отсутствию сущности в fragment в patch-режиме запрещён.[file:169]

### 9.4. RemovedIds pattern

Рекомендуемый формат:

```json
{
  "registryFragment": {
    "projects": [...],
    "removedIds": {
      "projectIds": ["project-uuid-1"],
      "infobaseIds": ["infobase-uuid-2"]
    }
  }
}
```

Если модуль не поддерживает delete для какой-то сущности, он обязан вернуть `skipped` + warning, а не молча проигнорировать.[file:169][file:167][file:168]

### 9.5. Trigger flags

Тяжёлые действия, связанные с apply, должны включаться только отдельно. Допустимые примеры:
- `--trigger-rebuild` для `config-mcp`;
- `--trigger-import` для `help-mcp` future mode, но не default;
- никакого неявного re-pairing и secret rewrite для `data-mcp`;
- никакого auto-export в `ConfigAdmin` после apply без отдельной команды.

## 10. Secret bridge sketch

Секреты должны быть вынесены из обычного registry sync. Это особенно важно для `data-mcp` и `ConfigAdmin`, где есть реальные учетные данные, локальные vault/credentials и чувствительный operational context.[file:170]

### 10.1. Нормативное правило

Hub canonical model не хранит plain-text секреты в registry fragments.[file:170]

### 10.2. Разрешённый формат

Вместо этого разрешены только secret references:

```json
{
  "passwordRef": "hub-secret://vault/client-a/base-erp/admin-password"
}
```

или module-local encrypted blob, если он явно трактуется как opaque value, а не как Hub-readable secret.

### 10.3. Secret ownership

- `data-mcp`: `credentials.local.json` остаётся local-owned. Hub может управлять лишь ссылками/метаданными для pairing policy, но не содержимым секретов.
- `ConfigAdmin`: пароль может приходить как `passwordRef`; локальный vault сам решает, как резолвить и хранить его в runtime.

## 11. Module-specific apply rules

### 11.1. Config MCP

- Hub владеет проектами и database bindings.
- Локально вычисляемые `dbFile`, `userVersion`, `.building` — не authoritative с точки зрения Hub.
- `apply-registry` должен использовать atomic temp-write + replace для `projects.json`.

### 11.2. Help MCP

- Hub владеет `defaultVersion` и `infobaseBindings`.
- Локальные `.db` каталоги, import output и parser artifacts — local-owned.
- После смены `defaultVersion` допускается `restartRequired=true`.

### 11.3. Data MCP

- Hub владеет mapping `infobaseId <-> dataConnectionId <-> databaseid` и syncable S3 metadata.
- Credentials, access keys, timeouts и polling tuning — local-owned, если не введён отдельный secret/control contract.
- `apply-registry` должен использовать atomic save `config.local.json`.

### 11.4. ConfigAdmin

- Hub владеет client/infobase administrative graph и cross-module links.
- Vault state, run history и locks — local-owned.
- `apply-registry` должен делать upsert по `clientId` и `infobaseId`, а не по display names.

## 12. Implementation directive for agents

Каждый агент, реализующий протокол в репозитории, должен считать v1 + этот addendum обязательным контрактом.[file:169][file:167][file:168]

Минимальный deliverable от агента:
- file/class change plan;
- CLI command matrix;
- JSON examples conforming to this addendum;
- список protocol deviations;
- risk notes по locks, secrets и migration.[file:169][file:167][file:168]

Если агент не может реализовать часть addendum без серьёзной ломки архитектуры, он обязан явно вернуть:
- `Deviation`;
- `Reason`;
- `Impact`;
- `Safe workaround`; 
- `Target version for closure`.[file:169][file:167][file:168]

## 13. Итоговая директива

Начиная с этого addendum, любые новые реализации inventory/status/registry sync должны считаться корректными только если они соответствуют формальным схемам и правилам этого документа. Narrative-описания из v1 недостаточно, если они противоречат данным схемам и нормативным правилам.[file:169][file:167][file:168]
