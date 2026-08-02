# Agent map

Single entry point for the orchestrator (the main agent).

## What this project is

Indexes a 1C configuration export (XML + BSL) into SQLite and exposes MCP tools for code and metadata search/analysis. The portable MCP server is autonomous: index and tools work without Admin Hub. Admin Hub integration — headless CLI (`rebuild-index`, `apply-registry`) and local adaptation in [`admin-hub-integration.md`](admin-hub-integration.md).

## Session start

1. Read `docs/todo.md`.

## Directory map

```
admin_tool/               # GUI and CLI (hub_protocol, db_manager)
server/                   # MCP server (server.py, tools.py)
shared/                   # XML parser, ProjectManager, hub_protocol
tests/
scripts/                  # bench-form-insert, parse-benchmark
docs/
  agent-map.md            # this file
  architecture.md         # data flow, product policies
  todo.md                 # backlog
  admin-hub-integration.md
.tasks/                   # subagent handoff (gitignored)
```

## Test / build

```powershell
python -m pytest tests/
build_all.bat   # portable: Admin/, Server/, Tools/
```

## Key policies (do not violate)

- **NO_DB_MIGRATIONS** — recreate databases via `admin_tool`, never migrate existing SQLite in `databases/`.
- **`INDEXER_VERSION`** — bump in `shared/indexer_version.py` on incompatible schema changes (`.cursor/rules/bump-indexer-version.mdc`).
- **Testing** — verify only on the connected MCP via tool calls; start with `active_databases` (see `testing-protocol.md`).
- **Parser** — extend from real export XML/BSL, not guesses; ask for export paths when missing.
- **Ephemeral handoffs** — `HANDOFF-*.md` in repo root (gitignored); integration canon in `admin-hub-integration.md`.
