## Agent hints

**Role:** Sub (subordinate) · group `1c-cursor` · Head: `1c-admin-tool` (`C:/projects/1c-admin-tool`).

**Subagent:** `.cursor/agents/` — **1** (`doc-librarian`). **Skills:** `.cursor/skills/` — **4** (`normalize-project`, `canon-align`, `maintain-docs`, `sync`).

Full context — in `docs/`:

1. `docs/agent-onboarding.md` — policies and project type
2. `docs/todo.md` — backlog and unprocessed inbox packets
3. `docs/architecture.md` — data flow and components
4. `docs/README.md` — table of contents and domain specs
5. `docs/group/integration.md` — Head link, protocol state
6. Admin Hub: `docs/admin-hub/integration.md`; contract — `protocol-v1.md` + addendum v1.0.1–v1.0.3

Before a session: if the operator reports packets in `docs/group/inbox/` — skill **`sync`** (outbox→inbox delivery is manual; see `docs/group/OPERATOR-HANDOFF.md`).

On SQLite schema or data format changes — see `.cursor/rules/bump-indexer-version.md` (manual bump of `INDEXER_VERSION` in `shared/indexer_version.py`).

For admin/CLI/sync work under Admin Hub — follow `docs/admin-hub/integration.md` and addendum v1.0.1; MCP tools remain the read-only query plane.

Handoff reports for other teams are ephemeral (`HANDOFF-*.md` in repo root, not in git); integration canon only in `docs/admin-hub/`. See `.cursor/rules/cross-team-handoff.mdc`.

Structure check: `python scripts/project-doctor.py --type Sub`.
