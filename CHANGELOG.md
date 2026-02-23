# Лог доработок

Все доработки сгруппированы по дню. При внесении изменений в код обновляйте этот файл.

**Правило:** одна доработка (фича, исправление, доработка одной области) — один пункт списка. Если правка дополняет или уточняет уже описанную сегодняшнюю доработку (тот же сценарий, та же часть кода), не добавляйте новый пункт — отредактируйте существующий, расширив описание.

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
