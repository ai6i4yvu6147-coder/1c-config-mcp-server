# Agent map

Single entry point for the orchestrator (the main agent).

## Type

**Subordinate (Sub)** — module `1c-config-mcp` in group `1c-cursor`. Head: `1c-admin-tool` (`C:/projects/1c-admin-tool` · `C:/repo/1c-config-admin-tool`).

## What this project is

Indexes a 1C configuration export (XML + BSL) into SQLite and exposes MCP tools for code and metadata search/analysis. The portable MCP server is autonomous: index and tools work without Hub. Admin Hub integration — headless CLI (`rebuild-index`, `apply-registry`) and local adaptation in [`admin-hub-integration.md`](admin-hub-integration.md).

## Session start

1. Read `docs/todo.md`.
2. If `## Hub pending` has items → invoke skill **`sync`** before other work.
3. Full `docs/canons/` — on normalize or dispute, not every session.

## Directory map

```
admin_tool/               # GUI and CLI (hub_protocol, db_manager)
server/                   # MCP server (server.py, tools.py)
shared/                   # XML parser, ProjectManager, hub_protocol
tests/
scripts/                  # project-doctor, sync-status
docs/
  agent-map.md            # this file
  architecture.md         # data flow, product policies
  todo.md                 # backlog + ## Hub pending
  admin-hub-integration.md
  group/integration.md
.tasks/                   # subagent handoff (gitignored)
```

## Subagents — when to delegate

| Agent | Delegate when | Skip when |
|-------|---------------|-----------|
| `code-explorer` | Large search, impact map across parser/MCP/admin | Single known file |
| `task-planner` | Multi-step feature spanning modules | One-line fix |
| `implementer` | One plan step ready | No plan yet |
| `verifier` | Step/feature claimed done | Mid-implementation |
| `doc-librarian` | Bulk doc edits (via `maintain-docs`) | Single typo |

Built-in **Explore** / **Bash** handle tiny queries directly.

## Orchestrator owns the loop

Review the plan before the implementer runs. On `verifier: partial | fail`, send the Fix list back to the implementer — cap at 3 rounds, then surface to the user.

## `.tasks/` convention

```
.tasks/YYYY-MM-DD_<topic>_analysis.md   # code-explorer
.tasks/YYYY-MM-DD_<topic>_plan.md       # task-planner
.tasks/YYYY-MM-DD_<topic>_review.md     # verifier
```

Pass paths to subagents, not full file contents.

## Test / build

```powershell
python -m pytest tests/
build_all.bat   # portable: Admin/, Server/, Tools/
```

## Hub (Sub)

- **Hub file:** `C:/projects/1c-admin-tool/GROUP-HUB.md` · `C:/repo/1c-config-admin-tool/GROUP-HUB.md` — edit only `1c-config-mcp` registry row and own threads.
- **Shared canon:** Head `docs/group/shared/` at `head.path` (read directly, no local copy).
- **Local adaptation:** [`admin-hub-integration.md`](admin-hub-integration.md); group link — [`group/integration.md`](group/integration.md).

**Sync triggers:** `## Hub pending` in todo, user `/sync 1c-config-mcp <topic>`, or contract change in Head `docs/group/shared/`.

## Key policies (do not violate)

- **NO_DB_MIGRATIONS** — recreate databases via `admin_tool`, never migrate existing SQLite in `databases/`.
- **`INDEXER_VERSION`** — bump in `shared/indexer_version.py` on incompatible schema changes (`.cursor/rules/bump-indexer-version.mdc`).
- **Testing** — verify only on the connected MCP via tool calls; start with `active_databases` (see `testing-protocol.md`).
- **Parser** — extend from real export XML/BSL, not guesses; ask for export paths when missing.
- **Ephemeral handoffs** — `HANDOFF-*.md` in repo root (gitignored); integration canon in `admin-hub-integration.md`.
