## База данных (SQLite)

### Главное правило проекта: NO_DB_MIGRATIONS

В этом проекте **никогда** не пишутся:

- миграции схемы существующих файлов `databases/*.db`;
- конвертации данных из «старых» БД в «новые»;
- любые скрипты «обновления» БД «на месте».

Причина: базы считаются производным артефактом от выгрузки 1С и после изменений парсера/схемы **всегда пересоздаются** через `admin_tool`.

### Версия формата индекса (`INDEXER_VERSION`)

- Константа: `shared/indexer_version.py` → `INDEXER_VERSION` (целое число).
- При успешном создании/обновлении базы через `admin_tool` в файл `.db` записывается **`PRAGMA user_version = INDEXER_VERSION`** (см. `DatabaseManager.create_database` в `admin_tool/db_manager.py`).
- Это **не миграция**: только маркер «под какой формат собрана база». Старые базы с меньшим `user_version` или с `0` считаются устаревшими для текущего сервера; их нужно пересобрать через админку (как и при любых несовместимых изменениях схемы).
- **Когда увеличивать `INDEXER_VERSION`** (вручную, в том же коммите, что и изменение): см. `.cursor/rules/bump-indexer-version.mdc` и docstring в `shared/indexer_version.py`.
- В GUI админки и в ответе MCP `active_databases` показывается, что база устарела (сравнение с текущим `INDEXER_VERSION`).

### Сборка и блокировка MCP

Пересоздание базы в `admin_tool` (GUI) идёт **во временный файл** `foo.db.tmp` с sidecar-маркером `foo.db.building` (см. `shared/db_build_state.py`). После успешной сборки — атомарная подмена `os.replace(tmp, db)`; при ошибке старая `foo.db` сохраняется.

Пока активен маркер `.building`, MCP **не использует** эту базу в query-tools и помечает её `is_updating` в `active_databases`. Это не меняет `INDEXER_VERSION` и не требует пересборки portable-сервера.

### Как БД создаётся

Модуль: `admin_tool/db_manager/` (пакет: `core.py` — жизненный цикл соединения и атомарная сборка, `schema.py` — DDL, `insert_objects.py`/`insert_forms.py` — вставка, `relations.py` — `metadata_relations`)

- `build_from_xml_atomic` — маркер → сборка в `.db.tmp` → подмена целевого `.db`;
- создаётся схема таблиц;
- загружаются метаданные, формы, модули;
- код модулей индексируется через FTS5 (`code_search`);
- последним шагом выполняется `ANALYZE` — без `sqlite_stat1` планировщик на многогигабайтной базе выбирает `SCAN` там, где индекс дешевле (на ЕРП 3.3 ГБ сам `ANALYZE` — 1.8 c).
- **Пропущенные формы (P-2):** если парсинг конкретной формы падает с исключением, она пропускается (не попадает в индекс), но количество пропусков считается (`parser.skipped_forms`) и выводится через `progress_callback` (видно в build-логе GUI), а не только в stdout `print`, который в GUI-режиме никто не видит.

### Что хранится (в общих чертах)

- `metadata_objects`: объекты метаданных (uuid, тип, имя, синоним, комментарий, принадлежность для расширений).
- `object_commands`: команды **объектов** метаданных (не `CommonCommand`): имя, синоним, uuid, принадлежность; связь с родителем `object_id` → `metadata_objects`.
- `forms` + таблицы форм: свойства/реквизиты/команды/события/элементы UI. **`form_entity_properties` (EAV, v12):** свойства реквизитов, колонок и UI-элементов — см. [`form-entity-model.md`](form-entity-model.md); `INDEXER_VERSION` **12**, пересборка БД. **v15 (A-1/P-1):** flatten-фильтр убирает структурный шум (`AdditionSource`) и схлопывает локализованные строки (`item.lang`/`item.content` → одно значение) на входе — на выгрузке Трансгаз/ТД_ОперативныйУчет строк EAV стало на ~10% меньше (22 314 → 20 148); частичные индексы на горячих путях (A-2, см. `ix_fep_path_*`/`ix_fep_name_querytext` в `admin_tool/db_manager/schema.py`).
- `modules`: код модулей объектов, модулей форм и **модулей команд** (`module_type = 'CommandModule'`). Для модуля команды объекта задаётся `command_id` → `object_commands`; для модуля общей команды (`CommonCommand`) — `command_id IS NULL` (модуль «самого» объекта).
- `form_items`: identity + tree (`name`, `item_type`, `parent_id`); свойства UI — в `form_entity_properties` (`entity_kind=item`).
- `module_procedures`: индекс процедур/функций (границы строк) для адресного извлечения кода; колонка `used_in_scheduled_job` — процедура указана в `MethodName` хотя бы одного регл. задания.
- `scheduled_jobs`: свойства регламентных заданий (`method_name`, `use`, `predefined`, `restart_count_on_failure`, `restart_interval_on_failure`, …); связь с объектом через `object_id` → `metadata_objects`.
- `code_search` (FTS5): полнотекстовый поиск по коду модулей. External content над `modules`, индексируется **ровно одна** колонка — `code`. Служебные поля в FTS не кладутся: `MATCH` без имени колонки ищет по всем, и `module_type`/`object_name` давали совпадения-призраки, съедавшие лимит выдачи ещё до проверки релевантности; плюс `object_name` в `modules` нет вовсе, из-за чего `rebuild`/`snippet()`/`highlight()` падали с `no such column` (v22, аудит 2026-08 A-6/A-7). Имя объекта и тип модуля берутся джойном к `modules`/`metadata_objects`.
- `fo_content_ref`, `fo_form_usage`: привязки функциональных опций (уже есть).
- **Type system (фаза 1 + формы):** см. [`dependency-layer.md`](dependency-layer.md), [`form-type-system.md`](form-type-system.md):
  - `metadata_objects`: `object_kind` (`ConfigObject` | `TypeDescriptor`), `is_primitive`, `base_type`, `qualifier_1..3` для синтетических примитивов и form-wrappers (`ValueListType`, `ValueTable`, `DynamicList`);
  - `metadata_type_slots` — типы реквизитов/колонок ТЧ, **реквизитов/колонок форм** (`source_table`: `attributes`, `tabular_section_columns`, `form_attributes`, `form_attribute_columns`) и **состава DefinedType** (`source_table`: `metadata_objects`, `source_row_id` = id объекта DefinedType);
  - `form_attribute_columns` — колонки ValueTable / AdditionalColumns (имя, заголовок, `table_context`); в обзоре формы не перечисляются — drill-down через `get_form_attribute` + `column_name` (spec);
  - **Form properties (v12):** [`form-entity-model.md`](form-entity-model.md) — `form_entity_properties`, overview profiles, `get_form_attribute` / `get_form_item`; ФО на колонках — `fo_form_usage` с `element_type=FormAttributeColumn` и `parent_element_name`;
  - **v16:** `DefinedType` в whitelist; состав типа в `metadata_type_slots`; фикс дублей реквизитов регистров (см. `CHANGELOG.md`).
  - `metadata_relations` — структурные связи (`subsystem_member` для подсистем; роли — `role_grants`, фаза 4);
  - **Роли (фаза 4):** `role_settings`, `role_grants`, `role_access_restrictions`, `role_restriction_templates`; `index_metadata` (`config_name`, `extension_purpose`, `source_db_name`) — см. [`roles-layer.md`](roles-layer.md).

### Где к БД обращаются

- MCP runtime: `server/tools.py` (чтение)
- Admin tool: `admin_tool/db_manager.py` (создание/пересоздание)

