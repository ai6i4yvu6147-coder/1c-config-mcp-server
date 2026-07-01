## Agent onboarding (AI context)

### Project type

**Sub** (subordinate) — module `1c-config-mcp` in group `1c-cursor`.

| Field | Value |
|-------|-------|
| Head | `1c-admin-tool` |
| Head path | `C:/projects/1c-admin-tool` |
| Protocol canon | `C:/projects/1c-admin-tool/docs/group/shared/` |
| State | `stable` (epoch 0) — see [`group/integration.md`](group/integration.md) |

The portable MCP server is **autonomous**: index and tools work without Hub. Admin Hub integration — via packet sync of docs and headless CLI (`rebuild-index`).

### Project in brief

The project indexes a 1C configuration export (XML + BSL) into SQLite and provides MCP tools for code and metadata search/analysis.

### Key project policies (do not violate)

- **NO_DB_MIGRATIONS**: never write migrations/conversions for existing SQLite databases in `databases/`. After schema/import logic changes, databases are **always recreated** via `admin_tool` from the source export.
- **`INDEXER_VERSION`**: on incompatible schema/data changes in the DB, bump the constant in `shared/indexer_version.py` (see `.cursor/rules/bump-indexer-version.md`, details in `database.md`).
- **Metadata type whitelist**: the parser intentionally handles only types from `shared/xml_parser.py` (`object_types`). New types are added **incrementally** as needed, with type-specific considerations.
- **Testing**: functional verification is done on the "working" MCP after the user rebuilds the server and reconnects MCP in the agent. Verification — **only via MCP tool calls**, always starting with `active_databases`; no parser simulation, no direct SQLite reads, no "technical" databases.
- **Sources vs runtime (portable)**: sources in the repo must not contain runtime state (e.g. `projects.json`, `databases/*.db`). These files live next to the portable instance and are created/changed via `admin_tool`.
- **Responsibility split**: the agent changes sources; the user rebuilds portable/server and databases; the agent verifies results in production via MCP tools.
- **Parser: rely on real exports**: when extending `shared/xml_parser.py` and import in `admin_tool/db_manager.py`, do not "guess" structure — rely on real XML/BSL export files. If export paths are not provided, ask the user (exports live outside the repo). **Source order:** to understand XML layout (not only the path to `Configuration.xml`), first request the export directory path or a **specific metadata file** (e.g. `Documents/…xml`) or a minimal XML fragment; external materials (web, third-party specs) — **after** reviewing a real file or if the user explicitly confirms no export is available and **not instead of** the export file.
- **Group-sync**: shared protocol canon — in Head `docs/group/shared/`; local Hub adaptation — [`admin-hub/`](admin-hub/). Sub updates local specs via **packets** from `docs/group/inbox/`; do not commit sync packets. Outbox→inbox delivery — **operator** per [`group/OPERATOR-HANDOFF.md`](group/OPERATOR-HANDOFF.md); processing — skill **`sync`**.

### Normalization and canons

| Path | Purpose |
|------|---------|
| `docs/canons/` | Local WI standards copy (canon **2.4.0**) |
| `group.manifest.yaml` | Sub role, module id, Head reference |
| `scripts/project-doctor.py` | Structure check |
| `docs/group/OPERATOR-HANDOFF.md` | Manual Head ↔ Sub packet delivery (operator) |
| `docs/group/templates/` | Sync packet templates |
| `.cursor/skills/` | **4 skills** — `normalize-project`, `canon-align`, `maintain-docs`, `sync` |
| `.cursor/agents/` | **1 subagent** — `doc-librarian` |
| `docs/normalize-record.md` | Last normalize record |

Re-normalize: `/re-normalize` command (see `.cursor/commands/re-normalize.md`) or initiator `subordinate.md` from Workspace improve.

### Terms (to avoid confusion)

- **"Real MCP" / "working MCP"**: MCP server **already connected in the IDE** (Cursor/other), verification via **actual tool calls**.
- **Important on names**: the connection name in the IDE may not match the project/folder/exe name.
  - In Cursor and MCP descriptions there are at least 2 identifiers: `serverIdentifier` and `serverName`.
  - For clarity, rely not on the name but on the presence of required tools (`active_databases`, `list_objects`, `search_code`, …) and the actual `active_databases` result.

### Quick links

- Architecture and data flow: `architecture.md`
- MCP tools: `mcp-tools.md`
- SQLite (tables/relations, FTS5, NO_DB_MIGRATIONS rule): `database.md`
- Metadata whitelist and how to extend: `metadata-whitelist.md`
- Type system (metadata + forms **done**), `find_referencing_objects` (**done**), subsystems in `metadata_relations` (phase 3 **done**); roles and subscriptions — phases 4–5 in backlog: `dependency-layer.md`
- Form type system details, MCP reference cases: `form-type-system.md`
- Testing protocol: `testing-protocol.md`
- Admin Hub integration (direction, does not block current work): `admin-hub/integration.md`
- Group and sync with Head: `group/integration.md`
