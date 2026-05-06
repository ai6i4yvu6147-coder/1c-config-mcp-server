## MCP tools

### Базовые правила использования

- **Не ориентируйтесь на имя MCP-подключения** в IDE: оно может не совпадать с названием проекта/сервера. Ориентируйтесь на доступные tools и на фактический вывод `active_databases`.
- Начинайте с `active_databases`: он возвращает список проектов и баз, из которых выбирается `project_filter` (обязателен для большинства инструментов). У каждой базы в структуре ответа есть флаг `is_outdated` (несовпадение `PRAGMA user_version` с текущим `INDEXER_VERSION`); в текстовом ответе устаревшие базы помечены суффиксом `[!] устарела`.
- `project_filter` должен быть точным именем проекта из `active_databases`.
- `extension_filter` (если используется) — точное имя базы из `active_databases` (основная/расширение).

### Где описаны инструменты в коде

- Регистрация/описание схем: `server/server.py`
- Реализация: `server/tools.py`

### Важные особенности

- `search_code` использует FTS5 для «обычных» запросов и переключается на `LIKE`, если в запросе есть спецсимволы или включены дополнительные фильтры (например, `object_name`, `module_type`).
- Чтобы ограничивать объём выдачи и нагрузку, в `search_code` есть лимит числа модулей на одну базу (`MAX_MODULES_SEARCH_CODE` в `server/tools.py`).

### Команды объектов и общие команды (`CommandModule`)

- **Список команд объекта** (не `CommonCommand`): `get_object_structure` → поле `commands` (`name`, `synonym`, `has_module`). Поле `modules` в этом ответе — только «обычные» модули объекта (`Module` / `ManagerModule` / `ObjectModule`), без модулей команд.
- **Код модуля команды объекта**: `get_module_code` с `module_type="CommandModule"` и **`command_name`** = имя команды из `commands`.
- **Общая команда** (`CommonCommand` в whitelist): в `get_object_structure` у объекта в `modules` будет `CommandModule`; `get_module_code` / `get_module_procedures` / `get_procedure_code` с `module_type="CommandModule"` **без** `command_name`.
- **Кнопка и привязка к команде на форме**: `get_form_structure` → у элементов `items` поля `command_name` (как в XML) и `command_source` (`Form` / `Object` / `Common`, по префиксу строки). В текстовом ответе MCP к строке элемента добавляются пометки вида `[команда объекта: …]`.
- **Поиск по коду модуля команды**: `search_code`; для `CommandModule` команды объекта в результатах есть `command_name`, в текстовой строке локации показывается `…CommandModule.<имя_команды>`; для `CommonCommand` — `CommonCommand.<Имя>.CommandModule`.

