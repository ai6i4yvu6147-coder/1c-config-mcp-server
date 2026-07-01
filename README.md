# 1C Config MCP Server

Для ИИ и разработчиков: см. [`docs/`](docs/) (начать с [`docs/agent-onboarding.md`](docs/agent-onboarding.md)). Admin Hub: [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md). Краткий контекст для ИИ: [`README_AI.md`](README_AI.md).

Инструмент для работы с конфигурациями 1С через ИИ-ассистент с поддержкой MCP: анализ кода, поиск объектов, структура метаданных.

**Важно:** базы всегда пересоздаются, миграций нет.

## Быстрый старт

1. Сборка: `build_all.bat` → portable с `Server/`, `Admin/`, `Tools/`.
2. `Admin/1C-Config-Admin.exe` → проект → база → путь к `Configuration.xml` из выгрузки.
3. MCP: в конфиг клиента добавить command на `Server/1c-config-server.exe` внутри portable-папки.
4. Инструменты: `active_databases`, `list_objects`, `search_code`, `get_object_structure`, …

## Структура проекта (исходники)

| Каталог / файл | Назначение |
|----------------|------------|
| `admin_tool/` | GUI и CLI (`admin_tool/cli.py`, Hub protocol) |
| `server/` | MCP-сервер |
| `shared/` | парсер XML, ProjectManager, hub_protocol |
| `docs/admin-hub/` | интеграция managed tool с Admin Hub |
| `docs/group/` | синхронизация с группой `1c-cursor` (Sub) |
| `projects.example.json` | пример runtime-конфига portable |

## Группа и Admin Hub

- **Роль:** Sub · группа `1c-cursor` · Head: `1c-admin-tool`
- **Интеграция:** [`docs/group/integration.md`](docs/group/integration.md)
- **Hub CLI:** `rebuild-index`, `apply-registry`, `status` — см. [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md)

## Портативность

Portable можно переносить. После переноса обновите путь к exe в конфиге MCP-клиента и перезапустите ИИ-приложение.

Подробные шаги (MCP config, troubleshooting) — в [`docs/agent-onboarding.md`](docs/agent-onboarding.md) и исторически в git-истории `readme.txt` (удалён при нормализации Sub 2.2.0).
