# Перевод чтения форм (`Form.xml`) на единый движок (`onec_metadata_schema`)

Трек `forms-engine-migration`. Последняя и **самая крупная** поверхность линии единого
движка ([`library-migration.md`](library-migration.md)). В отличие от ролей/ДКС, где
поверхность маленькая и ложится в нейтральный dict целиком, формы — большой EAV-механизм,
и наивное «читаем библиотекой» не проходит. Здесь — дизайн разреза, нейтральная структура
`read_form`, стратегия паритета и пошаговый план A/B-миграции.

## Почему формы — не «роли №2»

Read-парсер форм C-MCP ([`forms.py`](../shared/xml_parser/forms.py) +
[`form_property_flattener.py`](../shared/form_property_flattener.py)) на ~90% состоит из
**модели хранения C-MCP**, а не из знания формата:

- `flatten_entity` строит плоские EAV-строки `property_path`/`property_name`/`ordinal`/
  `value_text`/`value_type` — с C-MCP-инференцией типа (boolean/number/longtext),
  отбрасыванием `UNSET_DATE`, `SKIP_TAGS` по виду сущности. Это осознанная архитектура
  (P1–P8 в [`form-entity-model.md`](form-entity-model.md)): Entity→Types→Properties, таблица
  `form_entity_properties`, типы только в `metadata_type_slots`.
- Движок же (`reader.parse`→`Node`, `decode_properties`) декодирует свойства в **другую**
  модель, заточенную под round-trip сериализацию, а не под EAV-индексацию, и **не отдаёт
  сырой subtree**, который нужен флэттенеру.

Вывод: нельзя ни «просто подставить `parse` под EAV» (модель-приёмник несовместима), ни
перенести EAV в движок (это загрязнило бы его storage-семантикой C-MCP).

## Разрез: движок читает формат, C-MCP владеет EAV

Целевое разделение (то же, что у ролей/ДКС, но с явной границей EAV):

- **Движок — `read_form`**: читает logform-формат (namespace, корневые свойства,
  контейнеры `Attributes`/`Commands`/`ChildItems`/`Items`/`AutoCommandBar`, дерево items и
  ~24 вида элементов, события, функциональные опции, колонки, слоты типов, титулы,
  `ConditionalAppearance`) и отдаёт **нейтральную структурную модель**. Свойства каждой
  сущности отдаёт как **policy-free зеркало subtree** — без skip/инференции/отбрасывания.
- **C-MCP — EAV**: `flatten_entity` (skip/`value_type`/`UNSET_DATE`/ordinals) поверх этого
  зеркала строит `form_entity_properties`. Плюс uuid/модуль/`form_kind` (из соседних файлов
  `Forms/<Имя>.xml`, `Ext/Form/Module.bsl` — их в `Form.xml` нет, читает C-MCP как раньше).

### Ключ к низкому риску EAV: нейтральный узел мимикрирует под ET

`flatten_entity` использует из элемента ровно три вещи: итерацию детей, `.tag` (локальный
после `_local_tag`), `.text`. Нейтральный узел движка (`RawElement{tag(локальный), text,
children}` с `__iter__`) удовлетворяет этому интерфейсу → **`flatten_entity` работает без
изменений**, а зеркало строится из того же ET, что видел старый парсер, → EAV **байт-в-байт**.

### Слоты типов — резолвер движка, по факту байт-в-байт

`type_slots` форм движок строит своим резолвером (`type_slots`/`parse_cfg_type_string`,
уже приведён к паритету с C-MCP при миграции дескрипторов). Бар допускал редкие дифы класса
«≥», но по факту достигнут **полный байт-паритет** (0 расхождений на корпусе). Ключевой нюанс,
всплывший на A/B: контейнер `Settings` реквизита-**DynamicList** несёт типы состава списка
(`cfg:DocumentRef`/`AnyIBRef`/`Characteristic.X`…), и их надо собирать **рекурсивно**
(`.//TypeSet`/`.//Type`) — как в legacy `_extract_slots_from_v8_type_container`, а не по прямым
потомкам (первый прогон терял их → регресс, исправлено). EAV от слотов не зависит (отдельное
типизированное поле, в зеркало не входит).

## Нейтральная структура `read_form(source) -> dict`

Работает над `Ext/Form.xml` (namespace `http://v8.1c.ru/8.3/xcf/logform`), толерантно к
префиксам (обход по локальным именам, как `dcs_read`/`rights`):

```
{
  properties: {PropName: text, ...},            # корневые (AutoSave, AutoTitle, ...)
  events:     [{name, handler, call_type}],      # Events/Event (форма — с call_type)
  attributes: [{name, title, is_main, type_slots, functional_options,
                columns: [{table, name, title, type_slots, functional_options,
                           property_tree}] | None,
                property_tree}],                  # RawElement для EAV
  commands:   [{name, title, action, shortcut, representation, functional_options}],
  items:      [{name, id, type, parent_id, events: [{name, handler}],  # item — без call_type
                functional_options, property_tree}],  # плоский список, порядок документа
  conditional_appearance: <ET.tostring(.//ConditionalAppearance)> | None,
}
```

C-MCP-reshape (`_parse_form_via_library`) добавляет `uuid`/`form_kind`/`module` и разворачивает
`property_tree` → `entity_properties` через существующий `flatten_*`. Инвариант дерева items
(порядок обхода `AutoCommandBar.ChildItems`+`AutoCommandBar.Items`, затем корневой `ChildItems`;
внутри каждого элемента — его `ChildItems`+`Items`; `parent_id` = строковый `@id` родителя)
воспроизводится точно.

## План (пошагово, A/B на каждом шаге)

Верификация — на всех формах реального корпуса `C:\Users\Alex\Documents\1` (АСБ/Планета/
Трансгаз/Фитэра): полный диф записи формы старый↔новый. Бар: **EAV/структура — 0 расхождений;
type_slots — только «≥»**.

- **Шаг 0 — дизайн** (этот док). Нейтральная структура, паритет-стратегия, бар приёмки. **done**
- **Шаг 1 — движок `read_form`** (`onec_metadata_schema/form_read.py` + `RawElement`): полная
  структурная модель + нейтральные зеркала + слоты типов резолвером. Библиотечные тесты
  (структура, порядок items, локализация, слоты, ФО, события, толерантность к префиксам). **done**
- **Шаг 2 — форк C-MCP** `_parse_form` за развилкой `_parse_form_via_library` с фолбэком на
  сохранённый `_parse_form_legacy`; `flatten_*` не меняется (ходит по `RawElement`). A/B полной
  записи формы на всём корпусе. **done**
- **Шаг 3 — очистка (done, 2026-07-19):** форк снят — `_parse_form` читает только движком
  (`_parse_form_via_library` + skip-on-error). Удалены `_parse_form_legacy` и 12 его logform-
  хелперов (`forms.py`), а также logform-слоты типов в `types.py`. Живыми оставлены
  `_read_form_uuid`/`_parse_form_module` (соседние файлы, общие для обоих был-путей) и
  EAV-флэттенер. `INDEXER_VERSION` при этом не менялся форматом EAV (общий bump до 19 — из-за
  политики MXL, не форм). См. CHANGELOG 2026-07-19.

## Результат (2026-07-19)

A/B `_parse_form_legacy` ↔ `_parse_form_via_library` на **22 826** формах корпуса (АСБ/Планета/
Трансгаз/Фитэра): **254 330** реквизитов, **636 198** элементов UI, **3 097 496** EAV-строк —
**0 расхождений** по структуре, EAV **и** слотам типов (полный байт-паритет). Проверены: развилка
(`_parse_form` == legacy), фолбэк при `ImportError` (== legacy), отсутствующий каталог (→ None).
Тесты: C-MCP 198 passed / 9 skipped; библиотека +13 form_read (158 passed). `INDEXER_VERSION` не
поднимался (17 — вывод парсера байт-идентичен).

## Что остаётся в C-MCP (не мигрирует)

- **EAV-флэттенер** (`form_property_flattener.py`): `value_type`-инференция, `UNSET_DATE`,
  `SKIP_TAGS`, ordinals — storage-политика, не формат.
- **uuid/модуль формы/`form_kind`**: из соседних файлов, не из `Form.xml`.
- **Схема БД форм, вставка, MCP-инструменты** ([`form-entity-model.md`](form-entity-model.md)) —
  этот трек их не трогает; меняется только источник чтения `Form.xml`.

## Граница движка после трека

Единым движком читается: дескрипторы, ДКС, права роли (`read_rights`) и **формы**
(`read_form`, формат logform; EAV-проекция остаётся в C-MCP). Вне движка — flowchart
(`xcf/scheme`), модули (BSL), дескриптор роли (тривиальный MDClasses) и MXL-макеты (отложено).
