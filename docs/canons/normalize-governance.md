# Канон: нормализация

Версия: **1.2.0** (canon 2.2.0)

Нормализация — приведение репозитория к **структуре роли** (S / H / Sub) по канонам Workspace improve.

Выполняет **агент целевого репозитория** (initiator или skill `normalize-project`). WI — источник канонов и шаблонов; правки в чужой репозиторий из WI не делаются.

---

## Процедура

1. Уточнить роль **S | H | Sub** и путь к WI (`WORKSPACE_IMPROVE`).
2. Прочитать каноны **по роли** (не весь каталог целиком):
   - **S:** `normalize-governance.md`, `project-structure.md`, `normalize-merge.md`, `documentation.md`
   - **H / Sub:** то же + `group-sync.md`
3. Чеклист целевого состояния: `<WI>/normalize.bundle.yaml`.
4. Привести репозиторий к чеклисту: docs, `docs/canons/`, `.cursor/`, скрипты по роли — с учётом того, что уже есть в проекте.
5. Шаблоны брать из `<WI>/templates/` (чтение и материализация, не зеркало каталога).
6. **Документация:** привести entry-point docs к канону через skill **`maintain-docs`** → subagent **`doc-librarian`**. Не делать массовые правки docs в родительском чате.
7. `docs/normalize-record.md`, `project-doctor`, отчёт.

При неоднозначности — спросить.

---

## Материализация `.cursor/`

Skills и agents по списку роли в `normalize.bundle.yaml`. Адаптировать под репо: id модуля, пути head, локальные ссылки.

Agents копировать **только** из `<WI>/templates/agents/<name>.md` → `.cursor/agents/<name>.md` (полный файл). Не использовать stub-файлы из WI `.cursor/agents/`.

---

## Утилиты (по роли, в `scripts/`)

| Скрипт | Назначение |
|--------|------------|
| `project-doctor.py` | Проверка структуры |
| `sync-relay.py` | Доставка пакетов H↔Sub |
| `protocol-snapshot.py` | Baseline протокола (H/Sub) |
| `sync-status.py` | Сводка состояний группы |

---

## Повторная нормализация

Тот же цикл: актуальные каноны WI → обновление локальной копии в репо.
