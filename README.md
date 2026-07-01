# 1C Config MCP Server

For AI and developers: see [`docs/`](docs/) (start with [`docs/agent-onboarding.md`](docs/agent-onboarding.md)). Admin Hub: [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md). Brief AI context: [`README_AI.md`](README_AI.md).

Tool for working with 1C configurations via an AI assistant with MCP support: code analysis, object search, metadata structure.

**Important:** databases are always recreated; there are no migrations.

## Quick start

1. Build: `build_all.bat` → portable with `Server/`, `Admin/`, `Tools/`.
2. `Admin/1C-Config-Admin.exe` → project → database → path to `Configuration.xml` from the export.
3. MCP: add a command in the client config pointing to `Server/1c-config-server.exe` inside the portable folder.
4. Tools: `active_databases`, `list_objects`, `search_code`, `get_object_structure`, …

## Project structure (sources)

| Directory / file | Purpose |
|------------------|---------|
| `admin_tool/` | GUI and CLI (`admin_tool/cli.py`, Hub protocol) |
| `server/` | MCP server |
| `shared/` | XML parser, ProjectManager, hub_protocol |
| `docs/admin-hub/` | managed tool integration with Admin Hub |
| `docs/group/` | sync with group `1c-cursor` (Sub) |
| `projects.example.json` | example portable runtime config |

## Group and Admin Hub

- **Role:** Sub · group `1c-cursor` · Head: `1c-admin-tool`
- **Integration:** [`docs/group/integration.md`](docs/group/integration.md)
- **Hub CLI:** `rebuild-index`, `apply-registry`, `status` — see [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md)

## Portability

The portable build can be moved. After moving, update the exe path in the MCP client config and restart the AI application.

Detailed steps (MCP config, troubleshooting) — in [`docs/agent-onboarding.md`](docs/agent-onboarding.md) and historically in git history of `readme.txt` (removed during Sub normalize 2.2.0).
