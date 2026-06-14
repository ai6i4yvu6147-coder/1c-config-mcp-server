# Project backlog



Живой список невыполненных задач и идей по **функционалу MCP-сервера конфигурации 1С** (парсер, индекс, MCP tools, admin GUI). Файл в git — чтобы после clone на другой машине было видно текущее состояние.



**Не дублировать** сюда закрытые задачи и историю — только то, что ещё не сделано. Закрытое — в [`CHANGELOG.md`](../CHANGELOG.md).



**Не включать** сюда эксплуатационные шаги (пересборка portable, пересоздание `databases/*.db` пользователем вручную, настройка MCP в IDE) — это не доработки инструмента.



## Как пользоваться



| Роль | Действие |

|------|----------|

| Владелец проекта | Добавляет пункты, меняет статус, убирает выполненное |

| Агент | По запросу читает список, проверяет готовность к пункту, предлагает следующий шаг |



## Статусы



| Статус | Значение |

|--------|----------|

| `idea` | Намерение, ещё не оформлено в задачу |

| `ready` | Задача сформулирована, можно брать в работу |

| `blocked` | Ждёт внешнего условия (выгрузка, решение по scope) |

| `in-progress` | В работе |



При выполнении пункт **удаляется** из списка (или переносится в CHANGELOG — по согласованию).



## Проверка готовности (для агента)



По запросу «проверь todo» или «можно ли сделать X из списка»:



1. Прочитать этот файл.

2. Для релевантного пункта — есть ли в репозитории код/доки/тесты; для парсера — нужна ли реальная выгрузка (см. `agent-onboarding.md`).

3. Ответить: что готово, чего не хватает, что блокирует старт.



Не начинать реализацию по списку без явного запроса пользователя.



---



## Срез состояния (2026-06-14)



| Область | Статус |

|---------|--------|

| `ScheduledJob` в whitelist, `scheduled_jobs`, `used_in_scheduled_job` | **готово** (см. CHANGELOG) |

| Поиск РЗ через `list_objects` / `find_object` / `get_object_structure` | **готово** (по имени метаданных) |

| Поиск объектов по **синониму** (`metadata_objects.synonym`) | **нет** — см. `find-object-synonym` |

| Поиск РЗ по `MethodName` | **нет** — см. `scheduled-job-search` |

| Admin GUI: массовое обновление, статус операции | **нет** — см. `gui-bulk-update` |

| Admin GUI: «устарела» после успешного обновления | **баг** — см. `gui-outdated-status-bug` |

| Admin GUI: лог этапов / тайминги сборки БД | **нет** — см. `gui-build-log-timings` |

| Расширение whitelist (Subsystem, Role, …) | **не начато** — см. `dependency-layer.md` фазы 3–5 |

| Type system (metadata + формы, `metadata_type_slots`) | **готово** — `INDEXER_VERSION` 9; см. CHANGELOG, [`form-type-system.md`](form-type-system.md) |

| `find_referencing_objects`, `metadata_relations` | **не начато** — фазы 2–5 ниже |



---



## Задачи



<!-- id | статус | кратко | контекст / ссылки -->



- **form-dynamiclist-settings** · `idea` · Парсинг Settings динамического списка на форме (MainTable, СКД)

  - **Зачем:** сейчас DynamicList в v1 — только wrapper + `query_text`; агент не видит главную таблицу/источник данных из Settings

  - **Scope (черновик):** `Settings/MainTable`, связь с объектом метаданных; опционально поля СКД — уточнять по эталонным Form.xml (Планировщик, АРМ)

  - **Связано с:** [`form-type-system.md`](form-type-system.md) (базовый type system форм **готово**); может потребовать bump `INDEXER_VERSION` и новые поля БД

  - **Не в текущей итерации** — отдельный backlog-пункт после v9



- **gui-outdated-status-bug** · `ready` · После обновления БД в GUI статус остаётся «устарела»

  - **Симптом:** успешное обновление конфигурации, в дереве по-прежнему красная подсветка / «Устарела (v… < v…)»

  - **Гипотеза:** после `create_database` дерево не перечитывается — в `QuickUpdateDialog._update_database_thread` и `UpdateDatabaseWindow._update_database_thread` нет вызова `main_app._load_projects()` (в отличие от `CreateDatabaseWindow`)

  - **Сторона:** `admin_tool/gui_v2.py`

  - **Критерий закрытия:** после любого сценария обновления одной базы колонка «Состояние» показывает `OK v{INDEXER_VERSION}` без ручного перезапуска GUI



- **gui-bulk-update** · `ready` · Массовая актуализация всех конфигураций + индикатор процесса

  - **Задача:** обновить все базы всех проектов (или выбранного проекта) одной командой, с сохранёнными путями `source_xml`

  - **UI (минимум):** строка/заголовок состояния, напр. «Обновляется проект Гамбург, расширение ФТ_Доработки»; по возможности — прогресс (N из M)

  - **Сторона:** `admin_tool/gui_v2.py`, `ProjectManager` (пути к XML уже в `projects.json`)

  - **Открыто:** останавливать ли при первой ошибке; обновлять ли только устаревшие или все

  - **Критерий закрытия:** одна кнопка/действие проходит по списку баз с `source_xml`; пользователь видит текущую операцию; по завершении дерево актуально



- **find-object-synonym** · `ready` · Поиск объектов метаданных по синониму

  - **Аудит (2026-06-10):** синоним **индексируется** (`metadata_objects.synonym`, парсер `xml_parser._parse_properties`), но **не участвует в поиске**

    - `find_object`: только `WHERE o.name LIKE ?` ([`server/tools.py`](../server/tools.py))

    - `get_object_structure` (неоднозначность): частичное совпадение тоже только по `name`

    - `find_attribute`: по имени реквизита, не по title/синониму объекта

  - **Варианты:** расширить `find_object` (`name OR synonym LIKE`) · опциональный параметр `search_field` · отдельный tool

  - **Связано с:** `scheduled-job-search` (синоним РЗ — частный случай)

  - **Критерий закрытия:** `find_object` по фрагменту русского синонима находит объект без знания технического имени



- **scheduled-job-search** · `idea` · Поиск регламентных заданий по `MethodName`

  - **Проблема:** процедура из `MethodName` (`CommonModule.X.Y`) не ищется через `find_object`

  - **Варианты:** расширить `find_object` для типа ScheduledJob · JOIN с `scheduled_jobs.method_name` · отдельный MCP tool

  - **Материалы:** таблица `scheduled_jobs`; при доработке схемы — `bump-indexer-version.md`

  - **Не путать с** dependency layer (`dependency-layer.md`) — это отдельная ось (handler, не metadata ref)

  - **Критерий заключения:** запрос «найди РЗ для процедуры Y» даёт релевантный результат



- **dependency-layer-phase-0** · `ready` · `find_object` по синониму (без схемы)

  - **Спека:** [`dependency-layer.md`](dependency-layer.md) — фаза 0

  - **Сторона:** `server/tools.py` (`find_object`, при неоднозначности — `get_object_structure`)

  - **Критерий закрытия:** поиск по фрагменту русского `synonym` находит объект



- **type-system-phase-2** · `ready` · Tool `find_referencing_objects` (обратный поиск по слотам)

  - **Спека:** [`dependency-layer.md`](dependency-layer.md) — фаза 2

  - **Сторона:** `server/tools.py`, `server/server.py`, `docs/mcp-tools.md`

  - **Критерий закрытия:** см. «Критерии готовности фазы 2» в `dependency-layer.md`



- **relations-phase-3** · `ready` · `metadata_relations` + whitelist `Subsystem`

  - **Спека:** [`dependency-layer.md`](dependency-layer.md) — фаза 3

  - **Зависимости:** type-system-phase-1

  - **Критерий закрытия:** подсистемные связи в `find_referencing_objects` с меткой `via: subsystem_member`



- **relations-phase-4** · `blocked` · whitelist `Role` (MVP grants)

  - **Спека:** [`dependency-layer.md`](dependency-layer.md) — фаза 4; **blocked** без реальной выгрузки ролей



- **relations-phase-5** · `blocked` · `EventSubscription`

  - **Спека:** [`dependency-layer.md`](dependency-layer.md) — фаза 5; **blocked** без реальной выгрузки



---



## Идеи



<!-- статус: idea — без жёсткого scope -->



- **gui-build-log-timings** · `idea` · Лог этапов сборки БД и замеры времени на форме обновления

  - **Задача:** на форме создания/обновления БД — прокручиваемый список (как лог): строки по мере прохождения этапов, с длительностью, напр. `12:01:05 — Парсинг XML — 412 с`, `12:07:12 — Объекты (N) — …`, `12:14:03 — Формы — …`, `12:14:10 — fo_content_ref / линковка РЗ — 0.4 с`, `Готово`

  - **Зачем:** на крупных выгрузках (Логист основная) непонятно, «зависло» или идёт долгий этап; замеры покажут узкие места (парсер vs формы vs прочее)

  - **Сторона:** `admin_tool/db_manager.py` (разбивка этапов + `time.perf_counter()`), `admin_tool/gui_v2.py` (виджет лога)

  - **Почему не сработал прогресс-бар раньше (учесть при реализации):**
    - `DatabaseManager.create_database` уже принимает `progress_callback`, но **GUI его не передаёт** — все потоки вызывают `create_database(xml)` без callback (`CreateDatabaseWindow`, `QuickUpdateDialog`, `UpdateDatabaseWindow`)
    - обновление идёт в **фоновом `threading.Thread`**; в tkinter **нельзя** трогать виджеты из worker-потока — только через `queue.Queue` + `root.after()` (или `after` с polling очереди)
    - текущие callback в `_insert_configuration` — только «Объекты» / «Формы» раз в 10 объектов; **нет** сообщений на парсинг XML, `fo_content_ref`, `_link_scheduled_job_procedures`, commit — там UI «молчит» минутами

  - **Рекомендуемый MVP (проще прогресс-бара):** append-only `ScrolledText` / `Listbox` + очередь событий; не пытаться сначала сделать плавный `%` — достаточно дискретных строк по **завершении** этапа. Прогресс-бар — опционально позже, если заработает тот же механизм `after`

  - **Ограничение tkinter:** динамические оповещения **возможны**, но только с правильной связкой поток → очередь → главный loop; без этого UI кажется «мёртвым». Если `after`-очередь окажется ненадёжной на длинных сборках — зафиксировать в пункте и рассмотреть альтернативу UI (`gui-redesign`)

  - **Связано с:** `gui-bulk-update` (тот же лог при массовом обновлении)

  - **Критерий закрытия:** при обновлении Логист основная в логе видны все крупные этапы с секундами; UI обновляется во время сборки без зависания окна


- **gui-cancel-build** · `idea` · Прерывание загрузки/обновления базы из GUI

  - **Задача:** кнопка «Отмена» на форме создания/обновления БД — остановить долгую сборку без закрытия всего admin tool

  - **Зачем:** на крупных конфигурациях (10–20+ мин) пользователь может ошибиться файлом, выбрать не ту базу или передумать; сейчас поток идёт до конца, окно «молчит»

  - **Сторона:** `admin_tool/gui_v2.py` (кнопка, флаг отмены, состояние потока), `admin_tool/db_manager.py` (проверка отмены в длинных циклах)

  - **Технически (учесть):**
    - `threading.Thread` **нельзя** надёжно убить извне — нужен cooperative cancel: `threading.Event` / callback `should_cancel()` → проверки в `_insert_configuration` (циклы объектов/форм), опционально в парсере
    - парсинг XML целиком (`parser.parse()`) сейчас **не прерывается** на полпути — либо принять «отмена после парсинга», либо поэтапный парс (отдельная доработка)
    - при отмене: `rollback` / не `commit`, удалить или не оставлять битый `.db` (сейчас перед сборкой файл часто `unlink()` — зафиксировать желаемое поведение)
    - UI: кнопка активна только пока идёт сборка; по отмене — запись в лог (`gui-build-log-timings`) «Отменено пользователем»

  - **Связано с:** `gui-build-log-timings`, `gui-bulk-update` (отмена одной базы в пакете / отмена всего пакета — уточнить)

  - **Критерий закрытия:** во время сборки «Отмена» останавливает процесс за разумное время (секунды, не минуты); в `projects.json`/дереве не остаётся «полуготовой» рабочей БД без явного предупреждения


- **gui-redesign** · `idea` · Обновить внешний вид admin GUI (не обязательно)

  - **Контекст:** сейчас tkinter «утилитарно», как старое ПО; улучшить читаемость, отступы, иконки/цвета, возможно `ttk` тема

  - **Сторона:** `admin_tool/gui_v2.py`

  - **Приоритет:** низкий; не блокирует `gui-bulk-update` и фикс статуса

  - **Открыто:** оставаться на tkinter или рассматривать другой UI-слой



- **whitelist-subsystem** · `idea` · Индексация подсистем (`Subsystem`)

  - **Зачем:** навигация по структуре конфигурации, `subsystem_member` в `metadata_relations`

  - **Материалы:** [`metadata-whitelist.md`](metadata-whitelist.md), [`dependency-layer.md`](dependency-layer.md) фаза 3; нужна выгрузка с `Subsystems/`

  - **Tools:** `find_referencing_objects` (после type-system-phase-2)



- **whitelist-role** · `idea` · Индексация ролей (`Role`)

  - **Зачем:** `role_grant` в `metadata_relations`, анализ прав

  - **Материалы:** whitelist, [`dependency-layer.md`](dependency-layer.md) фаза 4; **blocked** без реальной выгрузки ролей

  - **Открыто:** MVP без полной модели RLS (права в `source_path`)



- **whitelist-event-subscription** · `idea` · Индексация подписок на события (`EventSubscription`)

  - **Зачем:** `event_source` / `event_handler` в `metadata_relations`

  - **Материалы:** whitelist, [`dependency-layer.md`](dependency-layer.md) фаза 5; **blocked** без реальной выгрузки

  - **Открыто:** обратный индекс handler → подписки



- **whitelist-http-service** · `idea` · Индексация HTTP-сервисов (`HTTPService`)

  - **Низкий приоритет** среди типов из whitelist-кандидатов; уточнять по запросу


