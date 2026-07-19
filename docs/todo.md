# Project backlog

Live list of open tasks and ideas for **1C configuration MCP server functionality** (parser, index, MCP tools, admin GUI). File in git — so after clone on another machine the current state is visible.

**Do not duplicate** closed tasks and history here — only what is not done yet. Closed items — in [`CHANGELOG.md`](../CHANGELOG.md).

**Do not include** operational steps (portable rebuild, manual `databases/*.db` recreation by user, MCP setup in IDE) — those are not tool improvements.

## Hub pending

## Admin Hub / group integration

- **Status:** `stable` (`sync_state`; see [`group/integration.md`](group/integration.md))
- Admin Hub Phase 3 rebuild CLI — **done**; `operations.log` — **done**

## How to use

| Role | Action |
|------|--------|
| Project owner | Adds items, changes status, removes completed |
| Agent | On request reads the list, checks readiness for an item, suggests next step |

## Statuses

| Status | Meaning |
|--------|---------|
| `idea` | Intent, not yet shaped into a task |
| `ready` | Task formulated, can be taken |
| `blocked` | Waiting on external condition (export, scope decision) |
| `in-progress` | In progress |

When done, the item is **removed** from the list (or moved to CHANGELOG — by agreement).

## Readiness check (for agent)

On request "check todo" or "can we do X from the list":

1. Read this file.
2. For the relevant item — is there code/docs/tests in the repo; for parser — is a real export needed (see `agent-map.md`).
3. Answer: what is ready, what is missing, what blocks start.

Do not start implementation from the list without explicit user request.

---

## State snapshot (2026-06-29)

| Area | Status |
|------|--------|
| `ScheduledJob` in whitelist, `scheduled_jobs`, `used_in_scheduled_job` | **done** (see CHANGELOG) |
| Scheduled job search via `list_objects` / `find_object` / `get_object_structure` | **done** (by metadata name) |
| Object search by **synonym** (`metadata_objects.synonym`) | **done** (see CHANGELOG) |
| **`find_referencing_objects`** (reverse search by slots) | **done** (see CHANGELOG) |
| Scheduled job search by `MethodName` | **no** — see `scheduled-job-search` |
| Admin GUI: bulk update, operation status | **no** — see `gui-bulk-update` |
| Admin Hub protocol Phase 1 (manifest, read-only CLI) | **done** — see CHANGELOG, [`admin-hub-integration.md`](admin-hub-integration.md) |
| Admin Hub protocol Phase 2–3 (sync, rebuild CLI) | **done** (incl. `operations.log`); see `integration.md` |
| Admin GUI: build stage log / timings | **done** — validated on real exports and live in the rebuilt admin GUI; see `gui-build-log-timings` |
| Whitelist extension (Role, EventSubscription, …) | **partial** — `Subsystem` (phase 3), `Role` (phase 4); see `dependency-layer.md` phase 5 |
| Type system (metadata + forms, `metadata_type_slots`) | **done** — v8–16; current index format — `INDEXER_VERSION` 16; see CHANGELOG, [`form-type-system.md`](form-type-system.md) |
| `metadata_relations` / role grants | **done** — subsystems (phase 3); roles via `role_grants` (phase 4); role UX polish (layer naming, merge, relation_kinds) — see CHANGELOG 2026-07-08 |

---

## Tasks

<!-- id | status | brief | context / links -->

- **dcs-schema-indexing** · `idea` · Index DataCompositionSchema (СКД) — первый шаг «единого движка»

  - **Design/стратегия:** [`library-migration.md`](library-migration.md) — почему СКД первый (старый парсер СКД не читает → нулевой риск; библиотека уже пишет СКД), первая разведка областей, открытые вопросы схемы

  - **Why:** внешний/встроенный отчёт читается как объект, но **СКД не индексируется** (`_parse_object` не читает `Templates/`). У чистого СКД-отчёта (напр. `РВП`) индекс тонкий — вся логика (источники, запрос, поля) в схеме

  - **Scope (draft):** `Templates/<Схема>/Ext/Template.xml`, `DataCompositionSchema` — области: `dataSet`+текст запроса (первый срез → `code_search`), `field`/`dataPath`, `dataSource`, `calculatedField`/`totalField`, `parameter`, `settingsVariant`. **Много новых таблиц** — нужен качественный анализ. **СКД не только у отчётов** — встречается на Catalog/Document/BusinessProcess/CommonTemplates

  - **Reference (СКД):** `РВП отчет/РВП.xml` (чистый СКД), СКД-шаблоны в `Расш бюдж/Catalogs|Documents`; библиотека `onec_metadata_schema.dcs` знает write-сторону. NB: `ФТ_ОтчетБДР` — MXL-макет, **не** СКД

  - **Related:** `form-dynamiclist-settings` (СКД в форме) — смежная ось; `bump-indexer-version` при новой схеме

- **library-engine-migration** · `done` (2026-07-19) · Перевод read-парсера на единый движок (`onec_metadata_schema`)

  - **Итог:** мигрировано всё, что моделирует библиотека, — **дескрипторы метаданных** (все whitelist-типы, шаги 1–4 за развилкой `_parse_object`/`LIBRARY_MIGRATED_TYPES`=20 + `Subsystem`) и **СКД** (трек `dcs-schema-indexing`, `dcs.py`). Пошаговая история и цифры A/B — в CHANGELOG (2026-07-18/19). Приёмка на живом MCP пройдена

  - **Граница движка (важно, чтобы не мигрировать зря):** формы (`Form.xml`), роли (`Rights.xml`), flowchart (`xcf/scheme`), модули (BSL) — **другие схемы, библиотека их не моделирует** → остаются на своих парсерах (`forms.py`/`roles.py`/`flowchart.py`/`modules.py`); переводить их на библиотеку смысла нет, пока схемы не появятся в самой `1c-metadata-schema` (write-сторона). Подробно — [`library-migration.md`](library-migration.md) § «Граница единого движка»

  - **Не задействовано, но библиотекой поддержано:** MXL-макеты (`spreadsheet`) — потенциальное расширение, отложено (см. `dcs-schema-indexing`)

  - **Метод верификации (образец, если появятся новые библиотечные поверхности):** A/B-диф полного объекта старый↔новый на выгрузках в `C:\Users\Alex\Documents\1` → приёмка на живом MCP. `INDEXER_VERSION` поднимать только при смене формы записываемых данных (шаги 1–4 — не меняли, 17)

- **roles-engine-migration** · `done` (2026-07-19) · Перевод чтения ролей/РЛС (`Rights.xml`) на единый движок (`onec_metadata_schema`)

  - **Итог:** библиотека получила read-модуль `rights.py`/`read_rights` (нейтральный разбор `<Rights>`, схема `8.2/roles` — **другая, не MDClasses**); C-MCP `parse_rights_xml` переведён на движок за развилкой с legacy-фолбэком (`shared/xml_parser/roles.py`). Таксономия `classify_target_qname` (target_kind) — модель хранения C-MCP — осталась в C-MCP. A/B на **3010** `Rights.xml` (946k грантов / 12k РЛС / 3.5k шаблонов) — **0 расхождений**. `INDEXER_VERSION` не поднимался (17 — вывод парсера байт-идентичен). Дизайн и полная инвентаризация поверхности — [`roles-engine-migration.md`](roles-engine-migration.md)

  - **Осталось за границей:** дескриптор роли (`Roles/<Name>.xml`, тривиальный property-only MDClasses — низкоценный микрослайс, не сделан); write-сторона `Rights.xml` (конструктор ролей/РЛС) — Stage G библиотеки; разбор внутренностей РЛС (`#ПоЗначениям`-пары) — Tier 3

- **forms-engine-migration** · `done` (2026-07-19) · Перевод чтения форм (`Form.xml`, logform) на единый движок (`onec_metadata_schema`)

  - **Итог:** библиотека получила read-модуль `form_read.py`/`read_form` (+`RawElement`) — читает logform-формат (контейнеры, дерево items, ~24 вида элементов, слоты типов, титулы, ФО, события, conditional appearance) и отдаёт нейтральную структурную модель, где свойства каждой сущности — policy-free `RawElement`-зеркало subtree. C-MCP `_parse_form` переведён на движок за развилкой `_parse_form_via_library` с legacy-фолбэком (`shared/xml_parser/forms.py`). **EAV-флэттенер (`form_property_flattener.py`) остался в C-MCP** — storage-политика (skip/value_type/UNSET_DATE/ordinals), не формат; ходит по `RawElement` без изменений. Слоты типов — резолвером движка. A/B на **22 826** формах (254k реквизитов, 636k элементов, **3.1M** EAV-строк) — **0 расхождений** (структура, EAV и слоты). `INDEXER_VERSION` не поднимался (17). Дизайн и инвентаризация — [`forms-engine-migration.md`](forms-engine-migration.md)

  - **Ключевой нюанс A/B:** типы состава реквизита-DynamicList лежат в контейнере `Settings` и собираются рекурсивно (`.//TypeSet`/`.//Type`) — паритет с legacy `_extract_slots_from_v8_type_container` (первый прогон брал прямых потомков → терял их, исправлено)

  - **Осталось за границей:** дескриптор роли (см. `roles-engine-migration`); write-сторона `Form.xml` (конструктор форм в `1c-help-mcp` уже пишет формы — round-trip round против `read_form` — потенциальная сверка); очистка legacy-дублирования форматного чтения (шаг 3, позже)

- **mxl-macet-indexing** · срез 1 `done` (2026-07-19), срез 2 `idea` · Индексация MXL-макетов (`SpreadsheetDocument`) через движок

  - **Срез 1 (done):** библиотека получила read-модуль `spreadsheet_read.py`/`read_spreadsheet` (+`read_spreadsheet_text`/`spreadsheet_shape_hints`); C-MCP индексирует видимый текст макета (ячейки+параметры+имена областей) в `code_search` FTS (`module_type='MxlText'`) — `search_code` находит макеты по содержимому. Обход `Templates/` отдельным `_parse_spreadsheet_templates` (развилка по `TemplateType=SpreadsheetDocument`, фолбэк), DCS-путь не тронут. Чистое добавление (старый парсер MXL не читал) — по плейбуку ДКС, 0 регресса. Проверено на АСБ main (12 545 макетов) — 0 ошибок парсинга; корпус ~22 264. `INDEXER_VERSION` 17→**18**. Дизайн — [`mxl-macet-indexing.md`](mxl-macet-indexing.md)

  - **Срез 2 (idea):** таблица `spreadsheet_template` (shape-hints + области/параметры) + MCP-tool `get_spreadsheet` (по образцу `dcs_schema`/`get_dcs_schema`), чтобы агент видел области `ПолучитьОбласть` и параметры без FTS. `spreadsheet_shape_hints` уже отдаёт всё нужное; при добавлении — `bump-indexer-version`

- **form-dynamiclist-settings** · `idea` · Parse DynamicList Settings on form (MainTable, DCS)

  - **Why:** currently DynamicList in v1 — wrapper + `query_text` only; agent does not see main table/data source from Settings

  - **Scope (draft):** `Settings/MainTable`, link to metadata object; optional DCS fields — refine against reference Form.xml (Scheduler, ARM)

  - **Related:** [`form-type-system.md`](form-type-system.md) (basic form type system **done**); may require bump `INDEXER_VERSION` and new DB fields

  - **Not in current iteration** — separate backlog item after v10

- **gui-bulk-update** · `ready` · Bulk update all configurations + progress indicator

  - **Task:** update all databases of all projects (or selected project) in one command, with saved `source_xml` paths

  - **UI (minimum):** status line/header, e.g. "Updating project Hamburg, extension FT_Dorabotki"; progress (N of M) if possible

  - **Side:** `admin_tool/gui_v2.py`, `ProjectManager` (XML paths already in `projects.json`)

  - **Open:** stop on first error; update only stale or all

  - **Done when:** one button/action walks databases with `source_xml`; user sees current operation; tree is up to date on completion

- **scheduled-job-search** · `idea` · Scheduled job search by `MethodName`

  - **Problem:** procedure from `MethodName` (`CommonModule.X.Y`) is not found via `find_object`

  - **Options:** extend `find_object` for ScheduledJob type · JOIN with `scheduled_jobs.method_name` · separate MCP tool

  - **Materials:** `scheduled_jobs` table; on schema change — `bump-indexer-version.mdc`

  - **Not to confuse with** dependency layer (`dependency-layer.md`) — separate axis (handler, not metadata ref)

  - **Done when:** query "find scheduled job for procedure Y" returns relevant result

- **relations-phase-5** · `blocked` · `EventSubscription`

  - **Spec:** [`dependency-layer.md`](dependency-layer.md) — phase 5; **blocked** without real export

---

## Ideas

<!-- status: idea — no fixed scope -->

- **gui-build-log-timings** · `done` · DB build stage log and timings on update form

  - **Task:** on create/update DB form — scrollable list (like a log): lines as stages complete, with duration, e.g. `12:01:05 — XML parse — 412 s`, `12:07:12 — Objects (N) — …`, `12:14:03 — Forms — …`, `12:14:10 — fo_content_ref / scheduled job linking — 0.4 s`, `Done`

  - **Why:** on large exports (Logist main) unclear if "hung" or long stage; timings show bottlenecks (parser vs forms vs other)

  - **Done (2026-07-05):**
    - `admin_tool/db_manager/core.py` + `insert_objects.py` — stage boundaries (parse, schema, objects, relations/fo_content_ref/scheduled-job linking, forms, done) timed via `time.perf_counter()`, folded into the existing `progress_callback(current, total, message)` messages — no signature/return-type changes
    - `shared/xml_parser/core.py` — finer per-stage breakdown *within* XML parse itself (modules/forms/properties/sections/flowchart/commands/subsystems), via `self.stage_seconds` + `_accumulate()` context manager; surfaced as an indented breakdown under the "XML parse" line
    - `admin_tool/gui_v2.py` — `AddDatabaseWindow`, `QuickUpdateDialog`, `UpdateDatabaseWindow` now pass a `progress_callback` into `build_from_xml_atomic` (previously omitted entirely — the actual root cause of "UI silent for minutes"); each dialog got a small `ScrolledText` log widget, appended via the existing `AdminAppV2.schedule_on_main()` (`root.after(0, fn)`) — no queue needed, per-stage call volume is low
    - `scripts/parse-benchmark.py` (new) — standalone CLI to run the parser/builder against a real export outside the GUI/exe, for timing measurement without touching `projects.json`/`databases/`
    - **Validated against real exports:** Фитэра/Задачник (631 MB, 2151 objects, 11.4 s) and АСБ/Бухгалтерия (5.8 GB, 11114 objects, 148.5 s) — both parse+build cleanly end to end
    - **Bug found + fixed along the way:** Windows `MAX_PATH` (260 char) silently broke/crashed on the АСБ export's deeply nested Subsystems tree (a 261-char path) — `ET.parse()`/`.exists()`/`open()` across the whole `shared/xml_parser/` package now go through a `_winlong()` (`\\?\` extended-length prefix) helper in `xml_helpers.py`. Also fixed a console-encoding crash in the benchmark script itself (a box-drawing character wasn't encodable in the Windows console codepage)
    - **Validated live in the rebuilt admin GUI** (user-confirmed): log widget shows real stage progress during an actual update
    - **Follow-up fix:** live use showed the per-10-objects/forms counters ("Объекты N/M") flooding the log with hundreds of lines — `progress_callback` gained an optional `replace_last` flag; those recurring counters now update the same log line in place (Tk Text last-line delete range is `'end-2l'..'end-1l'`, not `'end-1l'..'end'` — Tk always keeps one extra trailing blank row) while stage-boundary summaries stay as separate permanent lines

  - **Related:** `gui-bulk-update` (same log on bulk update)

  - **Done when:** on Logist main update log shows all major stages with seconds; UI updates during build without freezing

- **gui-cancel-build** · `idea` · Cancel DB load/update from GUI

  - **Task:** "Cancel" on create/update DB form — stop long build without closing entire admin tool

  - **Why:** on large configs (10–20+ min) user may pick wrong file, wrong database, or change mind; thread runs to end, window "silent"

  - **Side:** `admin_tool/gui_v2.py` (button, cancel flag, thread state), `admin_tool/db_manager.py` (cancel checks in long loops)

  - **Technically (account for):**
    - `threading.Thread` **cannot** be reliably killed externally — cooperative cancel: `threading.Event` / `should_cancel()` callback → checks in `_insert_configuration` (object/form loops), optionally in parser
    - full XML parse (`parser.parse()`) **not interruptible** mid-way currently — accept "cancel after parse" or staged parse (separate work)
    - on cancel: `rollback` / no `commit`, remove or do not leave broken `.db` (file often `unlink()` before build — document desired behavior)
    - UI: button active only during build; on cancel — log entry (`gui-build-log-timings`) "Cancelled by user"

  - **Related:** `gui-build-log-timings`, `gui-bulk-update` (cancel one DB in batch / cancel whole batch — clarify)

  - **Done when:** during build "Cancel" stops process in reasonable time (seconds, not minutes); no "half-ready" working DB left in `projects.json`/tree without explicit warning

- **gui-redesign** · `idea` · Refresh admin GUI look (optional)

  - **Context:** currently tkinter "utilitarian", like old software; improve readability, spacing, icons/colors, maybe `ttk` theme

  - **Side:** `admin_tool/gui_v2.py`

  - **Priority:** low; does not block `gui-bulk-update` and status fix

  - **Open:** stay on tkinter or consider another UI layer

- **whitelist-event-subscription** · `idea` · Index event subscriptions (`EventSubscription`)

  - **Why:** `event_source` / `event_handler` in `metadata_relations`

  - **Materials:** whitelist, [`dependency-layer.md`](dependency-layer.md) phase 5; **blocked** without real export

  - **Open:** reverse index handler → subscriptions

- **whitelist-http-service** · `idea` · Index HTTP services (`HTTPService`)

  - **Low priority** among whitelist candidates; refine on request
