## Agent hints

Полный контекст проекта — в `docs/`:

- начать с `docs/agent-onboarding.md`
- затем `docs/README.md` (оглавление)
- открытый backlog: `docs/todo.md` — идеи и невыполненные доработки; по запросу проверять готовность, не реализовывать без явной команды
- Admin Hub protocol (направление интеграции модуля): `docs/admin-hub/integration.md`; контракт — `docs/admin-hub/protocol-v1.md` + addendum v1.0.1 + v1.0.2

При изменениях схемы БД или формата данных в SQLite — см. `.cursor/rules/bump-indexer-version.md` (ручной бамп `INDEXER_VERSION` в `shared/indexer_version.py`).

При доработках admin/CLI/sync под Admin Hub — следовать `docs/admin-hub/integration.md` и addendum v1.0.1; MCP tools остаются read-only query plane.

Handoff-отчёты для других команд — эпиhemeral (`HANDOFF-*.md` в корне, не в git); канон интеграции только в `docs/admin-hub/`. См. `.cursor/rules/cross-team-handoff.mdc`.

