# Unified 1C AI Admin Hub — Protocol v1.0.4 Addendum

## Document status

Addendum to v1 + v1.0.1 + v1.0.2 + v1.0.3.

**Goal:** normatively close dispute D3 (merge 2026-07-01, Head ↔ `1c-data-mcp`): sealed S3 credentials, D-MCP unlock password in Hub, agent boundary.

**Mapping canon:** [`registry-mapping-data-mcp.md`](registry-mapping-data-mcp.md) (agreed after Sub `protocol_ack`).

On conflict with v1.0.1 §10.3 on data-mcp credentials, this addendum takes priority.

---

## 1. data-mcp sealed credentials

### 1.1. File name

- Canon: **`credentials.sealed.json`** at portable root (or path from `config.local.json` → `credentials_file`).
- Plaintext **`credentials.local.json`** in portable distribution **deprecated** after sealed path rollout.

### 1.2. Contents

- File stores **only** S3 `accessKeyId` / `secretAccessKey` (and future fields of the same class) in encrypted payload.
- Cipher: Argon2id + AES-256-GCM; parameters and test vector — in [`registry-mapping-data-mcp.md`](registry-mapping-data-mcp.md) § "Cipher test vector".

### 1.3. Registry sync

- `apply-registry` fragment **does not** contain S3 keys (as v1.0.1 §8.4).
- Sealed file write: Hub D-MCP settings UI (managed) or compact UI (standalone); optional Sub CLI `apply-secrets`.

> **Updated by v1.0.6:** runtime unlock via D-MCP MCP tool `unlock_credentials` (agent-mediated); Hub passive — no spawn/unlock. See [`protocol-v1.0.6-addendum.md`](protocol-v1.0.6-addendum.md).

---

## 2. D-MCP unlock password in Hub (admin bridge)

Extension of v1.0.1 §10.3 for **`managed`** mode:

| Allowed | Forbidden |
|---------|-----------|
| Hub stores **`encrypted_dmcp_password`** under vault master password | Hub stores S3 access keys in SQLite |
| Hub uses D-MCP password **only** for read/write `credentials.sealed.json` in admin UI | Context tools / registry / agent channels return D-MCP password or S3 keys |
| Explicit managed mode on `tool_instance` | Automatic Hub requirement for standalone portable |

**Standalone:** portable **not required** to give D-MCP password to Hub. Local compact UI — full first-run.

---

## 3. Agent and MCP boundary

- Agent calls data-mcp MCP tools with **`database_id`** (and query payload). **Does not** receive S3 credentials, sealed payload, D-MCP password.
- Hub `resolve_infobase_context` — **refs only** (see mapping doc).
- D-MCP MCP server unlocks sealed file **at process start**; password **not** passed through MCP protocol per tool call.

---

## 4. Compact UI modes (data-mcp)

| `mode` | Local compact UI |
|--------|------------------|
| `managed` | Read-only: bucket metadata, `connections[]`, lock state; **no** local edit of mappings/S3 keys |
| `standalone` | Full first-run: bucket, keys, connections |
| break-glass | `--standalone-override` or marker file — documented operator procedure when Hub unavailable |

---

## 5. Identifiers in JSON

- Fragment / `apply-registry`: field **`databaseid`** (lowercase).
- Hub context tool response: **`databaseId`** (camelCase) — dual convention, documented in mapping canon.

---

*Merge: `protocol_dispute` `20260701T161500-1c-data-mcp` → D1–D3 resolved by Head `20260701T170000`.*
