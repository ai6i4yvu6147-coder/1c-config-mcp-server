# Индексация MXL-макетов (`SpreadsheetDocument`)

Трек `mxl-macet-indexing`. Пятая read-поверхность единого движка
([`library-migration.md`](library-migration.md)) и первое **расширение** после завершения
миграции существующих парсеров. По плейбуку ДКС ([`dcs-schema-indexing.md`](dcs-schema-indexing.md)):
старый парсер `Templates/` MXL **не читал вовсе** → чистое добавление, нулевой риск регресса;
библиотека `onec_metadata_schema` уже **пишет** MXL (`spreadsheet.py`), read-сторона встаёт на тот
же движок.

## Что такое MXL-макет

Не-ДКС путь отчётов/печатных форм: `ПолучитьМакет("Имя").ПолучитьОбласть("Область")`,
заполнение по ячейкам в BSL, вывод `ТабДок.Вывести(...)`. Формат — `Templates/<Имя>/Ext/Template.xml`,
корень `<document>` (ns `http://v8.1c.ru/8.2/data/spreadsheet`). Дескриптор `Templates/<Имя>.xml`
(`MetaDataObject/Template`) несёт **`TemplateType=SpreadsheetDocument`** — это и есть discriminator
(у ДКС — `DataCompositionSchema`).

Масштаб (реальный корпус АСБ/Планета/Трансгаз/Фитэра): **~22 264** MXL-макета — на порядок больше,
чем ДКС-схем. MXL встречается у `Catalog`/`Document`/`Report`/регистров и в `CommonTemplates`.

### Структура (реальная выгрузка)

| Область | XML | Ценность |
|---|---|---|
| Текст ячейки | `rowsItem/row/c/c/tl/v8:item/v8:content` | **высшая** — видимые метки макета |
| `[Токен]` в тексте | `[ПараметрИмя]` внутри `content` | параметр заполнения |
| Ячейка-параметр | `rowsItem/row/c/c/parameter` (leaf) | целиком параметр |
| Именованная область | `namedItem/name` (`xsi:type=NamedItemCells`) | что адресует BSL (`ПолучитьОбласть`) |
| Каталоги оформления | `columns`/`font`/`format`/`line` | не индексируем (layout) |

## Разрез (движок читает формат, C-MCP индексирует)

Тот же разрез, что у ДКС/ролей/форм:

- **Движок — `read_spreadsheet`** ([spreadsheet_read.py](../../1c-metadata-schema/src/onec_metadata_schema/spreadsheet_read.py)):
  нейтральный обход `<document>` по локальным именам (толерантно к богатому реальному формату),
  извлекает только осмысленное — `cells` (`row`/`col`/`text`/`parameter`), `named_areas`,
  `column_count`. Хелперы: `read_spreadsheet_text` (склеенный видимый текст → FTS, `''` при
  пустом — деградация как у ДКС без `<query>`), `spreadsheet_shape_hints` (счётчики + список
  областей/параметров — для среза 2).
- **C-MCP — индексация** ([dcs.py](../shared/xml_parser/dcs.py) `_parse_spreadsheet_templates` +
  [insert_objects.py](../admin_tool/db_manager/insert_objects.py) `_insert_spreadsheet_templates`):
  обход `Templates/` (тот же, что у ДКС, отдельным методом — DCS-путь не тронут), развилка по
  `TemplateType=SpreadsheetDocument`, чтение через движок за фолбэком (`_spreadsheet_reader` → None
  при отсутствии библиотеки → no-op).

## Срез 1 (сделано) — текст → FTS

Видимый текст макета (ячейки + параметры + имена областей) кладётся строкой в `code_search`
(FTS) как модуль `module_type='MxlText'`, `object_name=<Объект>.<Макет>`. Тогда `search_code`
находит макеты по их содержимому (метки, параметры, области) — прямой аналог ДКС-среза 1
(`DcsQuery`). Макеты без текста строки не дают. `INDEXER_VERSION` 17 → **18** (новый
индексируемый контент → пересборка БД).

## Срез 2 (дизайн, не сделано) — структура макета

Как и у ДКС (`dcs_schema` + `get_dcs_schema`): таблица `spreadsheet_template` (денормализованные
`row_count`/`cell_count`/`parameter_count`/`named_area_count` + JSON областей/параметров) + MCP-tool
`get_spreadsheet`/встройка в `get_object_structure`, чтобы агент видел области (`ПолучитьОбласть`) и
параметры макета без FTS. `spreadsheet_shape_hints` уже отдаёт всё нужное. Открытый вопрос: хранить ли
полную сетку ячеек (blob) или только shape-hints; при добавлении — `bump-indexer-version`.

## Верификация

- **Библиотека:** `tests/test_spreadsheet_read.py` (10 кейсов: текст/параметр/`[Токен]`, ru-preference,
  области, FTS-blob, shape-hints, ns-префиксы, bytes/Element, не-`document` корень).
- **Корпус (чистое добавление, legacy нет):** бар — 0 ошибок парсинга, осмысленный текст.
  `read_spreadsheet_text` на АСБ main (**12 545** макетов, крупнейшая конфигурация) — **0 ошибок**,
  2 пустых (деградация), 1.25M областей, 56.5k параметров; корпус целиком ~22 264. Развилка/фолбэк:
  reader None → no-op, битый макет → skip (`skipped_dcs`), объект без `Templates/` → [].
- **Приёмка на живом MCP** — после пересборки: `search_code` находит макет по метке/параметру.

## Граница

`read_spreadsheet` не индексирует оформление (шрифты/форматы/границы/ширины) — это layout, не
семантика. MXL-write (`spreadsheet.py`) и MXL-read (`spreadsheet_read.py`) теперь на одном движке.
