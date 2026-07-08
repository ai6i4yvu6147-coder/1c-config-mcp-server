# Operator handoff — учётные данные и деплой

Human-tier — русский OK. В хаб-модели (canon 2.5.0) синхронизация протокола идёт через `GROUP-HUB.md` — оператор **не копирует пакеты** между репозиториями. За оператором остаются только вещи вне контекста агента: учётные данные и деплой.

---

## Репозитории группы

| Роль | Репозиторий | Путь |
|------|-------------|------|
| Head | `1c-admin-tool` / `1c-config-admin-tool` | `C:/projects/1c-admin-tool` · `C:/repo/1c-config-admin-tool` |
| Sub `1c-config-mcp` | `1c-config-mcp` / `1c-config-mcp-server` | `C:/projects/1c-config-mcp` · `C:/repo/1c-config-mcp-server` |

Хаб: `C:/projects/1c-admin-tool/GROUP-HUB.md` · `C:/repo/1c-config-admin-tool/GROUP-HUB.md`. Sub resolves via `head.paths` в `group.manifest.yaml`.

---

## Учётные данные (не в контексте агента)

| Что | Где хранится | Кто выдаёт |
|-----|--------------|-----------|
| Transport / deploy creds | secrets store (operator) | оператор |

Агент работает только с локальными хранилищами; секреты в контекст агента не попадают.

---

## Деплой / релиз

| Шаг | Команда / действие | Ответственный |
|-----|--------------------|---------------|
| Portable build | `build_all.bat` | оператор / разработчик |
| MCP reconnect | обновить путь к exe в конфиге IDE после переноса portable | оператор |

---

## Подсказка

```powershell
python scripts/sync-status.py --repo .
```
