## MCP tools

### Базовые правила использования

- **Не ориентируйтесь на имя MCP-подключения** в IDE: оно может не совпадать с названием проекта/сервера. Ориентируйтесь на доступные tools и на фактический вывод `active_databases`.
- Начинайте с `active_databases`: он возвращает список проектов и баз, из которых выбирается `project_filter` (обязателен для большинства инструментов). У каждой базы в структуре ответа есть флаги `is_outdated` (несовпадение `PRAGMA user_version` с текущим `INDEXER_VERSION`) и `is_updating` (идёт пересборка через `admin_tool`); поле `last_updated_at` (ISO-8601 UTC, mtime файла `.db` после последней успешной сборки) или `null`, если файла нет; в текстовом ответе дата в формате `DD.MM.YYYY HH:MM` и метки `[!] устарела` / `[!] обновляется`. Базы с флагами устаревания/сборки **не участвуют** в остальных tools — дождитесь окончания сборки и снова вызовите `active_databases`.
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
- **Типы реквизитов формы:** `get_form_structure` → массив `types[]` у реквизитов и колонок (как у metadata); колонки ValueTable/AdditionalColumns — `columns[].types[]`, `columns[].table` для AdditionalColumns. См. [`form-type-system.md`](form-type-system.md).
- **Поиск по коду модуля команды**: `search_code`; для `CommandModule` команды объекта в результатах есть `command_name`, в текстовой строке локации показывается `…CommandModule.<имя_команды>`; для `CommonCommand` — `CommonCommand.<Имя>.CommandModule`.

### Регламентные задания (`ScheduledJob`)

- **Список:** `list_objects(object_type="ScheduledJob")`.
- **Поиск по имени или синониму:** `find_object(name="...")` (частичное совпадение по `metadata_objects.name` или `synonym`). `get_object_structure` разрешает объект по имени или синониму (точное и частичное).
- **Детали:** `get_object_structure` → `method_name`, `use`, `predefined`, `restart_count_on_failure`, `restart_interval_on_failure`, `key`, `description`.
- **Процедуры общих модулей:** `get_module_procedures` для `CommonModule` — у процедур, на которые ссылается `MethodName` регл. задания, поле `used_in_scheduled_job: true` (в тексте — пометка `[регл. задание]`).
- После изменений — пересоздать БД через `admin_tool`.

### BusinessProcess: точки маршрута

- Источник: `BusinessProcesses/<Имя>/Ext/Flowchart.xml` (не основной `.xml` объекта).
- **`get_object_structure`** для `BusinessProcess` добавляет:
  - `route_points` — `{name, type, synonym, uuid, true_port?, false_port?}` (type: Start, Activity, Condition, Completion, Split, Join, …);
  - `route_transitions` — `{from, to, from_port?, title?}`.
- В **текстовом ответе MCP**: компактный индекс точек по типам и **adjacency list** переходов (полный граф, включая Split/Join). Подписи веток условий — из `title` линии или «Да»/«Нет» по портам Condition.
- После изменений схемы — пересоздать БД через `admin_tool` (актуальный `INDEXER_VERSION` в `shared/indexer_version.py`, сейчас **10**).

### Type system (фаза 1 — реализовано)

Спека: [`dependency-layer.md`](dependency-layer.md).

**Приоритет для агента:** для ссылочных типов использовать `get_object_structure` (исходящие типы), не `search_code`.

- **`get_object_structure`** — у реквизитов, измерений, ресурсов и колонок ТЧ массив **`types`**:
  - `{ "kind": "object", "object_type": "Catalog", "name": "…", "synonym": "…" }`
  - `{ "kind": "primitive", "base_type": "Number", "qualifiers": { "digits": 10, "fraction": 2 } }`
  - составной тип — несколько элементов в `types`.
- **`find_attribute`** — поле **`types`** вместо строки `attribute_type`.
- **`list_objects` / `find_object`** — только `ConfigObject`; `TypeDescriptor` (примитивы) не показываются. `find_object` ищет по **имени и синониму** объекта.

**Не материализуются (MVP):** `DefinedType`, `AnyRef`, безымянный `TypeSet`.

### Обратный поиск (`find_referencing_objects`, фазы 2–3 — реализовано)

Спека: [`dependency-layer.md`](dependency-layer.md).

**Приоритет для агента:** «кто ссылается на этот справочник/документ» — `find_referencing_objects`, не `search_code`.

- **`find_referencing_objects(object_name, project_filter, …)`** — обратный поиск через `metadata_type_slots` и `metadata_relations`:
  - metadata: реквизиты (`via: attribute`), колонки ТЧ (`via: tabular_section_column`);
  - формы: реквизиты формы (`via: form_attribute`), колонки реквизита формы (`via: form_attribute_column`);
  - подсистемы: объект в Content (`via: subsystem_member`, поле `source_name` — строка `Type.Name`).
- **`object_name`** — имя или синоним целевого объекта (как в `find_object` / `get_object_structure`).
- **`max_results`** — лимит записей на базу (по умолчанию 100); при обрезке — `is_truncated: true`.
- **`relation_kinds`** — фильтр `relation_kind` в `metadata_relations` (например `subsystem_member`); слоты metadata/форм всегда включаются. Пусто — все виды связей.
- Роли, подписки — после фаз 4–5; ФО — **`get_functional_options`**.

Исходящие ссылки отдельным tool **не** планируются — покрываются **`get_object_structure`**.

### Планируемые tools (relations, фазы 4+)

Спека: [`dependency-layer.md`](dependency-layer.md); роли и RLS — [`roles-layer.md`](roles-layer.md).

- **Фаза 4 (роли):** `find_role`, `list_roles`, `get_role_rights` (merge main+ext), `find_roles_for_object`; `role_grant` в `find_referencing_objects`.
- **`metadata_relations`** в `find_referencing_objects` — подписки (фаза 5).
- **`find_relation_path`** — позже, обход с `depth > 1`.

ФО — по-прежнему **`get_functional_options`**; в общий graph **не** дублировать.

