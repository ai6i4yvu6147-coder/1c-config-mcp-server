## Документация проекта

Цель этой папки — дать **структурированный контекст** (для ИИ и разработчиков), не раздувая корневые README.

### С чего начать (порядок чтения)

1. `agent-onboarding.md` — быстрый контекст + политики проекта (самое важное), включая порядок источников при работе с парсером (выгрузка перед внешними спеками).
2. `todo.md` — **невыполненные задачи и идеи** по функционалу сервера (живой backlog в git), включая необработанные пакеты в `group/inbox/`.
3. `architecture.md` — как устроен поток данных и какие части кода за что отвечают.
4. `mcp-tools.md` — какие инструменты MCP есть и как ими пользоваться.
5. `database.md` — что хранится в SQLite (и почему **нет миграций**).
6. `metadata-whitelist.md` — текущий whitelist типов метаданных и как добавлять новые.
7. `dependency-layer.md` — type system (metadata + формы **готово**), `find_referencing_objects` (**готово**), подсистемы в `metadata_relations` (фаза 3 **готово**); роли и подписки — фазы 4–5 в backlog.
8. `form-type-system.md` — спека type system форм (**готово**, v9): эталоны, решения, критерии MCP-проверки.
9. `testing-protocol.md` — как здесь принято проверять изменения на «боевом» MCP.
10. `performance.md` — заметки по узким местам и подходу к оптимизациям.

### Admin Hub (интеграция с единой админкой)

11. [`admin-hub/README.md`](admin-hub/README.md) — оглавление раздела.
12. [`admin-hub/integration.md`](admin-hub/integration.md) — направление разработки **этого модуля** (principles, roadmap).
13. [`admin-hub/protocol-v1.md`](admin-hub/protocol-v1.md) + addendum [v1.0.1](admin-hub/protocol-v1.0.1-addendum.md) + [v1.0.2](admin-hub/protocol-v1.0.2-addendum.md) + [v1.0.3](admin-hub/protocol-v1.0.3-addendum.md) — протокол экосистемы.

### Группа (Sub, 1c-cursor)

14. [`group/integration.md`](group/integration.md) — связь с Head (`1c-admin-tool`), состояние протокола, локальные отклонения.
15. [`canons/README.md`](canons/README.md) — локальная копия канонов Workspace improve 2.2.0.

