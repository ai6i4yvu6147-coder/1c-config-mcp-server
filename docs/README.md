## Project documentation

Structured context for AI and developers. Root overview: [`../README.md`](../README.md).

**Role:** Sub · group `1c-cursor` · Head `1c-admin-tool`.

### Reading order (canon `canons/documentation.md`)

1. [`agent-onboarding.md`](agent-onboarding.md) — project type, policies, group-sync
2. [`todo.md`](todo.md) — backlog; **check unprocessed packets in** `group/inbox/`
3. [`architecture.md`](architecture.md) — data flow and components
4. Domain specs (below)
5. [`group/integration.md`](group/integration.md) — Head link, protocol state

### Domain specs

| Document | Contents |
|----------|----------|
| [`mcp-tools.md`](mcp-tools.md) | MCP tools and call examples |
| [`database.md`](database.md) | SQLite schema, no-migrations policy |
| [`metadata-whitelist.md`](metadata-whitelist.md) | Metadata type whitelist |
| [`dependency-layer.md`](dependency-layer.md) | Type system, reverse references |
| [`form-type-system.md`](form-type-system.md) | Form type system |
| [`testing-protocol.md`](testing-protocol.md) | Verification on connected MCP |
| [`performance.md`](performance.md) | Performance notes |

### Admin Hub

| Document | Contents |
|----------|----------|
| [`admin-hub/README.md`](admin-hub/README.md) | Section index |
| [`admin-hub/integration.md`](admin-hub/integration.md) | Module roadmap, Phase 3 CLI |
| [`admin-hub/protocol-v1.md`](admin-hub/protocol-v1.md) + addendum v1.0.1–v1.0.3 | Ecosystem protocol |

### Group and normalization

| Document | Contents |
|----------|----------|
| [`group/integration.md`](group/integration.md) | Head, protocol state, inbox/outbox |
| [`group/OPERATOR-HANDOFF.md`](group/OPERATOR-HANDOFF.md) | Manual packet delivery between repos |
| [`group/templates/`](group/templates/) | Sync packet templates |
| [`canons/`](canons/) | Local WI canon copy |
| [`normalize-record.md`](normalize-record.md) | Last normalize metadata |

**Subagent and skills (canon 2.4.0):** `.cursor/agents/` — 1 (`doc-librarian`); `.cursor/skills/` — 4 (`normalize-project`, `canon-align`, `maintain-docs`, `sync`).

### docs/group-sync tools

```powershell
python scripts/project-doctor.py --type Sub
python scripts/sync-status.py --repo .
python scripts/protocol-snapshot.py --status --repo .
```

Sync packets in `group/inbox/` and `group/outbox/` are ephemeral (in `.gitignore`); delivery — operator per [`group/OPERATOR-HANDOFF.md`](group/OPERATOR-HANDOFF.md); processing — skill **`sync`**; delete after processing.
