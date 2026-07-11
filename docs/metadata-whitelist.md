## Whitelist метаданных (что индексируется)

### Зачем whitelist

Парсер выгрузки 1С (`shared/xml_parser.py`) намеренно обрабатывает **ограниченный набор типов** (`object_types`), потому что у разных типов метаданных могут быть:

- разные секции XML;
- разные модули/файлы в `Ext`;
- разные важные свойства, которые нужно дополнительно извлекать.

### Внешняя обработка — не whitelist

Файл внешней обработки (`<Имя>.xml`) имеет корень `MetaDataObject/ExternalDataProcessor`, а не `Configuration`. Это **третий вид корня проекта** (наряду с конфигурацией и расширением), не тип внутри `ChildObjects`. Индексация — отдельный трек `external-processor-root` в [`todo.md`](todo.md) через библиотеку `1c-metadata-schema` (Head `metadata-library-cluster.md`). Whitelist `DataProcessor` — только для встроенных обработок внутри конфигурации.

### Текущий whitelist (`shared/xml_parser.py`)

Сейчас парсер обходит `Configuration.xml/ChildObjects` и пытается загружать объекты следующих типов:

- `Catalog`
- `Document`
- `CommonModule`
- `InformationRegister`
- `AccumulationRegister`
- `AccountingRegister`
- `CalculationRegister`
- `ChartOfAccounts`
- `ChartOfCharacteristicTypes`
- `ExchangePlan`
- `Report`
- `DataProcessor`
- `Enum`
- `BusinessProcess`
- `Task`
- `FunctionalOption`
- `CommonCommand` (общие команды: один `CommandModule.bsl` в `CommonCommands/<Имя>/Ext/`)
- `CommonForm` (общие формы: `CommonForms/<Имя>.xml`, структура в `CommonForms/<Имя>/Ext/Form.xml`, модуль в `Ext/Form/Module.bsl`)
- `ScheduledJob` (регламентные задания: один `ScheduledJobs/<Имя>.xml`, без модулей; свойства `MethodName`, `Use`, `Predefined`, …)

Подсистемы (`Subsystem`) **не** в `ChildObjects` — парсятся отдельно из каталога `Subsystems/` (включая вложенные; квалифицированные имена из пути файла).

### Связь с type system и relations

Тип `Subsystem` **индексируется** (фаза 3): связи Content и вложенность — в `metadata_relations` (`subsystem_member`). Тип `Role` **индексируется** (фаза 4): grants/RLS — в `role_grants` и связанных таблицах ([`roles-layer.md`](roles-layer.md)). `EventSubscription` — фаза 5.

### Как добавить новый тип

1. Добавить тип в `object_types` в `shared/xml_parser.py` (и указать папку выгрузки).
2. На реальной выгрузке проверить структуру `<Тип>.xml` и наличие модулей в `Ext`.
3. При необходимости точечно расширить:
   - разбор свойств/реквизитов;
   - список модулей, которые нужно читать;
   - дополнительные сущности, которые должны попадать в SQLite.
4. Пересоздать БД через `admin_tool` (см. `docs/database.md`: **без миграций**).
5. Проверить на рабочем MCP через вызовы tools (см. `docs/testing-protocol.md`).

### Наблюдения по реальным выгрузкам (пример)

В одной из выгрузок в `Configuration.xml` встречаются типы, которых сейчас нет в whitelist, например:

- `Subsystem`
- `Role`
- `HTTPService`
- `EventSubscription`
- `CommonPicture`
- `DefinedType`
- `XDTOPackage`

Это **не баг**, а ожидаемое поведение whitelist: такие типы не индексируются, пока не добавлены осознанно.

