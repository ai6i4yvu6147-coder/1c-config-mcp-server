## Project documentation

Structured context for AI and developers. Root overview: [`../README.md`](../README.md).

**Role:** Sub · group `1c-cursor` · Head `1c-admin-tool`.

### Reading order

1. [`agent-map.md`](agent-map.md) — entry: directory map, delegation, sync triggers
2. [`todo.md`](todo.md) — backlog; **`## Hub pending`** for group sync
3. [`architecture.md`](architecture.md) — data flow, components, product policies
4. Domain specs (below)
5. [`group/integration.md`](group/integration.md) — Head link, protocol state

### Domain specs

| Document | Contents |
|----------|----------|
| [`mcp-tools.md`](mcp-tools.md) | MCP tools and call examples |
| [`database.md`](database.md) | SQLite schema, no-migrations policy |
| [`metadata-whitelist.md`](metadata-whitelist.md) | Metadata type whitelist |
| [`dependency-layer.md`](dependency-layer.md) | Type system, reverse references |
| [`roles-layer.md`](roles-layer.md) | Roles, RLS, phase 4 spec |
| [`form-type-system.md`](form-type-system.md) | Form type system |
| [`form-entity-model.md`](form-entity-model.md) | Form properties, overview profiles, drill-down (spec) |
| [`testing-protocol.md`](testing-protocol.md) | Verification on connected MCP |
| [`performance.md`](performance.md) | Performance notes |
| [`architecture-audit-2026-07.md`](architecture-audit-2026-07.md) | DB / parser / tools audit — findings and prioritized recommendations |
| [`admin-hub-integration.md`](admin-hub-integration.md) | Admin Hub module roadmap, Phase 3 CLI |

### Group and protocol

| Document | Contents |
|----------|----------|
| [`group/integration.md`](group/integration.md) | Head hub link, protocol state, local deviations |
| [`group/protocol-ref/epoch0/`](group/protocol-ref/epoch0/) | Stable protocol snapshot (v1 + addenda v1.0.1–v1.0.3) |
| [`group/OPERATOR-HANDOFF.md`](group/OPERATOR-HANDOFF.md) | Operator credentials/deploy (human tier) |
| [`canons/`](canons/) | Local WI canon copy |
| [`normalize-record.md`](normalize-record.md) | Last normalize metadata |

**Subagents and skills (canon 2.5.0):** `.cursor/agents/` — 5 (`doc-librarian` + dev pipeline); `.cursor/skills/` — 4 (`normalize-project`, `canon-align`, `maintain-docs`, `sync`).

### Group sync tools

```powershell
python scripts/project-doctor.py --type Sub
python scripts/sync-status.py --repo .
python scripts/protocol-snapshot.py --status --repo .
```

Hub state: `C:/projects/1c-admin-tool/GROUP-HUB.md` · `C:/repo/1c-config-admin-tool/GROUP-HUB.md`. Sync — skill **`sync`** when `## Hub pending` is non-empty.
