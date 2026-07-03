# Unified 1C AI Admin Hub — Consolidated Protocol v1

## Document status

This document is the agreed v1 specification for unifying 1C AI tooling ecosystem tools into a single administrative model. It is assembled from responses on `1c-config-mcp`, `1c-help-mcp`, `1c-data-mcp`, and `ConfigAdmin` and fixes the common contract that should be considered the target for implementation.[file:167][file:168][file:170]

The document is intended for agents implementing unification in specific repositories. It describes only the target protocol and does not duplicate research reasoning.[file:167][file:168][file:170]

## 1. Architectural model

### 1.1. Base diagram

The system follows **Admin Hub + Managed Tools** model. `Admin Hub` acts as control plane and owns the shared administrative model; each tool remains an autonomous managed module with its own internal logic, runtime, and domain data.[file:169][file:167][file:168]

### 1.2. Roles

**Admin Hub** is responsible for:
- master registry of clients, projects, infobases, and links;
- module inventory;
- status aggregation and health view;
- config sync downward to modules;
- orchestration of headless operations;
- unified administrative action journal.[file:169][file:167][file:168]

**Managed Tool** is responsible for:
- own runtime and domain logic;
- local data and technical artifacts;
- manifest/inventory/status/CLI/sync contract implementation;
- safe execution of its headless operations.[file:169][file:167][file:168]

### 1.3. Implementation principle

**Minimum invasive unification** applies: reuse existing core, thin CLI/adapters, preserve portable layout, reject big bang rewrite. GUI must not become the integration center.[file:169][file:167][file:168]

## 2. Mandatory module contract

Each managed tool must support 5 mandatory components:

1. `module.manifest.json`
2. `inventory --json`
3. `status --json`
4. `export-registry --json`
5. `apply-registry --input <file> --json`[file:169][file:167][file:168]

Additionally each module must support:
- structured exit codes;
- JSON stdout and diagnostics on stderr;
- readiness/locks model;
- append-only operations log or equivalent structured telemetry.[file:169][file:167][file:168]

## 3. Module manifest

Each managed tool must contain `module.manifest.json` at portable instance root or root-discoverable location per packaging contract. Manifest is source of truth for module discovery and must not be guessed from paths.[file:169][file:167][file:168]

### 3.1. Mandatory manifest schema

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

### 3.2. Mandatory fields

- `schemaVersion`: manifest schema version.[file:169][file:167][file:168]
- `moduleType`: module type (`config-mcp`, `help-mcp`, `data-mcp`, `config-admin`).[file:169][file:167][file:168]
- `moduleId`: stable machine ID.[file:169][file:167][file:168]
- `moduleVersion`: module release version.[file:169][file:167][file:168]
- `runtime.*`: actual runtime/admin/CLI entrypoints.[file:169][file:167][file:168]
- `paths.*`: paths to config, data, logs, operations journal.[file:169][file:167][file:168]
- `capabilities.*`: contract feature presence.[file:169][file:167][file:168]

### 3.3. Path rule

Admin Hub must not hardcode CLI, runtime, or data folder locations. All paths resolve via manifest. Especially important because module responses proposed CLI in different places: `Tools`, `Server`, or reuse of main exe.[file:169][file:167][file:168]

## 4. Inventory contract

Each module must support command:

```bash
<cli> inventory --json
```

### 4.1. Minimum inventory output

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

### 4.2. Inventory purpose

Inventory is needed for auto-discovery, binding tool instance to hub, displaying paths, and verifying module compatibility with unified protocol.[file:169][file:167][file:168]

## 5. Status and readiness contract

Each module must support command:

```bash
<cli> status --json
```

### 5.1. Minimum status format

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

### 5.2. Standardized values

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

### 5.3. Mandatory status content

Status must reflect:
- config and manifest readability;[file:169][file:167][file:168]
- existence of runtime/admin/CLI paths;[file:169][file:167][file:168]
- local data store or exchange backend availability;[file:169][file:167][file:168]
- lock/build/import marker state;[file:169][file:167][file:168]
- critical version mismatches;[file:169][file:167][file:168]
- reason for degraded/busy/misconfigured state.[file:169][file:167][file:168]

### 5.4. Interpretation examples

- `ready`: module readable, paths exist, no active lock.[file:169][file:167][file:168]
- `busy`: rebuild/import/export/apply-registry in progress, active lock marker present.[file:169][file:167][file:168]
- `degraded`: module works but has stale markers, outdated index, locked vault, or missing secondary artifacts.[file:169][file:167][file:168]
- `misconfigured`: mandatory config/manifest/runtime path missing or config invalid.[file:169][file:167][file:168]
- `offline`: instance/path physically unavailable.[file:169][file:167][file:168]

## 6. Registry sync contract

Admin Hub is master source of truth for shared administrative model. Each managed tool receives only its materialized fragment and exports only its locally relevant snapshot.[file:169][file:167][file:168]

### 6.1. Mandatory commands

```bash
<cli> export-registry --json
<cli> apply-registry --input registry.json --json
```

### 6.2. General requirements

`export-registry` must:
- return machine-readable JSON snapshot;[file:169][file:167][file:168]
- include only sync-relevant entities and fields;[file:169][file:167][file:168]
- not mix master-owned and purely local runtime state without explicit marking.[file:169][file:167][file:168]

`apply-registry` must:
- accept JSON fragment or snapshot;[file:169][file:167][file:168]
- validate schema version;[file:169][file:167][file:168]
- work atomically when changing persistent config;[file:169][file:167][file:168]
- return structured diff/result;[file:169][file:167][file:168]
- not launch heavy operations by default unless explicitly requested.[file:169][file:167][file:168]

### 6.3. apply-registry result format

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

Final v1 specification introduces mandatory `postApplyActions` block because individual modules may require restart/reload/config rebind after sync. Follows from `help-mcp` and `config-mcp` responses where config changes affect runtime behaviour.[file:169]

## 7. Ownership matrix

Final v1 protocol explicitly fixes **master-owned** and **local-owned** field split. Required to avoid breaking modules through excessive centralization.[file:169][file:167][file:168]

### 7.1. Master-owned fields

These fields are managed from Admin Hub and materialized in managed tools:
- `clientId`, `projectId`, `infobaseId`;[file:169][file:167][file:168]
- display names and human-readable entity titles;[file:169][file:167][file:168]
- links between infobase and config/help/data/export tool;[file:169][file:167][file:168]
- `databaseid` as logical data-MCP pairing with infobase;
- `defaultVersion` and version bindings for help-MCP;
- source XML path and activation metadata for config-MCP;
- export profile linkage and cross-module links for ConfigAdmin.

### 7.2. Local-owned fields

These fields remain under managed tool control and must not be authoritative in Hub:
- runtime locks, `.building`, `.tmp`, import locks, export locks;[file:169][file:167][file:168]
- SQLite `userversion`, FTS/index internals, parser output, run history;[file:169][file:167][file:168]
- `dbfile`, derived file names, operational temp paths;
- `meta.created`, import timestamps, help DB physical artifacts;
- `credentials.local.json`, local credentials and deployment-specific tuning in data-MCP;
- vault runtime state, encrypted secrets blobs, per-machine platform paths and run artifacts in ConfigAdmin.

### 7.3. Secrets

Secrets must not be part of ordinary registry sync v1. For `data-mcp` credentials remain local; for `ConfigAdmin` password info and vault state also remain local or go via separate secret bridge/pointer model, not ordinary fragment payload.[file:170]

## 8. Headless CLI contract

All administrative operations must be invoked via thin CLI facade over existing core. Calling GUI as integration mechanism is unacceptable for v1 except manual fallback.[file:169][file:167][file:168]

### 8.1. General CLI rules

- stdout: machine-readable JSON only.[file:169][file:167][file:168]
- stderr: diagnostics/log hints.[file:169][file:167][file:168]
- exit code `0`: successful operation only.[file:169][file:167][file:168]
- module must support headless subprocess invocation.[file:169][file:167][file:168]
- read-only and mutating operations must be explicitly distinguishable.[file:169][file:167][file:168]

### 8.2. Mandatory commands for all

```bash
<cli> inventory --json
<cli> status --json
<cli> export-registry --json
<cli> apply-registry --input registry.json --json
```

### 8.3. Mandatory commands by module type

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

The system must use a unified logical identifier model. Follows directly from responses where each module already has IDs or requests stabilization.[file:169][file:167][file:168]

### 9.1. Recommended ID set

- `clientId`
- `projectId`
- `infobaseId`
- `moduleId`
- `toolInstanceId`
- `dataConnectionId`
- `helpCatalogId`
- `operationRunId`[file:169][file:167][file:168]

### 9.2. Mapping rules

- `config-mcp`: `project.id` and `database.id` must map to `projectId` and `infobaseId`.
- `help-mcp`: help catalog must have stable `helpCatalogId`; binding attaches to platform version or infobase binding.
- `data-mcp`: `databaseid` remains operational pairing ID but must link to `dataConnectionId` and `infobaseId`.
- `ConfigAdmin`: `ClientProfile.Id` and `InfobaseProfile.Id` must be used as master-compatible IDs or have stable mapping.

## 10. Locking and concurrency contract

Because all modules work with files, SQLite, import/export, and temp artifacts, v1 introduces mandatory lock and busy state reporting model.[file:169][file:167][file:168]

### 10.1. General rules

- Any mutating operation must appear in `status` as `busy` or via lock marker.[file:169][file:167][file:168]
- If module already uses file/DB markers, they must be included in status output.[file:169][file:167][file:168]
- stale markers must be detected and explicitly marked.[file:169][file:167][file:168]
- Admin Hub must not directly edit internal module lock/temp files.[file:169][file:167][file:168]

### 10.2. Lock entry format

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

### 10.3. Module specifics

- `config-mcp`: `.building`, `.tmp`, single-writer policy for `projects.json`, outdated index state.
- `help-mcp`: import lock, SQLite write/read race, `defaultVersion` sync and import activity.
- `data-mcp`: config write races, S3 reachability degradation, potential config-write lock for `apply-registry`.
- `ConfigAdmin`: export lock, registry lock, vault locked state, SQLite concurrent access.

## 11. Operations log contract

Each module must maintain append-only operations log or functionally equivalent structured audit trail.[file:169][file:167][file:168]

### 11.1. Minimum record format

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

### 11.2. Purpose

Operations log is needed for:
- event feed in Admin Hub;[file:169][file:167][file:168]
- audit of automated actions;[file:169][file:167][file:168]
- analysis of failed rebuild/import/export/ping/apply;[file:169][file:167][file:168]
- history stitching by infobase and module instance.[file:169][file:167][file:168]

## 12. ConfigAdmin as host shell

Agreed v1 position: `ConfigAdmin` is the best candidate for host shell / primary Admin Hub foundation but must not absorb internal domain logic of other MCPs. It should evolve as orchestration/UI/master-registry layer over managed tools.[file:169][file:167][file:168]

This means:
- ConfigAdmin extends to master registry and tool orchestration;
- MCP modules remain separate managed instances;[file:167][file:168]
- integration via manifest + CLI + status + registry sync, not big merge codebase.[file:169][file:167][file:168]

## 13. Module-specific v1 requirements

### 13.1. 1C Config MCP

Mandatory v1 work:
- `module.manifest.json`;
- thin CLI facade;
- `inventory --json`;
- `status --json` with `projects.json`, `.db`, `.building`, `INDEXERVERSION`;
- `export-registry` / `apply-registry`;
- `rebuild-index`, `rebuild-all`, `reconcile-markers`;
- operations log.

### 13.2. 1C Help MCP

Mandatory v1 work:
- `module.manifest.json`;
- CLI entrypoint for list/status/import/default version;
- `inventory --json`;
- `status --json` with `defaultVersion`, catalog inventory, `meta.created`, `sourcePath`, `hasQueryHelp`;
- `export-registry` / `apply-registry`;
- `list-help-dbs`, `import-help`, `set-default-version`;
- import lock and operations log.

### 13.3. 1C Data MCP

Mandatory v1 work:
- `module.manifest.json`;
- CLI facade;
- `inventory --json`;
- `status --json`;
- `validate-config`, `ping`, `print-config`;
- `export-registry` / `apply-registry` for sync `databaseid` / prefix / bucket metadata;
- local-secret policy and operations log.

### 13.4. ConfigAdmin

Mandatory v1 work:
- `module.manifest.json`;
- JSON consistency for CLI;
- `inventory --json`;
- `status --json` for DB/runtime/vault/locks;
- `export-registry` / `apply-registry`;
- cross-module links in master model;
- `list-bases`, `list-runs`, `test-connection`, `export` operations;
- host-shell orchestration role.

## 14. Rollout plan v1

### Phase 1 — Discoverability and read-only protocol

First all modules become discoverable:
- manifest;[file:169][file:167][file:168]
- inventory;[file:169][file:167][file:168]
- status;[file:169][file:167][file:168]
- read-only CLI discipline.[file:169][file:167][file:168]

At this stage Admin Hub can already build unified environment status dashboard.[file:169][file:167][file:168]

### Phase 2 — Registry sync

Then controlled sync is added:
- `export-registry`;[file:169][file:167][file:168]
- `apply-registry`;[file:169][file:167][file:168]
- ownership matrix enforcement;[file:169][file:167][file:168]
- atomic writes and post-apply actions.[file:169][file:167][file:168]

### Phase 3 — Headless operations orchestration

Only after that module-specific control-plane operations are enabled:
- rebuild/import/ping/export/test-connection;[file:169][file:167][file:168]
- operations log aggregation;[file:169][file:167][file:168]
- cross-tool workflows in ConfigAdmin/Hub.[file:169][file:167][file:168]

## 15. Repository implementation requirement

Each agent implementing v1 in a specific module must:
- implement manifest and CLI without destroying current runtime;[file:169][file:167][file:168]
- reuse existing core/service layer;[file:169][file:167][file:168]
- not move GUI logic into integration layer;[file:169][file:167][file:168]
- ensure JSON protocol compatibility;[file:169][file:167][file:168]
- explicitly document master-owned and local-owned fields;[file:169][file:167][file:168]
- describe file/db races and status model for its module.[file:169][file:167][file:168]

## 16. Final directive

This document is the base v1 specification for unification. If a specific repository requires protocol deviation, the agent must document it explicitly as `protocol deviation`, stating reason, impact on Admin Hub, and safe workaround.[file:169][file:167][file:168]

Until v2 specification appears, any extensions must be backward compatible with v1 contract: manifest, inventory, status, registry sync, locks, and structured CLI.[file:169][file:167][file:168]
