# Лог доработок

Все доработки сгруппированы по дню. При внесении изменений в код обновляйте этот файл.

**Правило:** одна доработка (фича, исправление, доработка одной области) — один пункт списка. Если правка дополняет или уточняет уже описанную сегодняшнюю доработку (тот же сценарий, та же часть кода), не добавляйте новый пункт — отредактируйте существующий, расширив описание.

---

## 2026-07-03

- **Admin Hub Phase 2 ops (`operations.log`):** append-only JSONL audit trail на `apply-registry`, `rebuild-index`, `rebuild-all`; путь из manifest `paths.operationsLog`; `shared/operations_log.py`; тесты `tests/test_operations_log.py`.

## 2026-07-02

- **Re-normalize 2.4.0 (Sub):** agent-cache tier на English (`agent_docs_lang: en`); каноны WI 2.4.0; skills/agents обновлены из WI templates; deprecations 2.3.0 подтверждены удалёнными; `project-doctor` 2.4.0. Состояние протокола без изменений.

## 2026-07-01

- **Re-normalize 2.3.0 (Sub):** layout 2 agents→1 (`doc-librarian`); skills 9→4 (`normalize-project`, `canon-align`, `maintain-docs`, `sync`); удалён `sync-relay.py`; добавлены `docs/group/OPERATOR-HANDOFF.md`, `docs/group/templates/`; entry-point docs обновлены. Состояние протокола (`stable`, epoch 0, `protocol-ref`) без изменений.

## 2026-06-30

- **Дата последнего обновления базы:** mtime `.db` как `lastUpdatedAt` / `last_updated_at` — Admin GUI (колонка «Обновлена»), MCP `active_databases`, CLI `status` и `export-registry` (`indexStatus`); helper в `shared/index_status.py`.
- **Нормализация Sub (канон 2.2.0):** agent-first по WI; `group.manifest.yaml`, `docs/group/integration.md`, `docs/canons/`, scripts (`project-doctor`, `sync-relay`, `sync-status`, `protocol-snapshot`), 9 skills + 2 agents; `README.md` вместо `readme.txt`; `pyyaml>=6.0` в requirements (без удаления `mcp`/`pyinstaller`); отчёт `normalize-report.md`.

## 2026-06-29

- **Admin Hub Phase 3 (headless rebuild):** CLI `rebuild-index --db-id`, `rebuild-all`, `reconcile-markers`; `--trigger-rebuild` на `apply-registry` → `triggeredRebuilds[]`; `shared/hub_rebuild.py`, `find_database_by_id` в `ProjectManager`; `status --json` — `indexReadiness` на database; тесты `tests/test_hub_rebuild.py`; контракт в `docs/admin-hub/integration.md` § Phase 3 CLI.

## 2026-06-28

- **Согласование registry Hub ↔ config-mcp (2026-06-28):** mapping в [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md) § «Согласованный mapping».
- **Документация Remote Sync E2E:** контекст ConfigAdmin handoff (layout ExportRoot, полный цикл apply→rebuild, симптом «нет базы» после R1) — в [`docs/admin-hub/integration.md`](docs/admin-hub/integration.md); исходный handoff из корня не хранится.
- **Admin Hub protocol v1.0.3 (UTF-8 JSON I/O):** `shared/cli_json.py` (`write_json_stdout` через `stdout.buffer`, `read_json_file` с reject BOM); все `--json` команды CLI; BOM reject на `apply-registry --input`; `cliContract` в manifest example; `docs/admin-hub/protocol-v1.0.3-addendum.md`; тесты `tests/test_cli_json_encoding.py`.
- **Admin Hub Phase 2 (registry sync):** `apply-registry --input … --json` (patch default, snapshot, `removedIds`, atomic write `projects.json`); `shared/registry_apply.py`, `shared/source_path.py`, `shared/registry_ids.py`; `sourcePath`/`sourceKind` (directory → resolve `Configuration.xml`); strict UUID v4 на apply; export/status v1.0.2; `followUpOperations` при смене source; archive на apply — skip + warning (deviation); тесты `tests/test_registry_apply.py`.
- **Документация Admin Hub:** addendum v1.0.2 в `docs/admin-hub/protocol-v1.0.2-addendum.md`; обновлены `integration.md`, README раздела.
- **Admin Hub Phase 1 (read-only protocol):** `shared/runtime_paths.py`, `shared/hub_protocol.py`, `shared/index_status.py`, `admin_tool/cli.py` (`inventory`, `status`, `export-registry --json`); `module.manifest.example.json`; единый resolver путей в `ProjectManager` / MCP server; `build_all.bat` — `Tools/1c-config-cli.exe` и `module.manifest.json` в portable; `schemaVersion` в `projects.example.json`; тесты `tests/test_hub_protocol.py`.
- **Документация Admin Hub:** направление интеграции модуля зафиксировано в `docs/admin-hub/` (`integration.md`, `protocol-v1.md`, `protocol-v1.0.1-addendum.md`); обновлены `docs/README.md`, `architecture.md`, `todo.md` (hub-protocol phase 1–3), `AGENTS.md`, `agent-onboarding.md`. Удалены черновики и дубликаты из корня репозитория (анкеты, концепт, старый protocol draft).

## 2026-06-15

- **Dependency-layer фаза 3: `metadata_relations` + whitelist `Subsystem`:** парсер `_parse_subsystems()` (rglob, квалифицированные имена, `content_refs`, `child_subsystem_names`); таблица `metadata_relations` и `_link_subsystem_relations` при сборке БД; `find_referencing_objects` — UNION слотов и relations, фильтр `relation_kinds`, метка `via: subsystem_member`. `INDEXER_VERSION` увеличен до 10 — базы пересоздать из выгрузки. Тесты `tests/test_xml_parser_subsystem.py`, расширение `tests/test_find_referencing_objects.py`.
- **MCP: `find_referencing_objects` (dependency-layer фаза 2):** обратный поиск по `metadata_type_slots` — metadata (реквизиты, колонки ТЧ) и формы (реквизиты, колонки); метки `via`; `max_results`; helper `_resolve_config_object` для DRY с `get_object_structure`. `INDEXER_VERSION` не менялся. Unit-тесты `tests/test_find_referencing_objects.py`.
- **admin_tool GUI: статус «устарела» после обновления:** обновление дерева проектов и диалогов после сборки БД перенесено в главный поток tkinter через `AdminAppV2.schedule_on_main` (`root.after`); исправлено для создания, быстрого и обычного обновления базы.
- **MCP: поиск объектов по синониму (dependency-layer фаза 0):** `find_object` и `get_object_structure` ищут по `metadata_objects.synonym` (точное и частичное совпадение); `INDEXER_VERSION` не менялся. Unit-тесты `tests/test_find_object_synonym.py`.

## 2026-06-14

- **admin_tool: TypeDescriptor UNIQUE constraint:** нормализация квалификаторов (`None`→`''`, `Number` без fraction→`0`, int→str) и один `MetadataTypeResolver` на сборку; исправлены дубликаты `metadata_objects` при индексации типов.
- **admin_tool: сборка БД на Windows:** WinError 32 при обновлении часто маскировал реальную ошибку сборки (соединение SQLite к `.db.tmp` не закрывалось до удаления файла). `build_from_xml_atomic` — `finally` с гарантированным `close`, безопасная очистка `.tmp`, `journal_mode=DELETE` для временного файла, повторы `os.replace` при WinError 32/5. `reconcile_building_markers` не удаляет `.tmp` активной сборки. GUI показывает исходную ошибку через `format_build_error`.
- **Type system форм (form-type-system):** нормализация типов реквизитов и колонок Form.xml — `_extract_logform_type_slots` (составные типы, TypeSet, Settings/TypeDescription, wrappers ValueListType/ValueTable/DynamicList); таблица `form_attribute_columns`; слоты в `metadata_type_slots` (`form_attributes`, `form_attribute_columns`). Удалены `form_attributes.type` и `columns_json`. `get_form_structure` возвращает `types[]` у реквизитов и колонок (breaking change). `INDEXER_VERSION` увеличен до 9 — базы пересоздать из выгрузки.
- **Type system, фаза 1:** нормализация типов реквизитов и колонок ТЧ — таблица `metadata_type_slots`, синтетические `TypeDescriptor` в `metadata_objects` (`object_kind`, `base_type`, квалификаторы); парсер извлекает структурированные `type_slots` (ссылочные типы, примитивы с квалификаторами, составные); resolver при сборке БД. Колонки `attributes.attribute_type` и `tabular_section_columns.column_type` удалены. `get_object_structure` и `find_attribute` возвращают массив `types` (resolved object/primitive). `list_objects` / `find_object` не показывают `TypeDescriptor`. `DefinedType`, `AnyRef`, безымянный `TypeSet` — пока не материализуются. `INDEXER_VERSION` увеличен до 8 — базы пересоздать из выгрузки.

## 2026-06-10

- **Регламентные задания (ScheduledJob):** тип добавлен в whitelist парсера; таблица `scheduled_jobs`; поиск через `list_objects` / `find_object` / `get_object_structure` (method_name, use, predefined, перезапуск при сбое). В `module_procedures` — колонка `used_in_scheduled_job` (линковка по `MethodName` → `CommonModule.<модуль>.<процедура>`); в `get_module_procedures` — поле `used_in_scheduled_job`. `INDEXER_VERSION` не менялся — базы пересоздать вручную через `admin_tool`.

## 2026-06-08

- **BusinessProcess: точки маршрута в get_object_structure:** парсинг `Ext/Flowchart.xml` — таблицы `bp_route_points`, `bp_route_transitions`; в MCP — `route_points`, `route_transitions` и текстовый adjacency list (индекс точек по типам + переходы с подписями веток Condition). `INDEXER_VERSION` увеличен до 7 — базы пересоздать из выгрузки.

## 2026-06-06

- **Индексация //-аннотаций методов BSL:** парсер `_parse_module_procedures` собирает многострочные документирующие `//`-комментарии перед процедурами/функциями; в таблицу `module_procedures` добавлена колонка `comment`, `start_line` включает блок комментариев (и `&`-директивы). `get_module_procedures` возвращает `comment`; `get_procedure_code` отдаёт код с комментариями. `INDEXER_VERSION` увеличен до 6 — базы пересоздать из выгрузки.

## 2026-05-28

- **Парсер + MCP: CommonForm (общие формы):** `CommonForm` добавлен в whitelist и индексируется как объект с единственной формой `Form.xml` из `CommonForms/<Имя>/Ext/` и модулем `Ext/Form/Module.bsl`. Это делает общие формы доступными в MCP через `list_objects(object_type="CommonForm")`, `find_form`, `get_form_structure`, `get_module_code` после пересоздания БД.
- **Документация (протокол тестирования):** в `docs/testing-protocol.md` и `docs/agent-onboarding.md` уточнено, что проверка должна начинаться с `active_databases` и выполняться через MCP tools, без попыток подменить тест поиском runtime-файлов или локальным запуском кода.

## 2026-05-12

- **Парсер, составные типы:** `_extract_attribute_type` объединяет все значения из нескольких `v8:Type` внутри контейнера `Properties/Type` (составной тип в выгрузке 2.20), плюс по-прежнему `v8:TypeSet` и `ValueType`/`v8:Ref`. Ранее в индекс и `get_object_structure` попадал только первый тип. `INDEXER_VERSION` увеличен до 5 — существующие SQLite-базы нужно пересоздать из выгрузки.
- **Документация для агентов:** в `docs/agent-onboarding.md` и `docs/testing-protocol.md` зафиксирован приоритет реальной выгрузки (путь или фрагмент XML) над внешними источниками при разборе структуры метаданных для парсера.

## 2026-05-06

- **ТЗ MCP: команды объектов метаданных:** добавлено индексирование команд объектов и их `CommandModule.bsl`: таблица `object_commands`, ссылка `modules.command_id`, в `form_items` сохраняется `command_name` (сырое `CommandName` из Form.xml). `CommonCommand` добавлен в whitelist и индексируется как объект с `CommandModule`. MCP tools расширены: `get_object_structure.commands`, `get_module_*`/`get_procedure_code` поддерживают `CommandModule` + `command_name`, `get_form_structure` возвращает `command_name` и резолвит `command_source`, `search_code` показывает `command_name` для модулей команд.
- **Формы: AutoCommandBar:** элементы из `AutoCommandBar` больше не выпадают из `form_items` (парсинг контейнеров `ChildItems`/`Items`), кнопки команд объекта отображаются в `get_form_structure` как `[команда объекта: …]`.
- **Runtime: устаревшие базы:** MCP tools по умолчанию пропускают базы с `user_version < INDEXER_VERSION`, чтобы исключить ошибки вида `no such table/column` после бампов формата.
- **Документация/чистота исходников:** `projects.json` удалён из исходников (runtime‑конфиг), добавлен `projects.example.json`, обновлены формулировки про portable/runtime и процесс тестирования на реальном MCP.

## 2025-03-10

- **ТЗ MCP (реализация плана):** парсер: порядок элементов формы по документу (_parse_child_items — итерация по list(parent_elem)), расширение типов UI (HTMLDocumentField, FormattedDocumentField, FlowchartField, PlannerField, GanttChartField, ExtendedTooltip, SearchControl). Секция Attributes для регистров (парсинг и вставка в БД с section=Attribute). search_code: один запрос module_procedures WHERE module_id IN (...) вместо N+1. Индексы БД: attributes(name), form_items(data_path), tabular_section_columns(column_name). Инвалидация кэша соединений по mtime файла БД; перечитывание runtime-конфига projects.json при изменении mtime в get_active_databases. import json вынесен на уровень модуля в tools.py. list_objects: при отсутствии object_type лимит применяется по каждому типу объектов; find_attribute: объединённый лимит (второй запрос с LIMIT max_results - n). search_form_properties: явный if/else по колонке вместо SQL-конкатенации. Удалены scripts/, docs/, test_projects.json; readme.txt обновлён (актуальная структура, runtime projects.json, без Server/config.json и Admin.bat).
- **MCP 1C (ТЗ анализ и правки):** при несуществующем project_filter инструменты возвращают явную ошибку с перечислением доступных проектов (ValueError в tools.py, обработка в server.py). При нулевом результате search_code по найденному проекту возвращается диагностика (проект, число баз, совпадений: 0) и подсказка вызвать list_active_databases. Описание list_active_databases усилено для дискаверабилити (первый шаг, список проектов, доступные project_filter). Обратная связь: list_active_databases по-прежнему не отображался в клиенте — в inputSchema добавлен опциональный параметр placeholder (не используется), чтобы инструмент не отфильтровывался клиентами, скрывающими инструменты с пустым properties. В Claude (Chrome): переименован в **active_databases**. Позже выяснилось, что tool_search отдаёт инструменты по релевантности запроса, и active_databases не находился по запросам — в description добавлены явные поисковые формулировки: «список проектов», «перечень проектов», «какой project_filter указать», «первый шаг», «search_code find_object», «с чего начать» и др.

---

## 2025-03-05

- **ТЗ модификация MCP:** search_code: max_results трактуется как лимит **на один модуль** (из каждого модуля до max_results сниппетов); число модулей ограничено константой MAX_MODULES_SEARCH_CODE (100). В ответе для каждого совпадения добавлены procedure_display (Функция/Процедура: Имя или «<тело модуля>») и явные идентификаторы для get_procedure_code (object_name, module_type, form_name при FormModule). В server.py вывод дополнен этими полями.
- **ТЗ модификация MCP:** парсер _parse_module_procedures (admin_tool/db_manager.py) доработан для многострочных объявлений Процедура/Функция (закрывающая скобка и Экспорт на следующих строках); такие методы попадают в module_procedures и становятся доступны через get_procedure_code. После изменения парсера базы пересобрать из выгрузки.

---

## 2025-02-22

- **Очистка:** удалены черновики планов (оценка плана.txt, план предварительный.txt), скрипты разовой проверки ФО (scripts/check_fo_content.py, create_test_fo_db.py), каталоги сборки build/ и dist/.
- **get_object_structure:** приоритет точному совпадению имени объекта; при частичном совпадении и нескольких кандидатах возвращается список для уточнения (`ambiguous: true`, `candidates`).
- **Функциональные опции (ФО):** парсинг ФО из XML (тип FunctionalOption в object_types), извлечение свойств (Location, PrivilegedGetMode, Content) и привязок на формах (реквизиты, команды, элементы UI — FunctionalOptions/Item). Две таблицы: **fo_content_ref** (привязка ФО к объектам метаданных из Content: документ/реквизит/колонка ТЧ/ресурс; одна запись на один объект/реквизит/колонку; content_ref_type: Object | Attribute | TabularSectionColumn | Resource | Dimension) и **fo_form_usage** (привязка ФО к элементам форм — реквизит/команда/элемент формы). В **functional_options** хранятся только location_constant и privileged_get_mode (без дублирования Content). Двухпроходная вставка; заполнение fo_content_ref из Content с разрешением по (object_type, name). MCP: get_object_structure для ФО — content_refs и used_in из fo_content_ref/fo_form_usage; для любого объекта — поле in_functional_options (в каких ФО задействован). Инструмент get_element_functional_options по элементу формы. README_AI.md с путями к выгрузкам.
- **list_objects:** в ответ добавлены явные поля total_count, returned_count, is_truncated для индикации неполного результата; в тексте выводится подсказка при is_truncated: true (увеличить limit или сообщить пользователю).
- **ТЗ MCP (tz_mcp_improvements.md):** индексы БД (modules.object_id, forms.object_id, form_events.form_id, form_item_events.item_id). Таблица **module_procedures** (парсинг при сборке БД: имя, тип, start_line/end_line, params, is_export, execution_context, extension_call_type); get_module_procedures и get_procedure_code переведены на SELECT из БД и срез кода по строкам. Нормализация ТЧ: таблица **tabular_sections**, в tabular_section_columns — tabular_section_id вместо дублирования name/title/comment; get_object_structure через JOIN. find_attribute: поиск также по колонкам ТЧ (tabular_section_columns + tabular_sections), в ответе tabular_section_name и section=TabularSectionColumn. search_code: сниппет 200 символов до/после, обрезка по границам строк. get_form_structure: элементы формы с иерархией (depth, вывод с отступами). После изменений схемы базы пересоздаются заново.
- **Обратная связь по ТЗ MCP:** ускорение создания БД: прагмы SQLite при подключении (journal_mode=WAL) и в _insert_configuration (synchronous=OFF, cache_size=-256000, temp_store=MEMORY на время загрузки, после commit — synchronous=NORMAL); вставка записей в module_procedures через executemany вместо цикла execute. Парсинг execution_context и extension_call_type: сканируются все подряд идущие &-строки над процедурой (collect_annotation_lines_above), значение берётся по ближайшей к процедуре строке — корректно при любом порядке аннотаций (например &НаКлиенте и &Перед в модулях форм расширений). **extension_call_type:** распознавание аннотаций с параметром в скобках (общие модули расширений): &Перед("ИмяПроцедуры"), &После("..."), &Вместо("..."), &ИзменениеИКонтроль("..."). **execution_context:** детализация сохранена — отдельно ServerNoContext (НаСервереБезКонтекста/AtServerNoContext) и Server (НаСервере/AtServer), вместо сводки в один «Server».

---

## 2025-02-18

- **extension_filter:** в описаниях инструментов (server/server.py) зафиксирована архитектура «точное имя» — параметр должен совпадать с именем базы из list_active_databases; в описание list_active_databases добавлена рекомендация вызывать его первым и передавать имена без изменений.
- **Парсер, формат 2.20:** в _parse_register_section добавлен fallback на ChildObjects при отсутствии контейнеров Dimensions/Resources — измерения и ресурсы регистров извлекаются из дочерних элементов Dimension/Resource (выгрузки 2.20 и расширения).
- **Парсер, типы регистров:** добавлены AccountingRegister и CalculationRegister (object_types, register_types, standard_by_type).
- **Парсер, составные типы:** в _extract_attribute_type добавлена поддержка v8:TypeSet — тип заполняется для реквизитов с составным типом (множество типов).
- **Парсер, планы:** добавлены ChartOfAccounts (план счетов) и ChartOfCharacteristicTypes (план видов характеристик) в object_types — объекты парсятся и попадают в БД.
- **Парсер, значения перечислений (формат 2.20):** в _parse_enum_values добавлен fallback на ChildObjects при отсутствии контейнера EnumValues — значения перечисления (EnumValue) извлекаются из дочерних элементов; имя из атрибута или Properties/Name. get_object_structure возвращает enum_values для перечислений после пересоздания баз.
- **README_AI:** добавлен раздел «Цикл проверки изменений» (тестирование на реальном MCP после пересборки пользователем).
- **Имя и тип конфигурации из XML (GUI):** при выборе Configuration.xml название базы и признак «Основная конфигурация»/«Расширение» берутся из файла, а не из имени папки. Имя — из Properties/Name (get_configuration_name с поиском через ns, как в parse()); тип — по наличию ConfigurationExtensionPurpose (get_configuration_type()). Поле «Название» при выборе файла всегда перезаполняется из XML.
