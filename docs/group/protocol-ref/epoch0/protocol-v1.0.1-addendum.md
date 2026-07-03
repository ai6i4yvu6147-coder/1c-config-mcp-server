# Unified 1C AI Admin Hub — Protocol v1.0.1 Addendum

## Document status

This document is a mandatory addendum to `Unified 1C AI Admin Hub — Consolidated Protocol v1`. Its goal is to remove ambiguity before parallel implementation across multiple repositories and formalize protocol parts described conceptually in v1: JSON schemas, discovery/path rules, delete policy, canonical Hub model, exit codes, and runtime modes.[file:169][file:167][file:168]

On conflict between v1 and this addendum, this addendum takes priority as the more formal and later v1.0.1-level document.[file:169][file:167][file:168]

## 1. Canonical Hub model

Admin Hub uses a single canonical model from which registry fragments of individual modules are materialized downward. This prevents `config-mcp`, `help-mcp`, `data-mcp`, and `ConfigAdmin` from inventing incompatible link structures.[file:169][file:167][file:168]

### 1.1. Base entities

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

### 1.2. Normative IDs

All modules require the following stable IDs:
- `clientId`
- `projectId`
- `infobaseId`
- `toolInstanceId`
- `moduleId`
- `dataConnectionId`
- `helpCatalogId`
- `operationRunId`[file:169][file:167][file:168]

### 1.3. General ID rules

- All hub-owned IDs must be stable UUID-like strings, not display names.[file:169][file:167][file:168]
- Upsert by name alone is forbidden; minimum — explicit ID.[file:169]
- If a module historically uses a local operational ID, it must map it to canonical ID, not replace canonical ID. For `data-mcp` this especially applies to `databaseid`, which must link to `dataConnectionId` and `infobaseId`.

## 2. Runtime modes

Each managed tool must support two logical modes:
- `standalone`
- `managed`[file:170]

### 2.1. Manifest mode field

`module.manifest.json` must contain field:

```json
{
  "mode": "standalone"
}
```

Allowed values:
- `standalone`: module runs without Hub; local configs are primary source.[file:170]
- `managed`: module runs under Admin Hub; syncable config is treated as materialized view of Hub canonical model.[file:170]

### 2.2. Mode behavior

In `standalone` mode the module may continue with current GUI/local scenarios and need not expect `apply-registry` calls. In `managed` mode the module must treat `apply-registry` as a valid admin channel and follow ownership rules.[file:170]

### 2.3. Mode transition

Changing `mode` is allowed only by explicit manifest update or via future admin action, not automatically on first Hub discovery.[file:170]

## 3. Discovery and path resolution

Manifest is the sole source of truth for executable paths, config paths, and data paths. Hub must not infer them heuristically from folder or exe name.[file:169][file:167][file:168]

### 3.1. Discovery order

Normative discovery order:

1. Explicitly passed root path.
2. Explicitly passed manifest path.
3. Scan known tool roots for `module.manifest.json`.
4. Optionally future Hub registry cache.[file:169][file:167][file:168]

If manifest is not found, the instance is not discoverable per protocol v1.0.1.[file:169][file:167][file:168]

### 3.2. Path rules

- All paths in manifest may be relative to `paths.root` or absolute.[file:169][file:167][file:168]
- Hub must normalize paths to absolute before subprocess launch.[file:169][file:167][file:168]
- Relative path resolution always from manifest root, not current working directory.[file:169][file:167][file:168]
- CLI commands may accept `--root`, `--manifest`, `--data-dir`, but resolution priority must be formally defined.[file:169]

### 3.3. Path precedence

Priority order:
1. explicit CLI argument;
2. environment variable;
3. manifest field;
4. module internal default.[file:169][file:167][file:168]

### 3.4. Environment variables

Env overrides allowed only if documented by module. Minimum acceptable examples:
- `CONFIGADMINDATADIR` for ConfigAdmin-style dataDir override.
- Module analogs for dev/test environments if they do not break manifest contract.[file:169][file:167][file:168]

## 4. Manifest schema

### 4.1. Normative manifest schema

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

Additional fields allowed such as:
- `indexerVersion` for `config-mcp`;
- `registryLocal` / `configAdmin` secondary config path for `help-mcp`;
- `credentialsPath` or equivalent inventory-only field for `data-mcp`;
- `runsDir`, `locksDir` for `ConfigAdmin`.

Such fields must not break base manifest compatibility.[file:169][file:167][file:168]

## 5. Inventory schema

### 5.1. Normative inventory result schema

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

- All paths in output must be absolute.[file:169][file:167][file:168]
- `inventory` must not perform mutating operations.[file:169][file:167][file:168]
- If `adminExe` is absent, field may be `null`. Especially relevant for `data-mcp`.

## 6. Status schema

### 6.1. Normative status result schema

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

- Any active mutating operation must be reflected via `readiness=busy`, or `locks[]`, or both.[file:169][file:167][file:168]
- `warning + ready` allowed together if module is operational but has outdated index, stale lock, or secondary degradation.[file:170][file:167][file:168]
- `error + misconfigured` used for missing/corrupt mandatory artifacts.[file:169][file:167][file:168]

## 7. CLI behavior and exit codes

All CLI commands must follow unified I/O rules. Especially important because modules are implemented in different languages and runtimes.[file:169][file:167][file:168]

### 7.1. CLI output rules

- stdout: JSON object or JSON array only.[file:169][file:167][file:168]
- stderr: diagnostics, human-readable traces, warnings.[file:169][file:167][file:168]
- No mixed human text in stdout with `--json`.[file:169][file:167][file:168]

### 7.2. Unified exit codes

Normative exit code table:

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

- `409` must be used for lock/busy conflicts, not masked as generic failure. Explicitly proposed in `help-mcp` and logically compatible with other modules.[file:170][file:169][file:168]
- `status --json` should return `0` even when status=`warning` or `error`, if command successfully formed status payload. Non-zero only if CLI invocation itself failed per protocol.[file:169][file:167][file:168]

## 8. Registry fragment schemas

### 8.1. General fragment rules

Each `export-registry --json` must return:
- `schemaVersion`
- `moduleId`
- `moduleType`
- `exportedAt`
- `registryFragment` or equivalent top-level payload[file:169][file:167][file:168]

Required rule: fragment reflects only syncable administrative state, not entire local runtime/internal state.[file:169][file:167][file:168]

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

`dbFile`, `.db`, `.tmp`, `.building`, and other runtime fields are not Hub-authoritative and must not be written back by Hub as master-owned fields. They may appear only as export-only observational metadata.

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

Physical `.db` files, import timestamps, and parser internals remain local-owned.

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

`credentials.local.json`, access keys, and deployment-specific tuning are not part of ordinary sync fragment v1.0.1.

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

Passwords must not be exported in plain text. Only secret refs or local encrypted blobs allowed if not treated by Hub as plain-text secret payload.

## 9. Apply-registry semantics

### 9.1. General apply rules

`apply-registry` must:
- validate schema version;[file:169][file:167][file:168]
- validate `moduleId`/`moduleType`;[file:169][file:167][file:168]
- work atomically for persistent config updates;[file:169][file:167][file:168]
- return structured result JSON;[file:169][file:167][file:168]
- not launch heavy side operations unless explicitly flagged.[file:167][file:168][file:170]

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

Delete policy is fixed so four modules do not implement four different deletion interpretations.[file:170]

Normative rules:
- By default `apply-registry` works as **upsert-only**.[file:169]
- Entity deletion allowed only if:
  1. payload has explicit `removedIds`; or
  2. explicit flag `--apply-mode snapshot` passed.[file:169]
- `--apply-mode patch` is default.[file:169]
- Silent delete by entity absence in fragment in patch mode is forbidden.[file:169]

### 9.4. RemovedIds pattern

Recommended format:

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

If module does not support delete for an entity, it must return `skipped` + warning, not silently ignore.[file:169][file:167][file:168]

### 9.5. Trigger flags

Heavy apply-related actions must be enabled separately. Allowed examples:
- `--trigger-rebuild` for `config-mcp`;
- `--trigger-import` for `help-mcp` future mode, not default;
- no implicit re-pairing and secret rewrite for `data-mcp`;
- no auto-export in `ConfigAdmin` after apply without separate command.

## 10. Secret bridge sketch

Secrets must be excluded from ordinary registry sync. Especially important for `data-mcp` and `ConfigAdmin` with real credentials, local vault/credentials, and sensitive operational context.[file:170]

### 10.1. Normative rule

Hub canonical model does not store plain-text secrets in registry fragments.[file:170]

### 10.2. Allowed format

Only secret references allowed:

```json
{
  "passwordRef": "hub-secret://vault/client-a/base-erp/admin-password"
}
```

or module-local encrypted blob if explicitly treated as opaque value, not Hub-readable secret.

### 10.3. Secret ownership

- `data-mcp`: `credentials.local.json` remains local-owned. Hub may manage only refs/metadata for pairing policy, not secret contents.
- `ConfigAdmin`: password may arrive as `passwordRef`; local vault resolves and stores it in runtime.

## 11. Module-specific apply rules

### 11.1. Config MCP

- Hub owns projects and database bindings.
- Locally computed `dbFile`, `userVersion`, `.building` — not authoritative from Hub perspective.
- `apply-registry` must use atomic temp-write + replace for `projects.json`.

### 11.2. Help MCP

- Hub owns `defaultVersion` and `infobaseBindings`.
- Local `.db` catalogs, import output, parser artifacts — local-owned.
- After `defaultVersion` change `restartRequired=true` allowed.

### 11.3. Data MCP

- Hub owns mapping `infobaseId <-> dataConnectionId <-> databaseid` and syncable S3 metadata.
- Credentials, access keys, timeouts, polling tuning — local-owned unless separate secret/control contract introduced.
- `apply-registry` must use atomic save of `config.local.json`.

### 11.4. ConfigAdmin

- Hub owns client/infobase administrative graph and cross-module links.
- Vault state, run history, locks — local-owned.
- `apply-registry` must upsert by `clientId` and `infobaseId`, not display names.

## 12. Implementation directive for agents

Each agent implementing the protocol in a repository must treat v1 + this addendum as mandatory contract.[file:169][file:167][file:168]

Minimum agent deliverable:
- file/class change plan;
- CLI command matrix;
- JSON examples conforming to this addendum;
- list of protocol deviations;
- risk notes on locks, secrets, migration.[file:169][file:167][file:168]

If agent cannot implement part of addendum without serious architecture break, must explicitly return:
- `Deviation`;
- `Reason`;
- `Impact`;
- `Safe workaround`; 
- `Target version for closure`.[file:169][file:167][file:168]

## 13. Final directive

From this addendum, any new inventory/status/registry sync implementations are correct only if they conform to formal schemas and rules in this document. Narrative descriptions from v1 are insufficient if they contradict these schemas and normative rules.[file:169][file:167][file:168]
