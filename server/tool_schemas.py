from mcp.types import Tool

TOOL_SCHEMAS = [
    Tool(
        name="guide",
        description=(
            "Справка этого сервера о себе самом: с чего начать, какой инструмент под какую цель, "
            "чем этот сервер НЕ занимается, типовые грабли. Дёрните один раз перед первой "
            "серьёзной работой с конфигурацией — дешевле, чем выяснять это перебором вызовов. "
            "Без аргументов возвращает вводную часть и меню разделов; section=<id> — раздел "
            "целиком; section='all' — весь текст. Работает всегда, даже если индексы не собраны."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": (
                        "Id раздела из меню (например 'routes' или 'tools'); 'all' — весь текст. "
                        "Без параметра — вводная часть и список разделов."
                    ),
                }
            },
            "required": []
        }
    ),
    Tool(
        name="set_context",
        description=(
            "Deterministically (re)seed this server's sticky correlation context for the rest "
            "of the chat: task_id / session_id / agent / model. Call it once, right after "
            "work_on_task, before any other tool here — that guarantees every subsequent call "
            "in this process gets correlated even if you forget to repeat the ids on individual "
            "calls. All fields optional; fields you omit are left as they were. Journaling only "
            "— never affects tool behavior, results, or errors. Returns the resulting context so "
            "you can confirm what took effect."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="active_databases",
        description=(
            "Список проектов и баз данных 1С (основная конфигурация и расширения). Первый шаг работы: "
            "вызывайте без аргументов, чтобы узнать допустимые project_filter/extension_filter для остальных "
            "инструментов (search_code, list_objects, find_object, get_module_code и др.). Передавайте "
            "возвращённые имена без изменений (точное совпадение)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "placeholder": {
                    "type": "string",
                    "description": "Не используется; параметр опционален. Вызовите инструмент без аргументов для получения списка проектов и баз."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="search_code",
        description=(
            "Инструмент search_code: поиск фрагмента в BSL-коде модулей (ManagerModule, ObjectModule, "
            "FormModule и др.) и в QueryText форм. project_filter обязателен; extension_filter опционален. "
            "Список проектов и баз — active_databases."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно). Например: 'ТГ'"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                },
                "object_name": {
                    "type": "string",
                    "description": "Фильтр по имени объекта (опционально, можно частичное). Например: 'ФТ_Конвертации'"
                },
                "module_type": {
                    "type": "string",
                    "description": "Фильтр по типу модуля (опционально): Module, ManagerModule, ObjectModule, RecordSetModule, ValueManagerModule, FormModule, CommandModule"
                },
                "max_results": {
                    "type": "number",
                    "description": "Максимум результатов на базу (по умолчанию 10)",
                    "default": 10
                }
            },
            "required": ["query", "project_filter"]
        }
    ),
    Tool(
        name="find_object",
        description="Найти объект метаданных по имени или синониму. project_filter обязателен. Для расширений в ответе возвращается object_belonging (Own/Adopted).",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Имя или синоним объекта (можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["name", "project_filter"]
        }
    ),
    Tool(
        name="list_objects",
        description=(
            "Инструмент list_objects: перечень объектов метаданных конфигурации (Catalog, Document, "
            "CommonModule и др.); опционально object_type. project_filter обязателен. Для расширений в ответе "
            "— object_belonging (Own/Adopted). По каждой базе: total_count, returned_count, is_truncated; "
            "при is_truncated: true увеличьте limit или сообщите пользователю о неполном списке."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_type": {
                    "type": "string",
                    "description": "Тип объекта (опционально): CommonModule, Catalog, Document и т.д."
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                },
                "limit": {
                    "type": "number",
                    "description": "Максимум объектов на базу (по умолчанию 50)",
                    "default": 50
                }
            },
            "required": ["project_filter"]
        }
    ),
    Tool(
        name="get_module_code",
        description=(
            "Получить код модуля объекта, модуля формы или CommandModule (команда объекта / общая команда). "
            "project_filter обязателен. Для module_type='CommandModule': укажите command_name для модуля команды объекта; "
            "без command_name — модуль общей команды (объект типа CommonCommand)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта"
                },
                "module_type": {
                    "type": "string",
                    "description": "Тип модуля: Module, ManagerModule, ObjectModule, RecordSetModule (модуль набора записей регистра), ValueManagerModule (модуль менеджера значения константы), FormModule, CommandModule (по умолчанию Module)",
                    "default": "Module"
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы (обязательно для module_type='FormModule')"
                },
                "command_name": {
                    "type": "string",
                    "description": "Имя команды объекта (только для module_type='CommandModule'; взаимоисключение с form_name)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["object_name", "project_filter"]
        }
    ),
    Tool(
        name="get_module_procedures",
        description=(
            "Получить список процедур и функций модуля (сигнатуры и контекст выполнения Клиент/Сервер). project_filter обязателен. "
            "Поддержка CommandModule: command_name для команды объекта; без command_name — общая команда (CommonCommand)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта"
                },
                "module_type": {
                    "type": "string",
                    "description": "Тип модуля: Module, ManagerModule, ObjectModule, RecordSetModule (модуль набора записей регистра), ValueManagerModule (модуль менеджера значения константы), FormModule, CommandModule (по умолчанию Module)",
                    "default": "Module"
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы (обязательно для module_type='FormModule')"
                },
                "command_name": {
                    "type": "string",
                    "description": "Имя команды объекта (только для module_type='CommandModule'; взаимоисключение с form_name)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["object_name", "project_filter"]
        }
    ),
    Tool(
        name="get_procedure_code",
        description=(
            "Получить код конкретной процедуры или функции (включая директиву &НаКлиенте/&НаСервере). project_filter обязателен. "
            "CommandModule: command_name для команды объекта; без command_name — общая команда."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта"
                },
                "procedure_name": {
                    "type": "string",
                    "description": "Имя процедуры или функции"
                },
                "module_type": {
                    "type": "string",
                    "description": "Тип модуля: Module, ManagerModule, ObjectModule, RecordSetModule (модуль набора записей регистра), ValueManagerModule (модуль менеджера значения константы), FormModule, CommandModule (по умолчанию Module)",
                    "default": "Module"
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы (обязательно для module_type='FormModule')"
                },
                "command_name": {
                    "type": "string",
                    "description": "Имя команды объекта (только для module_type='CommandModule'; взаимоисключение с form_name)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["object_name", "procedure_name", "project_filter"]
        }
    ),
    Tool(
        name="find_form",
        description="Поиск форм по имени объекта и/или формы. project_filter обязателен. В ответе: form_kind (List/Choice/Element), для расширений — object_belonging.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта (опционально, можно частичное)"
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы (опционально, можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["project_filter"]
        }
    ),
    Tool(
        name="find_form_element",
        description="Найти формы, содержащие элемент по имени элемента или по связи с данными — ПутьКДанным (data_path). project_filter обязателен. В ответе: visible, enabled, data_path.",
        inputSchema={
            "type": "object",
            "properties": {
                "element_name": {
                    "type": "string",
                    "description": "Имя элемента формы (можно частичное). Задайте его или data_path."
                },
                "data_path": {
                    "type": "string",
                    "description": "Путь к данным (реквизит): поиск по полю DataPath/ПутьКДанным (можно частичное). Задайте его или element_name."
                },
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта для фильтрации (опционально, можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["project_filter"]
        }
    ),
    Tool(
        name="get_form_structure",
        description=(
            "Обзор структуры формы: реквизиты (types[] и подсказки drill-down), команды, события, "
            "элементы UI с профилем свойств по типу элемента. project_filter обязателен. "
            "DynamicList: QueryText только как подсказка (N chars) — полный текст через get_form_attribute. "
            "Колонки Table/ValueTable скрыты в обзоре — get_form_item / get_form_attribute."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта"
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["object_name", "form_name", "project_filter"]
        }
    ),
    Tool(
        name="get_form_attribute",
        description=(
            "Детали реквизита формы: ключевые свойства из EAV, types[], индекс колонок ValueTable или полей DynamicList. "
            "Полный Settings.QueryText динамического списка. project_filter обязателен. "
            "column_name (опционально): колонка ValueTable или поле DynamicList. "
            "По умолчанию свойства курируются (скрыт служебный шум); verbose=true — полный EAV."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {"type": "string", "description": "Имя объекта"},
                "form_name": {"type": "string", "description": "Имя формы"},
                "attribute_name": {"type": "string", "description": "Имя реквизита формы"},
                "column_name": {"type": "string", "description": "Имя колонки ValueTable или поля DynamicList (опционально)"},
                "verbose": {"type": "boolean", "description": "true — полный EAV без курирования (по умолчанию false)", "default": False},
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {"type": "string", "description": "Точное имя базы из active_databases (опционально)"},
            },
            "required": ["object_name", "form_name", "attribute_name", "project_filter"]
        }
    ),
    Tool(
        name="get_form_item",
        description=(
            "Детали элемента UI формы: ключевые свойства EAV (сначала профильные), события, индекс колонок для Table. "
            "project_filter обязателен. column_name (опционально): дочерний элемент колонки контейнера. "
            "По умолчанию свойства курируются (скрыт служебный шум); verbose=true — полный EAV."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {"type": "string", "description": "Имя объекта"},
                "form_name": {"type": "string", "description": "Имя формы"},
                "element_name": {"type": "string", "description": "Имя элемента UI"},
                "column_name": {"type": "string", "description": "Имя дочернего элемента колонки (опционально)"},
                "verbose": {"type": "boolean", "description": "true — полный EAV без курирования (по умолчанию false)", "default": False},
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {"type": "string", "description": "Точное имя базы из active_databases (опционально)"},
            },
            "required": ["object_name", "form_name", "element_name", "project_filter"]
        }
    ),
    Tool(
        name="search_form_properties",
        description=(
            "Поиск UI-элементов форм по любому свойству EAV (property_path) и опционально значению. "
            "project_filter обязателен. value_match=contains — поиск подстроки. "
            "Лимит max_results (по умолчанию 100) с is_truncated. Пути свойств — как в get_form_item "
            "(DataPath, Visible, Enabled, ReadOnly, CommandName, RowPictureDataPath, Settings.MainTable, …)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "property_path": {
                    "type": "string",
                    "description": "Путь свойства из EAV: Visible, Enabled, ReadOnly, DataPath, CommandName, Settings.MainTable, … (точное совпадение пути)"
                },
                "property_value": {
                    "type": "string",
                    "description": "Значение (опционально). Булевы синонимы да/нет/1/0 нормализуются в true/false."
                },
                "value_match": {
                    "type": "string",
                    "enum": ["exact", "contains"],
                    "description": "exact (по умолчанию) — точное значение; contains — подстрока (LIKE)",
                    "default": "exact"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Максимум элементов на базу (по умолчанию 100)",
                    "default": 100
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                }
            },
            "required": ["property_path", "project_filter"]
        }
    ),
    Tool(
        name="get_object_structure",
        description=(
            "Полная структура метаданных объекта 1С. project_filter обязателен. Для расширений в ответе — object_belonging (Own/Adopted). "
            "Поле modules — только модули объекта (без CommandModule команд). Команды объекта — в массиве commands: name, synonym, has_module. "
            "Общие команды (CommonCommand): CommandModule в modules, commands обычно пуст. "
            "BusinessProcess: route_points и route_transitions (схема из Flowchart.xml); в тексте — индекс точек и adjacency list переходов. "
            "ScheduledJob: method_name, use, predefined, restart_count_on_failure, restart_interval_on_failure. "
            "Constant: types — тип хранимого значения (реквизитов и форм у константы нет), modules — ValueManagerModule/ManagerModule. "
            "EventSubscription: event (событие), handler (обработчик CommonModule.<Модуль>.<Процедура>), sources (конкретные объекты-источники) и source_kinds (источник-вид-целиком, например все документы); своего кода у подписки нет. Обратный вопрос «что срабатывает при записи объекта X» — find_referencing_objects(relation_kinds=['event_subscription']). "
            "Списки реквизитов/измерений/ресурсов ограничены max_attributes (по умолчанию 50); при обрезке — <section>_total_count и is_truncated. "
            "sections — вернуть только указанные секции (экономия для широких объектов)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта (можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Только указанные секции: attributes, dimensions, resources, tabular_sections, "
                        "enum_values, commands, forms, modules, route_points. Пусто — все секции."
                    )
                },
                "max_attributes": {
                    "type": "integer",
                    "description": "Лимит списков реквизитов/измерений/ресурсов (по умолчанию 50; 0 — без лимита)",
                    "default": 50
                }
            },
            "required": ["object_name", "project_filter"]
        }
    ),
    Tool(
        name="find_referencing_objects",
        description=(
            "Обратный поиск: кто ссылается на объект метаданных через типы полей "
            "(metadata_type_slots) и структурные связи (metadata_relations). "
            "project_filter обязателен. "
            "via: attribute | tabular_section_column | form_attribute | form_attribute_column | "
            "subsystem_member (подсистема в Content) | role_grant (роль → право на объект) | "
            "event_subscription (подписка на событие → объект-источник; в ответе — событие и обработчик)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя или синоним целевого объекта (можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Максимум записей на базу (по умолчанию 100)"
                },
                "relation_kinds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Фильтр видов связей: subsystem_member, role_grant, event_subscription, attribute, … "
                        "Непустой список — только перечисленные via; для ролей удобнее find_roles_for_object. "
                        "Пусто — все виды."
                    )
                }
            },
            "required": ["object_name", "project_filter"]
        }
    ),
    Tool(
        name="get_functional_options",
        description="Функциональные опции для объекта или элемента формы. FormAttributeColumn: также attribute_name. project_filter обязателен.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта (документ, справочник и т.д.) — обязательно."
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)."
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из active_databases (опционально)."
                },
                "form_name": {
                    "type": "string",
                    "description": "Имя формы — для запроса по элементу формы (вместе с element_type и element_name)."
                },
                "element_type": {
                    "type": "string",
                    "description": "FormAttribute | FormCommand | FormItem | FormAttributeColumn — для элемента формы."
                },
                "element_name": {
                    "type": "string",
                    "description": "Имя реквизита/команды/элемента/колонки формы."
                },
                "attribute_name": {
                    "type": "string",
                    "description": "Имя реквизита-родителя (обязательно для FormAttributeColumn)."
                }
            },
            "required": ["object_name", "project_filter"]
        }
    ),
    Tool(
        name="find_attribute",
        description="Поиск реквизита по имени. project_filter обязателен. Для расширений в ответе — object_belonging (Own/Adopted).",
        inputSchema={
            "type": "object",
            "properties": {
                "attribute_name": {
                    "type": "string",
                    "description": "Имя реквизита (можно частичное)"
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)"
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                },
                "max_results": {
                    "type": "number",
                    "description": "Максимум результатов на базу (по умолчанию 20)",
                    "default": 20
                }
            },
            "required": ["attribute_name", "project_filter"]
        }
    ),
    Tool(
        name="find_role",
        description="Найти роль по имени или синониму. project_filter обязателен.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Имя или синоним роли (можно частичное)"},
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из active_databases (опционально)",
                },
            },
            "required": ["name", "project_filter"],
        },
    ),
    Tool(
        name="list_roles",
        description="Список ролей в проекте/базе. project_filter обязателен.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из active_databases (опционально)",
                },
                "limit": {"type": "integer", "description": "Максимум ролей на базу (по умолчанию 200)", "default": 200},
            },
            "required": ["project_filter"],
        },
    ),
    Tool(
        name="get_role_rights",
        description=(
            "Права роли: grants, RLS, шаблоны. merge=true (по умолчанию) — эффективное состояние "
            "main + расширения; merge=false — только выбранный слой."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "role_name": {"type": "string", "description": "Имя роли"},
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {
                    "type": "string",
                    "description": "Слой при merge=false (имя базы из active_databases)",
                },
                "merge": {"type": "boolean", "description": "Объединить main + расширения", "default": True},
                "object_name": {"type": "string", "description": "Фильтр по объекту (частичное совпадение)"},
                "rights": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Фильтр типов прав (Read, View, …)",
                },
                "rls": {"type": "boolean", "description": "Фильтр по наличию ограничений доступа"},
                "depth": {
                    "type": "string",
                    "enum": ["object", "all"],
                    "description": "object — только объектный уровень; all — включая реквизиты",
                    "default": "object",
                },
                "include_restriction_text": {
                    "description": "false | true (preview 200 символов) | full",
                    "default": False,
                },
                "max_results": {"type": "integer", "default": 200},
                "response_mode": {
                    "type": "string",
                    "enum": ["summary", "full"],
                    "description": "summary — сводка для тяжёлых ролей; full — перечисление grants",
                },
            },
            "required": ["role_name", "project_filter"],
        },
    ),
    Tool(
        name="find_roles_for_object",
        description=(
            "Обратный поиск: какие роли выдают права на объект. "
            "merge=true — сводка по всему проекту (main + расширения); merge=false — по слоям. "
            "project_filter обязателен."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {"type": "string", "description": "Имя или синоним объекта"},
                "project_filter": {"type": "string", "description": "Фильтр по проекту (обязательно)"},
                "extension_filter": {
                    "type": "string",
                    "description": "Имя базы из active_databases (опционально; при merge=true игнорируется)",
                },
                "merge": {
                    "type": "boolean",
                    "default": False,
                    "description": "true — объединённый список ролей по проекту; false — по базам",
                },
                "right_name": {"type": "string", "description": "Фильтр по типу права (Read, …)"},
                "rls": {"type": "boolean", "description": "true — только с RLS; false — без RLS"},
                "max_results": {"type": "integer", "default": 200},
            },
            "required": ["object_name", "project_filter"],
        },
    ),
    Tool(
        name="get_dcs_schema",
        description=(
            "Схема компоновки данных (СКД, DataCompositionSchema) объекта-владельца: наборы "
            "с текстом запроса и полями (роли: измерение/баланс/период), параметры, "
            "вычисляемые/итоговые поля, сводка вариантов настроек. project_filter обязателен. "
            "СКД крепится не только к отчётам — тысячи схем на Catalog/Document/регистрах "
            "(часто это встроенные правила отбора/выборки для BSL, не вывод отчёта; см. "
            "shape-hint has_query). Без template — обзор всех схем объекта (shape-hints: "
            "dataset_count/field_count/parameter_count/has_query/has_grouping/…); полный "
            "документ отдаётся, когда цель одна (или указан template). Межобъектный поиск по "
            "тексту запроса СКД — search_code (module_type='DcsQuery')."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Имя объекта-владельца (можно частичное)",
                },
                "project_filter": {
                    "type": "string",
                    "description": "Фильтр по проекту (обязательно)",
                },
                "template": {
                    "type": "string",
                    "description": (
                        "Имя шаблона схемы (частичное). Без него — обзор всех схем объекта."
                    ),
                },
                "extension_filter": {
                    "type": "string",
                    "description": "Точное имя базы из active_databases (опционально).",
                },
            },
            "required": ["object_name", "project_filter"],
        },
    ),
]
