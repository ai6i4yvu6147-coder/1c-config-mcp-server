## AI context

Full project documentation and rules live in `docs/`. For agent pipeline hints, see [`AGENTS.md`](AGENTS.md).

### Start here

1. `docs/agent-onboarding.md`
2. `docs/README.md` (table of contents)
3. Admin Hub integration: `docs/admin-hub/integration.md`
4. Group integration: `docs/group/integration.md`

### Key rules

- **NO_DB_MIGRATIONS**: no migrations/conversions for existing SQLite databases — databases are always recreated via `admin_tool`.
- **Metadata whitelist**: new types are added incrementally as needed.
- **Testing**: functional verification only on the connected MCP via tool calls (see `docs/testing-protocol.md`).
- **Group-sync**: do not commit sync packets; delivery — operator per `docs/group/OPERATOR-HANDOFF.md`; processing — skill `sync`.
- **Agents/skills (canon 2.4.0):** 1 subagent (`doc-librarian`); 4 skills (`normalize-project`, `canon-align`, `maintain-docs`, `sync`).
