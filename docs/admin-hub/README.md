## Admin Hub — документация интеграции

Материалы о приведении **1C Config MCP** к протоколу единой админки экосистемы 1С AI tooling.

### Назначение

Этот каталог фиксирует **направление разработки** модуля как managed tool: control plane (Admin Hub) + data plane (этот репозиторий). Реализация протокола — поэтапно, без big bang rewrite.

### Документы

| Документ | Для кого | Содержание |
|----------|----------|------------|
| [`integration.md`](integration.md) | разработчики и агенты **этого репо** | принципы, текущее состояние, roadmap, ownership для config-mcp |
| [`protocol-v1.md`](protocol-v1.md) | все модули экосистемы | Consolidated Protocol v1 (общий контракт) |
| [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) | все модули экосистемы | JSON-схемы, discovery, exit codes, sync |
| [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md) | все модули экосистемы | Phase 2/3: reconcile, sourcePath, IDs, followUpOperations (приоритет над v1.0.1) |
| [`protocol-v1.0.3-addendum.md`](protocol-v1.0.3-addendum.md) | все модули экосистемы | UTF-8 JSON I/O для CLI stdout/input (приоритет над v1.0.2) |
| [`../hub-sync/`](../hub-sync/) | Hub + config-mcp | согласованный mapping registry (2026-06-28); операционный канон — `integration.md` § «Согласованный mapping» |

### Порядок чтения

1. `integration.md` — что делать **в этом репозитории**.
2. `protocol-v1.md` + addendum v1.0.1 + v1.0.2 + v1.0.3 — полный контракт.

### Связь с backlog

Задачи по протоколу — в [`../todo.md`](../todo.md) (секция «Admin Hub protocol»). Не начинать реализацию без явного запроса.
