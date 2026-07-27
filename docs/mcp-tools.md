## MCP tools

> **Аудитория этого файла — разработчик сервера:** здесь внутренности (где что лежит в коде,
> лимиты, версии индексатора, спеки). Справка **для агента-потребителя** — отдельный файл
> [`agent-guide.md`](agent-guide.md): он зашивается в portable и отдаётся тулом `guide`.
> Появился новый тул — строку про него надо добавить в карту инструментов `agent-guide.md`,
> иначе `tests/test_agent_guide.py` покраснеет.

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
- **Поиск по `QueryText` DynamicList (T-5).** `search_code` дополнительно ищет совпадения в тексте запроса форм (EAV `property_name='QueryText'`, результат `match_kind='form_query'`). Этот поиск пропускается, если `module_type` задан и не равен `FormModule` (QueryText — свойство формы, а не модуля, нерелевантно при сужении к конкретному типу модуля), и ограничен тем же лимитом `MAX_MODULES_SEARCH_CODE`, что и поиск по модулям.

### Единый контракт и экономия ответов (аудит T-1–T-6)

- **Формат ответов — единый текст (T-3).** Все tools (включая role-tools `find_role`, `list_roles`, `get_role_rights`, `find_roles_for_object`) возвращают форматированный текст (`📁 Проект / └─ база`, маркеры, пометки `[слой: …]`, `(запрещено)`, `⚠`, усечения `N из M`), а не JSON. Поля данных прежние — изменился только рендеринг.
- **`get_object_structure`** для широких объектов ограничивает списки реквизитов/измерений/ресурсов: `max_attributes` (по умолчанию 50; `0` — без лимита). При обрезке в ответе — `<section>_total_count` и `is_truncated`, в тексте «показаны N из M … увеличьте max_attributes или find_attribute». Параметр `sections` (`attributes`, `dimensions`, `resources`, `tabular_sections`, `enum_values`, `commands`, `forms`, `modules`, `route_points`) возвращает только указанные секции. Точечный поиск реквизита — `find_attribute`.
- **`get_form_item` / `get_form_attribute`** по умолчанию **курируют** свойства EAV (`verbose=false`): скрыт служебный шум (`*.item.lang`, пустые значения, неустановленные даты), локализованные строки схлопнуты (`ToolTip.item.content` → `ToolTip`), профильные свойства элемента — первыми; у реквизита-DynamicList `Settings.Field.*` не дублируются в `properties` (они в индексе колонок). Полный дамп EAV — `verbose=true`. Число скрытых строк — в пометке `(+N служебных свойств скрыто)`.
- **`search_form_properties`** ищет UI-элементы по **любому** `property_path` из EAV (не только `Visible`/`Enabled`): `value_match=exact|contains`, лимит `max_results` (по умолчанию 100) с `total_count`/`is_truncated`. Регистронезависимое сравнение по кириллице — через Unicode-функцию `py_lower` на соединении.
- **Тип не резолвится → явная пометка (P-3).** Пустой `<Type/>` и прочие нерезолвленные случаи показывают `(тип не определён)`. **`cfg:DefinedType.X`** резолвится с `INDEXER_VERSION` **16** (объект в индексе) → `DefinedType.Имя` в `get_object_structure` / `find_attribute` / формах. Bare платформенные типы (`v8:Color`, `pl:Planner`, …) — см. [`form-type-system.md`](form-type-system.md).
- **Схема `active_databases` подрезана (T-6).** Описание инструмента избавлено от повторяющегося перечисления синонимов «список проектов»; поведение и параметры не изменились.

### Команды объектов и общие команды (`CommandModule`)

- **Список команд объекта** (не `CommonCommand`): `get_object_structure` → поле `commands` (`name`, `synonym`, `has_module`). Поле `modules` в этом ответе — только «обычные» модули объекта (`Module` / `ManagerModule` / `ObjectModule`), без модулей команд.
- **Код модуля команды объекта**: `get_module_code` с `module_type="CommandModule"` и **`command_name`** = имя команды из `commands`.
- **Общая команда** (`CommonCommand` в whitelist): в `get_object_structure` у объекта в `modules` будет `CommandModule`; `get_module_code` / `get_module_procedures` / `get_procedure_code` с `module_type="CommandModule"` **без** `command_name`.
- **Кнопка и привязка к команде на форме**: `get_form_structure` → у элементов `items` поля `command_name` (как в XML) и `command_source` (`Form` / `Object` / `Common`, по префиксу строки). В текстовом ответе MCP к строке элемента добавляются пометки вида `[команда объекта: …]`.
- **Типы реквизитов формы:** `get_form_structure` → массив `types[]` у реквизитов (колонки ValueTable / поля DynamicList в обзоре **не перечисляются** — только счётчик и подсказка drill-down; см. spec). См. [`form-type-system.md`](form-type-system.md), [`form-entity-model.md`](form-entity-model.md) §3.2.
- **Поиск по коду модуля команды**: `search_code`; для `CommandModule` команды объекта в результатах есть `command_name`, в текстовой строке локации показывается `…CommandModule.<имя_команды>`; для `CommonCommand` — `CommonCommand.<Имя>.CommandModule`.

### Form entity model (v12)

Спека: [`form-entity-model.md`](form-entity-model.md). `INDEXER_VERSION` **12** — пересборка БД.

**Workflow:**

1. **`get_form_structure`** — обзор: типы, дерево элементов **без** дочерних колонок у `Table`; реквизиты DynamicList/ValueTable — `types[]`, подсказки (`QueryText: present (N chars)`, `columns: N`).
2. **`get_form_attribute`** (`attribute_name`; опционально **`column_name`**) — полный `Settings.QueryText`, EAV-свойства, индекс колонок/полей.
3. **`get_form_item`** (`element_name`; опционально **`column_name`**) — свойства контейнера + индекс колонок UI; с `column_name` — дочерний элемент колонки.
4. **`search_code`** — также ищет фрагмент в `Settings.QueryText` → подсказка `get_form_attribute`.
5. **`get_functional_options`** — `element_type=FormAttributeColumn` (нужны `attribute_name` + `column_name`).

### СКД / схемы компоновки данных (dcs-schema-indexing, `INDEXER_VERSION` 17 — пересборка БД)

Спека: [`dcs-schema-indexing.md`](dcs-schema-indexing.md). Симметрия с формами: `get_dcs_schema` — что `get_form_structure` для формы. СКД крепится **не только к отчётам** (тысячи схем на Catalog/Document/регистрах; часто встроенное правило отбора/выборки для BSL — см. shape-hint `has_query`).

- **`get_dcs_schema`** (`object_name`, `project_filter` обязателен; опц. `template`, `extension_filter`) — семантический документ схемы: наборы (текст запроса, поля с ролями измерение/баланс/период), параметры, вычисляемые/итоговые поля, сводка вариантов настроек. Без `template` — обзор всех схем объекта (shape-hints `dataset_count`/`field_count`/`has_query`/`has_grouping`/…); полный документ отдаётся, когда цель одна (или указан `template`).
- **`search_code` по тексту запроса СКД** — текст запроса набора индексируется как `module_type='DcsQuery'` (Срез 1), `object_name = <Объект>.<Шаблон>`. Сужение `module_type='DcsQuery'` — только СКД-запросы. Схемы без `<query>` (правила отбора каталогов) в FTS не попадают (документ второго среза всё равно сохраняется).
- Хранение: `dcs_schema` (blob `schema_json` + денормализованные shape-hints), ключ `(object_id, template_name)`; MXL-макеты отсеиваются (`TemplateType != DataCompositionSchema`) — отдельный трек.

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
- После изменений схемы — пересоздать БД через `admin_tool` (актуальный `INDEXER_VERSION` в `shared/indexer_version.py`, сейчас **16**).

### Type system (фаза 1 — реализовано)

Спека: [`dependency-layer.md`](dependency-layer.md).

**Приоритет для агента:** для ссылочных типов использовать `get_object_structure` (исходящие типы), не `search_code`.

- **`get_object_structure`** — у реквизитов, измерений, ресурсов и колонок ТЧ массив **`types`**:
  - `{ "kind": "object", "object_type": "Catalog", "name": "…", "synonym": "…" }`
  - `{ "kind": "primitive", "base_type": "Number", "qualifiers": { "digits": 10, "fraction": 2 } }`
  - составной тип — несколько элементов в `types`.
- **`find_attribute`** — поле **`types`** вместо строки `attribute_type`.
- **`list_objects` / `find_object`** — только `ConfigObject`; `TypeDescriptor` (примитивы) не показываются. `find_object` ищет по **имени и синониму** объекта.

**`DefinedType` (`INDEXER_VERSION` 16):** индексируется как `ConfigObject`. `get_object_structure` → секция «Состав типа» (члены из `Properties/Type`). Ссылки `cfg:DefinedType.X` у реквизитов/измерений/ресурсов и форм → `DefinedType.X` в `types[]`. `find_referencing_objects` — обратный поиск на DefinedType.

**Не материализуются (MVP):** `AnyRef`, безымянный `TypeSet`.

### Обратный поиск (`find_referencing_objects`, фазы 2–4 — реализовано)

Спека: [`dependency-layer.md`](dependency-layer.md).

**Приоритет для агента:** «кто ссылается на этот справочник/документ» — `find_referencing_objects`, не `search_code`.

- **`find_referencing_objects(object_name, project_filter, …)`** — обратный поиск через `metadata_type_slots` и `metadata_relations`:
  - metadata: реквизиты (`via: attribute`), колонки ТЧ (`via: tabular_section_column`);
  - формы: реквизиты формы (`via: form_attribute`), колонки реквизита формы (`via: form_attribute_column`);
  - подсистемы: объект в Content (`via: subsystem_member`, поле `source_name` — строка `Type.Name`);
  - роли: право на объект (`via: role_grant`, JOIN `role_grants` по `parent_object_qname`).
- **`object_name`** — имя или синоним целевого объекта (как в `find_object` / `get_object_structure`).
- **`max_results`** — лимит записей на базу (по умолчанию 100); при обрезке — `is_truncated: true`.
- **`relation_kinds`** — фильтр видов связей (`subsystem_member`, `role_grant`, `attribute`, …); непустой список — только перечисленные `via` (для ролей удобнее `find_roles_for_object`). Пусто — все виды связей.
- Роли (детали прав) — **`get_role_rights`**; подписки — фаза 5; ФО — **`get_functional_options`**.

Исходящие ссылки отдельным tool **не** планируются — покрываются **`get_object_structure`**.

### Роли и RLS (фаза 4 — реализовано)

Спека: [`roles-layer.md`](roles-layer.md).

- **`find_role`** — поиск роли по имени/синониму; `role_qualified_name`, `uuid`, слой, adopted-ссылка.
- **`list_roles`** — список ролей в проекте/базе; `is_truncated` + `total_count`.
- **`get_role_rights`** — центральный tool: `merge=true` (по умолчанию) — эффективное состояние main + расширения; `merge=false` — один слой. Фильтры: `object_name`, `rights`, `rls`, `depth` (`object` / `all`), `include_restriction_text`. Для `ПолныеПрава` и тяжёлых ролей — `response_mode=summary` по умолчанию.
- **`find_roles_for_object`** — обратный поиск ролей с явным grant на объект; `merge=true` — сводка по проекту (main + расширения); `merge=false` — по базам; `admin_roles_note` при наличии `ПолныеПрава`.
- **`active_databases`** — у расширений дополнительно `extension_purpose` (`Customization` / `AddOn` / `Patch`).

После изменений схемы — пересоздать БД через `admin_tool` (актуальный `INDEXER_VERSION` в `shared/indexer_version.py`, сейчас **16**).

### Планируемые tools (relations, фаза 5+)

Спека: [`dependency-layer.md`](dependency-layer.md).

- **Фаза 5 (подписки):** `EventSubscription` в `metadata_relations`.
- **`find_relation_path`** — позже, обход с `depth > 1`.

ФО — по-прежнему **`get_functional_options`**; в общий graph **не** дублировать.

