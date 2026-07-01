## Agent hints

**Роль:** Sub (subordinate) · группа `1c-cursor` · Head: `1c-admin-tool` (`C:/projects/1c-admin-tool`).

**Субагенты и skills:** `.cursor/agents/` — **2** (`doc-librarian`, `group-sync-arbitrator`); `.cursor/skills/` — **9** (в т.ч. `canon-align`, `process-group-inbox` — только skills, не agents).

Полный контекст — в `docs/`:

1. `docs/agent-onboarding.md` — политики и тип проекта
2. `docs/todo.md` — backlog и необработанные пакеты в inbox
3. `docs/architecture.md` — поток данных и компоненты
4. `docs/README.md` — оглавление и доменные спеки
5. `docs/group/integration.md` — связь с Head, состояние протокола
6. Admin Hub: `docs/admin-hub/integration.md`; контракт — `protocol-v1.md` + addendum v1.0.1–v1.0.3

Перед сессией: если в `docs/group/inbox/` есть пакеты — skill `process-group-inbox`.

При изменениях схемы БД или формата данных в SQLite — см. `.cursor/rules/bump-indexer-version.md` (ручной бамп `INDEXER_VERSION` в `shared/indexer_version.py`).

При доработках admin/CLI/sync под Admin Hub — следовать `docs/admin-hub/integration.md` и addendum v1.0.1; MCP tools остаются read-only query plane.

Handoff-отчёты для других команд — эпиhemeral (`HANDOFF-*.md` в корне, не в git); канон интеграции только в `docs/admin-hub/`. См. `.cursor/rules/cross-team-handoff.mdc`.

Проверка структуры: `python scripts/project-doctor.py --type Sub`.
