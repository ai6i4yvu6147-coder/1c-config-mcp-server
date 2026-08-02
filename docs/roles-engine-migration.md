# Перевод ролей и РЛС на единый движок (`onec_metadata_schema`)

Трек `roles-engine-migration`. Продолжение линии единого движка формата
([`library-migration.md`](library-migration.md)) на поверхность, которую та заметка
явно оставляла за границей: **роли и ограничения доступа (РЛС)**. Здесь — полная
инвентаризация поверхности ролей/РЛС в C-MCP, дизайн миграции (по образцу ДКС) и что
уже сделано.

## Почему это отдельный трек, а не часть `library-engine-migration`

`Rights.xml` — **другая схема**, не MDClasses. Дескрипторы метаданных живут в
`http://v8.1c.ru/8.3/MDClasses`, а права роли — в `http://v8.1c.ru/8.2/roles`
(корень `<Rights>`). Библиотека `onec_metadata_schema` до этого трека моделировала
ровно две read-поверхности — **дескрипторы** (`parse`/`Node`) и **СКД** (`dcs_read`),
— а `Rights.xml` не читала вовсе. Поэтому в `library-migration.md` роли значились на
границе движка: «остаются на своём парсере, пока схема не появится в самой библиотеке».

Этот трек и есть «появление схемы в библиотеке» — но на **read-стороне**, ровно как
это было с ДКС: библиотека получила `dcs_read` раньше полного write-round-trip, чтобы
обслужить индексацию C-MCP. Точно так же теперь она получила `read_rights`. Write-сторона
(конструирование `Rights.xml`) — позже, территория Stage G.

## Инвентаризация: вся поверхность ролей/РЛС в C-MCP

Сквозной путь данных — «выгрузка → парсер → SQLite → MCP-инструменты». Роли, в отличие
от whitelist-типов, читаются **не** через `_parse_object`, а отдельным обходом каталога
`Roles/` (как `Subsystem` — обход `Subsystems/`).

### 1. Источники (реальная выгрузка)

| Файл | Содержимое | Кто читает |
|------|-----------|-----------|
| `Roles/<Name>.xml` | Дескриптор роли: корень `MetaDataObject/Role`, `Name`/`Synonym`/`Comment`/`uuid`; в расширении — `ObjectBelonging`, `ExtendedConfigurationObject` | `_parse_roles` (свой MDClasses-парсер свойств) |
| `Roles/<Name>/Ext/Rights.xml` | Корень `<Rights>` (ns `8.2/roles`): 3 корневых флага, гранты (`object`→`right`→`value`), РЛС (`restrictionByCondition`), шаблоны ограничений (`restrictionTemplate`) | `parse_rights_xml` → **теперь `onec_metadata_schema.read_rights`** |

Формат `Rights.xml` (подтверждено на реальных выгрузках, см. §«Масштаб»):

- **Корневые флаги:** `setForNewObjects`, `setForAttributesByDefault`,
  `independentRightsOfChildObjects` (bool|отсутствует).
- **Грант:** `<object><name>Тип.Имя(.Уточнение…)</name><right><name>Read</name><value>true</value>…`.
  Имя цели — квалифицированное: объектный уровень (`Document.X`), реквизит
  (`.Attribute.Y`), ТЧ (`.TabularSection.TS[.Attribute.A]`), ресурс/измерение/команда,
  `StandardAttribute`, а также `Configuration.*` и вложенные `Subsystem.…`.
- **РЛС** (UI «Ограничения доступа к данным») — `restrictionByCondition` **внутри** `<right>`:
  без `<field>` = «Прочие поля»; с `<field>Ref</field>` = конкретное поле; `<condition>` —
  текст ограничения (макросы `#ПоЗначениям`/`#ДляРегистра`/… или язык запросов). Несколько
  `restrictionByCondition` под одним `<right>` допустимы.
- **Шаблоны ограничений** (`restrictionTemplate` в конце файла) — `name` + `condition`,
  общие для роли, вызываются из текста РЛС по `#ИмяШаблона(...)`.

### 2. Парсер

| Файл | Роль |
|------|------|
| [`shared/xml_parser/roles.py`](../shared/xml_parser/roles.py) | `parse_rights_xml` (развилка) + `RolesMixin._parse_roles` (обход `Roles/`, дескриптор, привязка прав). Вызов — `core.py` под `_accumulate('roles')` |
| [`shared/xml_parser/role_qname.py`](../shared/xml_parser/role_qname.py) | `classify_target_qname(qname)` → `(target_kind, parent_object_qname)`. **Таксономия C-MCP** (object/attribute/tabular_section[_attribute]/resource/dimension/command/standard_attribute/configuration/field), а не факт формата — остаётся в C-MCP |

### 3. Хранение (SQLite)

`admin_tool/db_manager/schema.py` — 4 таблицы; `admin_tool/db_manager/roles.py` — вставка.

| Таблица | Ключ | Примечание |
|---------|------|-----------|
| `role_settings` | `role_object_id` (PK) | 3 флага |
| `role_grants` | автоинкремент | `target_qname/target_kind/parent_object_qname/right_name/granted` |
| `role_access_restrictions` | `grant_id` FK → `role_grants` | привязка к **object-level** гранту с `granted=1` по `(target_qname,right_name)`; `field_scope`/`restriction_text` |
| `role_restriction_templates` | `role_object_id` | `template_name`/`condition_text` |

### 4. Выдача (MCP)

| Файл | Роль |
|------|------|
| `server/role_db.py` | `fetch_role_row`/`fetch_role_layer`/`read_index_metadata` |
| `server/role_merge.py` | чистые merge/filter-хелперы: overlay слоёв по `ConfigurationExtensionPurpose` (Customization<AddOn<Patch), фильтры, summary-режим, отбор используемых шаблонов |
| `server/tools/roles.py` | `find_role`, `list_roles`, `get_role_rights`, `find_roles_for_object` |
| `server/dispatch/roles.py` | текстовое форматирование ответов |

Семантика merge/слоёв/инструментов — [`roles-layer.md`](roles-layer.md) (фаза 4). Этот
трек её **не трогает** — он меняет только чтение `Rights.xml` на движок; всё, что ниже
парсера (SQLite-форма, merge, инструменты), не менялось.

## Дизайн миграции (образец — ДКС)

Тот же трёхчастный разрез, что у `dcs_read`:

1. **Движок владеет форматом.** Новый модуль библиотеки
   [`onec_metadata_schema/rights.py`](../../1c-metadata-schema/src/onec_metadata_schema/rights.py):
   `read_rights(source) -> dict` — нейтральный разбор `<Rights>`, толерантный к namespace,
   по локальным именам тегов (как `dcs_read`). Возвращает **структурно-верную** форму
   (ограничения вложены в свой `<right>`), без таксономии потребителя:
   ```
   {settings: {set_for_new_objects, set_for_attributes_by_default,
               independent_rights_of_child_objects},   # bool|None
    objects:  [{name, rights: [{name, value(bool|None),
                                restrictions: [{field(str|None), condition(str)}]}]}],
    templates:[{name, condition}]}
   ```
2. **Потребитель владеет своей моделью хранения.** `classify_target_qname` (таксономия
   `target_kind`) — это модель индекса C-MCP, не факт про `Rights.xml`, поэтому остаётся
   в C-MCP. `_reshape_rights_from_library` разворачивает нейтральную форму в плоские
   `role_grants`/`role_access_restrictions` C-MCP, применяя таксономию.
3. **Развилка с фолбэком** (снята 2026-07-19). Была: `parse_rights_xml` = «библиотека, иначе
   legacy» с падением в сохранённый ET-парсер. После A/B (0 расхождений на 3010 файлах) форк
   **удалён** — `parse_rights_xml` читает только движком (`_reshape_rights_from_library(read_rights(...))`),
   `parse_rights_xml_via_library`/`parse_rights_xml_legacy` и их хелперы снесены. Сохранён
   skip-on-error: битый/недоступный `Rights.xml` → `None` (роль без грантов), не падение сборки.

### Инвариант паритета (что именно сохранено байт-в-байт)

`_reshape_rights_from_library(read_rights(xml))` даёт **тот же dict**, что старый
`parse_rights_xml`. Сохранены тонкие контракты legacy:

- имена целей/прав/полей/шаблонов — со `strip()`; текст `<condition>` — **без** strip
  (отступы значимы для макросов РЛС);
- `<value>`/флаги — `true`/`false`/иначе `None`;
- пропуск `<object>`/`<right>` с пустым `<name>`;
- порядок документа сохранён; namespace-толерантность (движок читает по локальному имени —
  надмножество прежней «ns-или-без-ns» логики).

## Что сделано (2026-07-19)

- **Библиотека:** `rights.py` + `read_rights`, реэкспорт из `__init__.py`; тест
  `tests/test_rights_read.py` (10 кейсов: флаги, гранты/значения, РЛS с `<field>` и без,
  шаблоны с сохранением пробелов, skip-empty, ns-префиксы, bytes/Element, не-`Rights` корень).
- **C-MCP:** `parse_rights_xml` переведён на движок за развилкой; legacy сохранён как
  фолбэк и A/B-эталон. `_parse_roles`, схема БД, вставка, merge, инструменты — **не менялись**.
- **A/B-верификация:** `parse_rights_xml_legacy` ↔ `parse_rights_xml_via_library` на
  **всех 3010** `Rights.xml` (АСБ/Альфа/Трансгаз/Фитэра): **946 091** грант, **11 993**
  РЛС-ограничения, **3495** шаблонов — **0 расхождений**. Проверены рабочий путь развилки
  (== legacy), фолбэк при `ImportError` (== legacy), отсутствующий файл (→ None). Тесты:
  C-MCP 198 passed / 9 skipped; библиотека 145 passed.
- **`INDEXER_VERSION` не поднимался (17):** форма записываемых данных та же (вывод парсера
  байт-идентичен) → старые БД функционально валидны, полная приёмка на живом MCP —
  формальность (данные не изменились). См. `testing-protocol.md`.

## Что осталось за границей движка (пока)

- **Дескриптор роли** (`Roles/<Name>.xml`, корень `MetaDataObject/Role`) — это MDClasses
  (property-only тип: Name/Synonym/Comment + ObjectBelonging/ExtendedConfigurationObject).
  Технически читается генерик-ридером библиотеки (как `CommonModule`), но C-MCP читает его
  своим `_parse_properties` в обходе `Roles/`. Перевод дескриптора — **низкая ценность**
  (тривиальные свойства) и отдельный микрослайс; здесь намеренно не делался, чтобы держать
  срез узким. Содержательная часть движка — это `Rights.xml`, и она переведена.
- **Write-сторона `Rights.xml`** (конструктор ролей/РЛС в `1c-help-mcp`) — Stage G
  библиотеки: `read_rights` уже даёт форму, которую симметрично собирал бы `build_rights`.
- **Разбор внутренностей РЛС** (`#ПоЗначениям`-пары, анализ языка запросов) — Tier 3,
  как и прежде; движок хранит `condition` дословно.

## Метод верификации (образец для будущих поверхностей ролей)

A/B полного вывода `parse_rights_xml` старый↔новый на всех `Rights.xml` в
`C:\Users\Alex\Documents\1` (скрипт-образец гонялся из scratchpad) → 0 расхождений →
приёмка на живом MCP. `INDEXER_VERSION` поднимать только при смене формы записываемых
данных (этот срез — не менял).
