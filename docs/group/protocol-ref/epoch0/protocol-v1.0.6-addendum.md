# Unified 1C AI Admin Hub — Protocol v1.0.6 Addendum

## Document status

Addendum to v1 + v1.0.1 + v1.0.2 + v1.0.3 + v1.0.4 + v1.0.5.

**Goal:** agent-mediated D-MCP runtime unlock with **passive Hub** (settings + context only). Amends v1.0.4 §3 agent boundary.

**Status:** ack by Sub `20260702T190000` (2026-07-02). Head D-H5 implemented.

**Mapping canon:** [`registry-mapping-data-mcp.md`](registry-mapping-data-mcp.md).

On conflict with v1.0.4 §3 (“password not passed through MCP protocol per tool call”), **this addendum takes priority** for the dedicated unlock tool defined below.

---

## 1. Role split (normative)

| Actor | Responsibility | Must not |
|-------|----------------|----------|
| **Hub** | Settings UI; Hub SQLite persist; CLI orchestration (`apply-secrets`, `apply-registry`); `resolve_infobase_context` (refs + lock hint) | Spawn/unlock D-MCP; return D-MCP password or S3 keys to agent |
| **D-MCP MCP server** | Runtime unlock session; S3 data tools; sealed-file decrypt in process memory | Return S3 keys or password in tool responses |
| **Agent** | Resolve context via Hub; ask user for D-MCP password when locked; call D-MCP **`unlock_credentials`** once per server process; then data tools with `database_id` only | Receive S3 secrets; use Hub as unlock orchestrator |

**Hub stores `encrypted_dmcp_password`** for **admin** Save / `apply-secrets` only. That storage does **not** authorize Hub to unlock the live MCP server on behalf of the agent.

---

## 2. Hub `resolve_infobase_context` (passive)

Hub context tool returns **refs only** plus optional readiness hint.

### 2.1. Required / optional fields

| Field | Required | Notes |
|-------|----------|-------|
| `infobaseId`, names, `configMcp` refs | yes | unchanged from mapping doc |
| `dataMcp.databaseId`, `paired` | when paired | unchanged |
| `dataMcp.credentialsState` | recommended | `locked` \| `unlocked` \| `unknown` |

`credentialsState` may be derived from last Hub `status --json` (`details.credentialsResolvable`) or `unknown` if not checked. Hub **must not** block on unlock; hint only.

### 2.2. Forbidden in context response

- D-MCP password (plaintext or Hub-decrypted)
- S3 `accessKeyId` / `secretAccessKey`
- Sealed file payload

---

## 3. D-MCP MCP tool: `unlock_credentials`

### 3.1. Purpose

Decrypt sealed credentials into **process memory** so data tools can run. Replaces mandatory pre-start `DMCP_PASSWORD` for agent-driven workflows.

### 3.2. Contract

**Input:**

```json
{ "password": "<D-MCP password UTF-8>" }
```

**Output (success):**

```json
{
  "success": true,
  "unlocked": true,
  "credentialsResolvable": true
}
```

**Output (failure):**

```json
{
  "success": false,
  "unlocked": false,
  "errors": ["Invalid password or corrupted sealed file"]
}
```

**Rules:**

1. **Once per server process** — after successful unlock, subsequent calls return `unlocked: true` without re-decrypt (idempotent) or `already_unlocked` warning.
2. **Forbidden on data tools** — `run_query`, `get_attachments`, etc. **must not** accept D-MCP password.
3. **No secret echo** — response never contains S3 keys or password.
4. **Logging** — implementations must not log password or decrypted keys.
5. **Same cipher** — uses existing sealed envelope (Argon2id + AES-256-GCM); **no KDF change** in v1.0.6.

### 3.3. Coexistence with startup unlock

These remain valid and **orthogonal**:

| Method | When |
|--------|------|
| `DMCP_PASSWORD` env at process start | dev / CI / tray |
| Compact UI unlock | standalone operator |
| MCP `unlock_credentials` | agent-mediated (this addendum) |

---

## 4. Agent workflow (normative)

1. Call Hub `resolve_infobase_context` → refs + `credentialsState`.
2. If `locked` or data tool fails with credentials error → ask **user** for D-MCP password (same password configured in Hub admin UI in managed mode).
3. Call D-MCP `unlock_credentials`.
4. Call D-MCP data tools with `database_id` only.

Agent **must not** expect Hub to unlock D-MCP or to return the password from Hub SQLite.

---

## 5. Security posture (explicit tradeoff)

Agent-mediated unlock means the D-MCP password may transit **user → agent → MCP tool**. This is an accepted **convenience mode** for automation without Hub runtime orchestration.

Deployments requiring stricter boundaries may:

- use startup `DMCP_PASSWORD` / tray only and disable agent unlock policy; or
- set `module.manifest.json` flag `allowAgentUnlock: false` (optional Sub extension).

Default for new managed installs: **`allowAgentUnlock: true`** unless operator opts out.

---

## 6. Implementation notes

| Repo | Task |
|------|------|
| **1c-data-mcp** (Sub) | MCP tool `unlock_credentials` wrapping existing in-process unlock / `unlock_credentials_at_startup` |
| **1c-admin-tool** (Head) | D-H5: `resolve_infobase_context` + `credentialsState`; Hub MCP via `configadmin mcp serve` (passive) |

Cipher / test vector — **unchanged** (v1.0.4 + mapping doc).

---

*Proposal: Head `sync_delta` 20260702 — operator-confirmed auth model: passive Hub, agent-mediated D-MCP unlock. Sub ack `20260702T190000`; Head D-H5 `configadmin mcp serve`.*
