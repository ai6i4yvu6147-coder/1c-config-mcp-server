## Agent hints

**Role:** Sub (subordinate) · group `1c-cursor` · Head: `1c-admin-tool` (`C:/projects/1c-admin-tool` · `C:/repo/1c-config-admin-tool`).

**Subagents:** `.cursor/agents/` — **5** (`doc-librarian`, `code-explorer`, `task-planner`, `implementer`, `verifier`). **Skills:** `.cursor/skills/` — **4** (`normalize-project`, `canon-align`, `maintain-docs`, `sync`).

Full context — in `docs/`:

1. `docs/agent-map.md` — entry point, policies, hub triggers
2. `docs/todo.md` — backlog and `## Hub pending`
3. `docs/architecture.md` — data flow and product policies
4. `docs/README.md` — table of contents and domain specs
5. `docs/group/integration.md` — Head link, protocol state
6. Admin Hub: `docs/admin-hub-integration.md`; group contract — Head `docs/group/shared/` at `head.path`

If `docs/todo.md` has `## Hub pending` → skill **`sync`** before other work.

On SQLite schema or data format changes — see `.cursor/rules/bump-indexer-version.mdc` (manual bump of `INDEXER_VERSION` in `shared/indexer_version.py`).

For admin/CLI work under Admin Hub — follow `docs/admin-hub-integration.md` and Head `docs/group/shared/`; MCP tools remain the read-only query plane.

Handoff reports for other teams are ephemeral (`HANDOFF-*.md` in repo root, not in git); integration canon in `docs/admin-hub-integration.md`. See `.cursor/rules/cross-team-handoff.mdc`.

Structure check: `python scripts/project-doctor.py --type Sub`.

**Новый MCP-тул → строка в справке для агента.** Справка сервера — `docs/agent-guide.md` (тул `guide`, CLI `guide`, контракт Head `docs/agent-guide-contract.md`). Секция «Карта инструментов» должна перечислять ровно зарегистрированные тулы, иначе `tests/test_agent_guide.py` красный. Жанр справки — «цель → инструмент», границы и грабли; параметры не дублировать (они в схеме тула), внутренности не писать (они в `docs/`).
