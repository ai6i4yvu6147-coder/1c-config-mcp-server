# Unified 1C AI Admin Hub — Protocol v1.0.2 Addendum

## Document status

This document is an addendum to `Unified 1C AI Admin Hub — Consolidated Protocol v1` and `Protocol v1.0.1 Addendum`. Version 1.0.2 closes remaining architectural and operational gaps needed for confident `Phase 2` implementation and preparation for `Phase 3`: Hub persistence and reconcile, strict identifier rules, scoping for `platformPath`, `sourcePath` semantics, schema for `followUpOperations`, and retention policy for orphaned data.[file:169][file:167][file:168]

On conflict between v1/v1.0.1 and this document, v1.0.2 takes priority as the later normative version.[file:169][file:167][file:168]

## 1. Admin Hub implementation

In this system `Admin Hub` is implemented via **ConfigAdmin**. The canonical Hub model is physically stored in SQLite database `configadmin.db`, and ConfigAdmin acts simultaneously as:
- canonical registry storage;
- orchestration layer;
- UI host shell;
- control plane for managed tools.

This means a separate `hub.db` or separate external Hub component is not introduced in protocol v1.x. All canonical entities and links must persist in ConfigAdmin storage extended for the Hub model.

## 2. Hub persistence and reconcile

### 2.1. Canonical storage

Canonical Hub model is stored in `configadmin.db` and is the authoritative source of truth for:
- `clients`;
- `projects`;
- `infobases`;
- `toolInstances`;
- cross-module links (`configMcpProjectId`, `configMcpDatabaseId`, `dataConnectionId`, `helpCatalogId`).[file:169][file:167][file:168]

### 2.2. Reconcile direction

Normative sync direction:

1. **Hub -> tools** via `apply-registry` is the primary control-plane channel.[file:169][file:167][file:168]
2. **Tools -> Hub** via `export-registry` is used for:
   - inventory and inspection;[file:169][file:167][file:168]
   - read-back observational state;[file:169][file:167][file:168]
   - reconcile of locally computed/observed fields;[file:169][file:167][file:168]
   - drift detection.[file:169][file:167][file:168]

### 2.3. Conflict resolution

When canonical Hub model and fragment exported by a module diverge:

- For **master-owned** fields Hub is authoritative.[file:169][file:167][file:168]
- For **local-owned** fields the managed tool is authoritative.[file:169][file:167][file:168]
- For **observational/export-only** fields Hub may store them as read-back metadata but must not use them as basis for silent overwrite of master-owned fields.[file:170]

### 2.4. Reconcile modes

v1.0.2 introduces two logical reconcile modes:
- `authoritative-apply`: Hub materializes canonical state down into managed tool.[file:169][file:167][file:168]
- `observational-reconcile`: Hub reads fragment and updates only permitted read-back fields (`lastExportAt`, `lastExportStatus`, `indexStatus`, health metadata, etc.).[file:169][file:167][file:168]

## 3. Identifier rules

### 3.1. Hub-owned IDs

The following IDs must be **strict UUID v4**, lowercase, with hyphens:
- `clientId`
- `projectId`
- `infobaseId`
- `toolInstanceId`
- `dataConnectionId`
- `operationRunId`[file:169][file:168]

Normative regex:

```text
^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
```

### 3.2. Domain-specific slugs

The following fields may use **domain slug**, not UUID:
- `helpCatalogId`

Normative regex for help catalog slug:

```text
^help-\d+-\d+-\d+$
```

Example valid value:
- `help-8-3-27`

### 3.3. ID generation rules

- Hub-owned IDs are generated in ConfigAdmin as Admin Hub implementation.
- Managed tools must not unilaterally replace canonical IDs with their local IDs.[file:169][file:168]
- Local operational IDs are allowed only as secondary mapping fields. For `data-mcp` this applies to `databaseid`, which does not replace `dataConnectionId` and `infobaseId`.

## 4. `platformVersion` and `platformPath`

### 4.1. Canonical rule

`platformVersion` is a canonical Hub field at `infobase` level.[file:167]

`platformPath` is a **per-infobase operational property** used by ConfigAdmin to launch platform, export, and connection tests.

### 4.2. Ownership rule

- `platformVersion` — master-owned canonical Hub field.[file:167]
- `platformPath` — ConfigAdmin-owned infobase setting, materialized and used in ConfigAdmin.

### 4.3. Scope rule

Within v1.0.2 `platformPath` is considered a property of a specific `infobase` in ConfigAdmin storage, not a machine-global path in machine registry. This reflects the real scenario where different infobases may use different 1C platforms.

This field may be exported in ConfigAdmin fragment but must not be treated as machine-global property for all tool instances at once.

## 5. `sourcePath` semantics for configuration exports

### 5.1. Canonical replacement

Field `sourceXml` from early drafts is replaced by **`sourcePath`** as more precise and general.[file:170]

### 5.2. Allowed values

`sourcePath` may point to:
- directory with hierarchical XML configuration export;[file:170]
- archive file containing configuration export.

### 5.3. Source kind rule

v1.0.2 introduces required field:

```json
{
  "sourcePath": "D:/Exports/ClientA/BaseERP/config-export.zip",
  "sourceKind": "archive"
}
```

Allowed `sourceKind` values:
- `directory`
- `archive`[file:170]

### 5.4. Processing rule

- If `sourceKind=directory`, `config-mcp` must index export from directory.
- If `sourceKind=archive`, `config-mcp` must use archive input workflow defined by its implementation.[file:170]

## 6. ConfigAdmin role and in-process rule

ConfigAdmin performs **dual role**:
- as managed tool (`inventory/status/export-registry/apply-registry/list-bases/export/...`);
- as concrete Admin Hub implementation.

### 6.1. In-process execution rule

If Hub orchestration initiates ConfigAdmin's own operation, **in-process** execution via internal ConfigAdmin application services is allowed, without self-subprocess launch of `configadmin.exe`.

### 6.2. External module execution rule

For all other managed tools (`config-mcp`, `help-mcp`, `data-mcp`) orchestration must run via manifest-resolved CLI subprocess contract.[file:169][file:167][file:168]

This rule avoids meaningless self-subprocess pattern for ConfigAdmin while preserving unified headless protocol for external modules.

## 7. `followUpOperations` schema

### 7.1. Purpose

`followUpOperations` lets `apply-registry` or another control-plane operation return Hub a structured list of recommended follow-up actions. Especially important for `config-mcp` rebuild scenarios and subsequent orchestration workflows.[file:167][file:170]

### 7.2. Normative schema

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

### 7.3. Rules

- `moduleId` — module target for the operation.[file:169][file:167][file:168]
- `command` — CLI command per module contract.[file:169][file:167][file:168]
- `args` — flat JSON object with command arguments.[file:169][file:167][file:168]
- `reason` — human-readable explanation for follow-up.[file:169][file:167][file:168]
- `blocking` — if `true`, Hub must treat operation as mandatory to bring state into consistent form.[file:169][file:167][file:168]

### 7.4. Hub handling

Hub may:
- execute `followUpOperations` automatically per policy;[file:169][file:167][file:168]
- show them to user for confirmation;[file:169][file:167][file:168]
- defer them, saving as pending admin actions.[file:169][file:167][file:168]

## 8. Stale lock thresholds

v1.0.2 introduces recommended but normatively acceptable default stale thresholds. ConfigAdmin export, Help import, and Config MCP rebuild can run long; without thresholds Hub cannot correctly interpret stale markers.[file:169][file:167]

### 8.1. Default thresholds

| Lock reason | Default staleAfterMs |
|---|---:|
| `rebuild-index` | 3600000 |
| `rebuild-all` | 14400000 |
| `import-help` | 14400000 |
| `export` | 14400000 |
| `apply-registry` | 900000 |
| `config-write` | 900000 |

Values above mean 1 hour for single rebuild and 4 hours for heavy import/export batch operations. Aligns with Help import and ConfigAdmin export being potentially long operations.[file:170][file:169]

### 8.2. Lock payload extension

Recommended lock entry extension:

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

`apply-registry` in v1.0.2 performs **only logical change** of canonical/admin state. It must not automatically delete physical artifacts such as:
- XML/export archives;[file:169]
- config/help `.db` indexes;[file:167]
- run history;
- local caches and temp files.[file:169][file:167][file:168]

### 9.2. Orphan retention

After logical delete data is considered **orphaned** but retained until separate cleanup operation.[file:169]

### 9.3. Cleanup commands

Physical cleanup must run via separate commands, e.g.:
- `cleanup-orphans`
- `prune-exports`
- `prune-indexes`
- `cleanup-runs`[file:169]

Specific command set depends on module, but semantics must be explicit and not mixed with `apply-registry`.[file:169][file:167][file:168]

## 10. ConfigAdmin and project authority

`project` is a **Hub-only canonical entity**.[file:169]

This means:
- ConfigAdmin fragment need not export `projects[]` as primary entity.
- ConfigAdmin may reference project via `links.configMcpProjectId` and `projectId`-related fields if present.[file:169]
- Authoritative creation and lifecycle of `projectId` runs in ConfigAdmin as Admin Hub implementation.[file:169]

## 11. JSON Schema deliverables

v1.0.2 requires machine-validatable JSON Schema artifacts as part of the protocol package. These schemas must exist as separate files in the specification package or Admin Hub repository.[file:169][file:167][file:168]

Minimum set:
- `schemas/manifest-v1.schema.json`
- `schemas/inventory-v1.schema.json`
- `schemas/status-v1.schema.json`
- `schemas/apply-result-v1.schema.json`
- `schemas/registry-fragment-config-mcp-v1.schema.json`
- `schemas/registry-fragment-help-mcp-v1.schema.json`
- `schemas/registry-fragment-data-mcp-v1.schema.json`
- `schemas/registry-fragment-config-admin-v1.schema.json`[file:169][file:167][file:168]

Schema contents are not embedded fully in this document, but their presence becomes a normative requirement.[file:169][file:167][file:168]

## 12. Environment variable naming

For ConfigAdmin the normative env variable name is:

```text
CONFIGADMIN_DATA_DIR
```

`CONFIGADMINDATADIR` is allowed only as legacy alias during transition and must be documented as deprecated alias. This closes inconsistency between early texts and makes naming predictable.

## 13. Reference workflow

### 13.1. Export -> Config sync -> Rebuild

Normative reference workflow for ConfigAdmin and Config MCP:

1. ConfigAdmin exports infobase configuration.
2. ConfigAdmin updates canonical infobase metadata, including `sourcePath` and `sourceKind` if workflow requires.[file:169]
3. ConfigAdmin materializes fragment for `config-mcp` and calls `apply-registry`.[file:169]
4. `config-mcp` updates `projects.json` and returns `followUpOperations` with `rebuild-index` if needed.
5. Hub/ConfigAdmin runs `rebuild-index` automatically or after user confirmation.[file:169]

### 13.2. Help binding update

1. Hub updates `platformVersion` or `defaultHelpVersion` at `infobase` level.
2. ConfigAdmin materializes fragment for `help-mcp` and calls `apply-registry`.[file:167]
3. `help-mcp` updates config and may return `restartRequired=true` or `followUpOperations` for import/refresh scenario.

### 13.3. Data connection reconcile

1. Hub/ConfigAdmin updates `infobaseId <-> dataConnectionId <-> databaseid` mapping or S3 metadata.
2. ConfigAdmin calls `apply-registry` for `data-mcp`.[file:168]
3. `data-mcp` applies `config.local.json` and Hub may run `validate-config` or `ping --database-id ...` as post-apply verification.

## 14. Implementation directive

From this point protocol v1.x is sufficiently defined for:
- immediate `Phase 1` implementation;
- controlled `Phase 2` implementation;[file:169][file:167][file:168]
- preparation of `Phase 3` orchestration scenarios.[file:169][file:167][file:168]

Each agent implementing protocol support must rely on:
- v1;
- v1.0.1 addendum;
- this v1.0.2 addendum.[file:169][file:167][file:168]

If a module cannot immediately meet part of v1.0.2 requirements, return explicit `protocol deviation` with closure plan.[file:169][file:167][file:168]
