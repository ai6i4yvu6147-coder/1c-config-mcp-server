# Unified 1C AI Admin Hub — Protocol v1.0.5 Addendum

## Document status

Addendum to v1 + v1.0.1 + v1.0.2 + v1.0.3 + v1.0.4.

**Goal:** single canonical portable write surface for data-mcp — D-MCP CLI (and compact UI using the same code path). Clarifies v1.0.4 §1.3 after Head implementation review (2026-07-02).

**Mapping canon:** [`registry-mapping-data-mcp.md`](registry-mapping-data-mcp.md).

On conflict with v1.0.4 §1.3 wording on optional Hub direct sealed-file write, **this addendum takes priority**.

---

## 1. Canonical portable write surface (data-mcp)

All writes to the portable instance **`config.local.json`** and **`credentials.sealed.json`** go through **D-MCP implementation** (CLI subprocess from Hub, or compact UI calling the same library code in standalone).

| Data class | Portable target | Command | In `apply-registry` fragment? |
|------------|-----------------|---------|-------------------------------|
| Bucket metadata, `connections[]` | `config.local.json` | **`apply-registry`** | yes (metadata only) |
| S3 `accessKeyId` / `secretAccessKey` | `credentials.sealed.json` | **`apply-secrets`** | **no** (v1.0.4 §1.3 unchanged) |
| Hub pairing refs, D-MCP password | Hub SQLite only | — | — |

### 1.1. Hub (managed) — normative Save orchestration

On Hub **Save** (D-MCP settings UI), after Hub SQLite persist:

1. **`apply-secrets`** — write / replace sealed credentials file (when S3 keys provided or rotation requested).
2. **`apply-registry`** — patch `config.local.json` (bucket + connections metadata).
3. Post-apply: **`validate-config`**; optional **`ping --database-id`**.

Hub **must not** write `credentials.sealed.json` or `config.local.json` directly. **No fallback** to Head file I/O for production managed sync.

### 1.2. Compact UI (standalone)

Full first-run and credential edit use the **same sealing and config persistence code** as CLI `apply-secrets` / `apply-registry` (in-process calls, not a second format).

### 1.3. `apply-secrets` CLI (Sub)

- **Required** for managed Hub parity (promoted from v1.0.4 “optional”).
- Contract: JSON stdin or `--input` file with `accessKeyId`, `secretAccessKey`; D-MCP password via env `DMCP_PASSWORD` or `--password-stdin` (dev/CI only per v1.0.4 agent boundary).
- Output: writes `credentials.sealed.json` at path from `sealed_secrets_path` / `config.local.json` → `credentials_file`; atomic replace; UTF-8 JSON without BOM.
- Cipher / test vector — unchanged (v1.0.4 + mapping doc § Cipher test vector).

#### 1.3.1. Credential migration on successful `apply-secrets` (Head `sync_delta` 20260702T210000)

After sealed file is written and verified (round-trip unseal), **`apply-secrets` must complete portable migration in the same locked transaction** (Sub-owned; Hub **must not** patch `config.local.json` or delete legacy files):

1. **Point config at sealed file** — atomically update `config.local.json` → `credentials_file` to the **relative** path of the sealed file just written (`credentialsFile` / `sealedSecretsPath` override, else manifest default `credentials.sealed.json`).
2. **Remove deprecated plaintext** — delete portable-root **`credentials.local.json`** when it exists and its resolved path differs from the sealed target. No other paths removed.
3. **Failure safety** — if sealing or config update fails, do not delete plaintext; prior sealed file unchanged unless replace succeeded.

**Response** (additive fields on success):

```json
{
  "postApplyActions": {
    "reloadRequired": true,
    "credentialsFileUpdated": true,
    "plaintextRemoved": true
  },
  "warnings": ["removed_deprecated_plaintext:credentials.local.json"]
}
```

**Rationale:** managed Hub Save calls `apply-secrets` then `apply-registry`; leaving `credentials_file` on plaintext or keeping `credentials.local.json` on disk bypasses sealed + unlock (observed in portable QA 2026-07-02). Compact UI / in-process `apply-secrets` (**§1.2**) must use the same migration helper.

### 1.4. What does not change

- S3 keys **remain excluded** from `apply-registry` fragment and agent/context channels.
- Hub stores **D-MCP password** in SQLite (`encrypted_dmcp_password`), not S3 keys.
- Managed compact UI stays **read-only** for mappings and S3 keys (v1.0.4 §4).

---

## 2. Implementation note (Head)

Head D-H4 (2026-07-02): managed Save orchestrates Sub CLI only (`apply-secrets` → `apply-registry` → `validate-config`). Direct sealed-file write (D-H3 interim) removed.

---

*Accepted: Sub `protocol_ack` `20260702T180000` (2026-07-02) on Head `sync_delta` `20260702T160000`. Sub `apply-secrets` done; Head D-H4 unblocked.*

*§1.3.1 accepted: Sub `protocol_ack` `20260702T210000` (2026-07-02) on Head `sync_delta` `20260702T210000` — credential migration in `apply-secrets`.*
