import os
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

from .xml_helpers import _winlong


REGISTER_TYPES = (
    'InformationRegister',
    'AccumulationRegister',
    'AccountingRegister',
    'CalculationRegister',
)

# Виды объектов, чей дескриптор читается единым движком формата (onec_metadata_schema)
# вместо старого ручного обхода ElementTree. Растёт пачками за одной развилкой, каждый
# перевод доказан A/B-дифом дескриптор-полей на реальных выгрузках. Пока НЕ переведён
# только Subsystem (отдельный обход каталога Subsystems/). См. docs/library-migration.md.
LIBRARY_MIGRATED_TYPES = frozenset({
    'DataProcessor', 'Report',
    'Catalog', 'Document', 'Enum',
    'InformationRegister', 'AccumulationRegister', 'AccountingRegister', 'CalculationRegister',
    'ChartOfAccounts', 'ChartOfCharacteristicTypes', 'ExchangePlan',
    'BusinessProcess', 'Task',
    'CommonModule', 'CommonCommand', 'CommonForm',
    'ScheduledJob', 'FunctionalOption', 'DefinedType',
})

# Подмножество LIBRARY_MIGRATED_TYPES без реквизитов/секций/ТЧ: весь предметный смысл — в
# свойствах дескриптора (+ соседние файлы модулей/форм/команд, читаемые тем же file-walk,
# что и старый путь). Собираются отдельным ассемблером `_assemble_property_only_object`,
# чтобы не усложнять ветку типов-с-реквизитами. См. docs/library-migration.md (шаг 3).
PROPERTY_ONLY_MIGRATED_TYPES = frozenset({
    'CommonModule', 'CommonCommand', 'CommonForm',
    'ScheduledJob', 'FunctionalOption', 'DefinedType',
})


class ConfigurationParserCore:
    """Configuration.xml top-level parsing, per-object dispatch, subsystems, properties/attributes."""

    def __init__(self, config_path):
        """
        Args:
            config_path: Путь к файлу Configuration.xml
        """
        self.config_path = Path(config_path)
        self.root_dir = self.config_path.parent
        # Накопленное время по категориям парсинга (заполняется во время parse()),
        # используется вызывающей стороной (db_manager) для разбивки в progress_callback.
        self.stage_seconds = {}
        # Формы, не разобранные из-за исключения (см. FormsMixin._parse_form) — заполняется
        # во время parse(), используется вызывающей стороной для отчёта в progress_callback
        # (P-2: ошибка раньше уходила только в stdout print и терялась в GUI-сборке).
        self.skipped_forms = []
        # СКД-схемы, не прочитанные из-за исключения (см. TemplatesDcsMixin._parse_dcs_schemas)
        # — тот же контракт «пропуск, не падение», что и для форм.
        self.skipped_dcs = []

    @contextmanager
    def _accumulate(self, stage_name):
        """Копит время выполнения блока в self.stage_seconds[stage_name] (суммарно за весь parse())."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stage_seconds[stage_name] = self.stage_seconds.get(stage_name, 0.0) + (time.perf_counter() - t0)

    def parse(self):
        """Парсит корень выгрузки и возвращает структуру данных.

        Виды корня: `MetaDataObject/Configuration` (конфигурация и расширение — один тег,
        различаются по ConfigurationExtensionPurpose/ObjectBelonging),
        `MetaDataObject/ExternalDataProcessor` (внешняя обработка) и
        `MetaDataObject/ExternalReport` (внешний отчёт) — внешние объекты читаются через
        библиотеку onec_metadata_schema, см. external_processor.py.
        """
        tree = ET.parse(_winlong(self.config_path))
        root = tree.getroot()

        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)

        if config is not None:
            return self._parse_configuration(config, ns)

        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        if self._get_object_element(root, 'ExternalDataProcessor', md_ns) is not None:
            return self._parse_external_data_processor(root)
        if self._get_object_element(root, 'ExternalReport', md_ns) is not None:
            return self._parse_external_report(root)

        return {'name': '', 'objects': []}

    def _parse_configuration(self, config, ns):
        """Разбор корня `MetaDataObject/Configuration` (конфигурация или расширение)."""
        properties = config.find('md:Properties', ns)
        config_name = ''
        if properties is not None:
            # Имя конфигурации: в формате 2.20 — Properties/Name, в старом — возможно md:n
            name_elem = properties.find('md:Name', ns)
            if name_elem is None:
                name_elem = properties.find('md:n', ns)
            if name_elem is not None and name_elem.text:
                config_name = name_elem.text.strip()

        objects = self._parse_child_objects(config, ns)
        with self._accumulate('subsystems'):
            objects.extend(self._parse_subsystems())
        with self._accumulate('roles'):
            objects.extend(self._parse_roles())

        extension_purpose = ''
        if properties is not None:
            purpose_elem = properties.find('md:ConfigurationExtensionPurpose', ns)
            if purpose_elem is not None and purpose_elem.text:
                extension_purpose = purpose_elem.text.strip()

        return {
            'name': config_name,
            'extension_purpose': extension_purpose,
            'objects': objects
        }

    def _parse_child_objects(self, config, ns):
        """Извлекает список дочерних объектов"""
        objects = []
        child_objects = config.find('md:ChildObjects', ns)

        if child_objects is None:
            return objects

        object_types = {
            'Catalog': 'Catalogs',
            'Document': 'Documents',
            'CommonModule': 'CommonModules',
            'InformationRegister': 'InformationRegisters',
            'AccumulationRegister': 'AccumulationRegisters',
            'AccountingRegister': 'AccountingRegisters',
            'CalculationRegister': 'CalculationRegisters',
            'ChartOfAccounts': 'ChartsOfAccounts',
            'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes',
            'ExchangePlan': 'ExchangePlans',
            'Report': 'Reports',
            'DataProcessor': 'DataProcessors',
            'Enum': 'Enums',
            'BusinessProcess': 'BusinessProcesses',
            'Task': 'Tasks',
            'FunctionalOption': 'FunctionalOptions',
            'CommonCommand': 'CommonCommands',
            'CommonForm': 'CommonForms',
            'ScheduledJob': 'ScheduledJobs',
            'DefinedType': 'DefinedTypes',
        }

        for obj_type, folder_name in object_types.items():
            for element in child_objects.findall(f'md:{obj_type}', ns):
                obj_name = element.text
                if obj_name:
                    obj_data = self._parse_object(obj_name, obj_type, folder_name)
                    if obj_data:
                        objects.append(obj_data)

        return objects

    def _subsystem_qualified_name(self, xml_path):
        """Квалифицированное имя подсистемы из пути под Subsystems/."""
        rel = xml_path.relative_to(self.root_dir / 'Subsystems')
        parts = []
        for part in rel.parts:
            if part == 'Subsystems':
                continue
            if part.endswith('.xml'):
                part = part[:-4]
            parts.append(part)
        return '.'.join(parts)

    def _parse_subsystems(self):
        """Парсит все подсистемы (включая вложенные) из каталога Subsystems/.

        Подсистема — единственный whitelist-тип, читаемый не через `_parse_object`, а
        отдельным обходом каталога (`parse()` библиотеки — однофайловый, сборку папки не
        делает): имя подсистемы — квалифицированное из пути (`_subsystem_qualified_name`),
        не из дескриптора. Сам дескриптор `<Имя>.xml` читается единым движком
        (`_parse_subsystem_via_library`), при неудаче — старым ET-путём (`_parse_subsystem_legacy`),
        как и прочие типы за развилкой. См. docs/library-migration.md (шаг 4).
        """
        subsystems_root = self.root_dir / 'Subsystems'
        if not subsystems_root.is_dir():
            return []

        results = []
        for xml_file in sorted(subsystems_root.rglob('*.xml')):
            if 'Ext' in xml_file.parts:
                continue
            record = self._parse_subsystem_via_library(xml_file)
            if record is None:
                record = self._parse_subsystem_legacy(xml_file)
            if record is not None:
                results.append(record)
        return results

    def _parse_subsystem_via_library(self, xml_file):
        """Дескриптор подсистемы единым движком → тот же dict, что даёт
        `_parse_subsystem_legacy`. Возвращает None, если библиотека не нашла дескриптор
        `Subsystem` (тогда вызывающий откатывается на старый путь — напр. корень
        `MetaDataObject.Subsystem`, который `_find_descriptor_node` не распознаёт)."""
        try:
            import onec_metadata_schema
        except ImportError as exc:  # pragma: no cover - packaging guard
            raise RuntimeError(
                "Единый движок формата требует библиотеку '1c-metadata-schema' "
                "(onec_metadata_schema). Установите её "
                "(`pip install -e ../1c-metadata-schema`) и пересоберите portable."
            ) from exc
        try:
            node = onec_metadata_schema.parse(xml_file)
        except (ET.ParseError, OSError):
            # OSError includes FileNotFoundError from Windows MAX_PATH (260 char)
            # limitations on very deeply nested Subsystems trees.
            return None
        descriptor = self._find_descriptor_node(node, 'Subsystem')
        if descriptor is None:
            return None

        properties = self._adapt_descriptor_properties(descriptor, 'Subsystem')
        content_refs = self._subsystem_content_refs(descriptor.properties.get('Content'))
        child_subsystem_names = [
            child.ref
            for child in descriptor.children
            if child.tag == 'Subsystem' and child.collection == 'ChildObjects' and child.ref
        ]
        return self._subsystem_record(
            self._subsystem_qualified_name(xml_file),
            descriptor.uuid or '',
            properties,
            content_refs,
            child_subsystem_names,
        )

    def _parse_subsystem_legacy(self, xml_file):
        """Старый ET-путь разбора дескриптора подсистемы (фолбэк за развилкой)."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        try:
            root = ET.parse(_winlong(xml_file)).getroot()
        except (ET.ParseError, OSError):
            return None
        obj_elem = self._get_object_element(root, 'Subsystem', md_ns)
        if obj_elem is None:
            return None

        properties = self._parse_properties(root, 'Subsystem')
        uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''

        content_refs = []
        properties_elem = root.find(f'.//{{{md_ns}}}Properties')
        if properties_elem is not None:
            content_elem = properties_elem.find(f'{{{md_ns}}}Content')
            if content_elem is not None:
                for item in content_elem:
                    text = (item.text or '').strip()
                    if text and '.' in text:
                        content_refs.append(text)

        child_subsystem_names = []
        child_objects = root.find(f'.//{{{md_ns}}}ChildObjects')
        if child_objects is not None:
            for sub_elem in child_objects.findall(f'{{{md_ns}}}Subsystem'):
                if sub_elem.text and sub_elem.text.strip():
                    child_subsystem_names.append(sub_elem.text.strip())

        return self._subsystem_record(
            self._subsystem_qualified_name(xml_file),
            uuid,
            properties,
            content_refs,
            child_subsystem_names,
        )

    @staticmethod
    def _subsystem_content_refs(content):
        """Ссылки состава подсистемы из декодированного Content: элементы
        `<xr:Item xsi:type="xr:MDObjectRef">Тип.Имя</xr:Item>` → их текст. Паритет с legacy:
        только непустые, содержащие '.' (в реальных выгрузках Content — всегда плоские
        `xr:Item`-ссылки)."""
        if not isinstance(content, dict):
            return []
        items = content.get('Item')
        if items is None:
            return []
        if not isinstance(items, list):
            items = [items]
        refs = []
        for item in items:
            text = item.get('value') if isinstance(item, dict) else item
            if isinstance(text, str) and text.strip() and '.' in text:
                refs.append(text.strip())
        return refs

    @staticmethod
    def _subsystem_record(qname, uuid, properties, content_refs, child_subsystem_names):
        """Единый dict-контракт подсистемы (без `dcs_schemas` — у подсистем нет шаблонов)."""
        return {
            'name': qname,
            'type': 'Subsystem',
            'uuid': uuid,
            'properties': properties,
            'modules': [],
            'forms': [],
            'tabular_sections': [],
            'dimensions': [],
            'resources': [],
            'enum_values': [],
            'commands': [],
            'content_refs': content_refs,
            'child_subsystem_names': child_subsystem_names,
        }

    def _parse_object(self, name, obj_type, folder_name):
        """Разбор объекта метаданных. Развилка единого движка: типы из
        LIBRARY_MIGRATED_TYPES читаются через onec_metadata_schema (дескриптор → адаптер
        из external_processor.py), остальные — старым путём `_parse_object_legacy`. Каждый
        перевод типа доказан A/B-дифом дескриптор-полей на реальных выгрузках. См.
        docs/library-migration.md.
        """
        if obj_type in LIBRARY_MIGRATED_TYPES:
            obj = self._parse_object_via_library(name, obj_type, folder_name)
            if obj is not None:
                return obj
            # Дескриптор не распознан библиотекой — не теряем объект молча, идём старым путём.
        return self._parse_object_legacy(name, obj_type, folder_name)

    def _parse_object_via_library(self, name, obj_type, folder_name):
        """Читает дескриптор `<Name>.xml` единым движком и собирает тот же dict, что даёт
        `_parse_object_legacy`. Дескриптор-часть (uuid, properties, реквизиты/ТЧ/секции
        регистра/значения перечисления, слоты типов) — из onec_metadata_schema; модули/формы/
        команды/СКД/flowchart — теми же file-walk методами, что и старый путь (побайтово те же
        данные). Возвращает None, если библиотека не нашла дескриптор нужного вида (тогда
        вызывающий откатывается на старый путь).
        """
        xml_file = self.root_dir / folder_name / f"{name}.xml"
        if not os.path.exists(_winlong(xml_file)):
            return None
        try:
            import onec_metadata_schema
        except ImportError as exc:  # pragma: no cover - packaging guard
            raise RuntimeError(
                "Единый движок формата требует библиотеку '1c-metadata-schema' "
                "(onec_metadata_schema). Установите её "
                "(`pip install -e ../1c-metadata-schema`) и пересоберите portable."
            ) from exc

        node = onec_metadata_schema.parse(xml_file)
        descriptor = self._find_descriptor_node(node, obj_type)
        if descriptor is None:
            return None

        # Property-only типы (нет реквизитов/секций/ТЧ) собираются отдельно — их развилка
        # модулей/форм/команд по виду объекта отличается от типов-с-реквизитами.
        if obj_type in PROPERTY_ONLY_MIGRATED_TYPES:
            return self._assemble_property_only_object(
                descriptor, name, obj_type, folder_name, xml_file
            )

        with self._accumulate('properties'):
            properties = self._adapt_descriptor_properties(descriptor, obj_type)

        # Дескриптор-блоки по виду объекта (то же дерево, что в _parse_object_legacy):
        # регистры → секции Dimension/Resource/Attribute; Enum → значения; прочие → ТЧ.
        tabular_sections = []
        dimensions = []
        resources = []
        register_attributes = []
        enum_values = []
        with self._accumulate('sections'):
            if obj_type in REGISTER_TYPES:
                dimensions = self._adapt_register_section(descriptor, 'Dimension')
                resources = self._adapt_register_section(descriptor, 'Resource')
                register_attributes = self._adapt_register_section(descriptor, 'Attribute')
            elif obj_type == 'Enum':
                enum_values = [
                    self._adapt_enum_value(c) for c in descriptor.children if c.tag == 'EnumValue'
                ]
            else:
                tabular_sections = [
                    self._adapt_tabular_section_node(c)
                    for c in descriptor.children if c.tag == 'TabularSection'
                ]

        # Соседние файлы — те же методы, что в старом пути (побайтово те же данные).
        with self._accumulate('modules'):
            modules = self._parse_modules(name, folder_name)
        default_forms = {
            'Element': properties.get('default_object_form') or properties.get('auxiliary_object_form'),
            'List': properties.get('default_list_form') or properties.get('auxiliary_list_form'),
            'Choice': properties.get('default_choice_form') or properties.get('auxiliary_choice_form'),
        }
        with self._accumulate('forms'):
            forms = self._parse_forms(name, folder_name, default_forms)
        # Команды читаются из сырого XML — file-walk метод берёт ET-корень, как и старый путь.
        root = ET.parse(_winlong(xml_file)).getroot()
        with self._accumulate('commands'):
            commands = self._parse_object_commands(root, name, folder_name, obj_type)
        with self._accumulate('dcs'):
            dcs_schemas = self._parse_dcs_schemas(name, folder_name)

        route_points = []
        route_transitions = []
        if obj_type == 'BusinessProcess':
            with self._accumulate('flowchart'):
                flowchart = self._parse_flowchart(name, folder_name)
            route_points = flowchart['route_points']
            route_transitions = flowchart['route_transitions']

        result = {
            'name': name,
            'type': obj_type,
            'uuid': descriptor.uuid or '',
            'properties': properties,
            'modules': modules,
            'forms': forms,
            'tabular_sections': tabular_sections,
            'dimensions': dimensions,
            'resources': resources,
            'enum_values': enum_values,
            'commands': commands,
            'dcs_schemas': dcs_schemas,
        }
        if obj_type in REGISTER_TYPES:
            result['attributes'] = register_attributes
        if obj_type == 'BusinessProcess':
            result['route_points'] = route_points
            result['route_transitions'] = route_transitions
        return result

    def _assemble_property_only_object(self, descriptor, name, obj_type, folder_name, xml_file):
        """Собирает dict property-only объекта (тот же, что даёт `_parse_object_legacy`):
        нет реквизитов/секций/ТЧ, весь смысл — в свойствах дескриптора. Соседние файлы
        (модули/формы/команды/СКД) читаются теми же file-walk методами, что и старый путь
        (побайтово те же данные). Развилка modules/forms/commands по виду объекта — точный
        паритет с `_parse_object_legacy` (см. docs/library-migration.md, шаг 3).
        """
        with self._accumulate('properties'):
            properties = self._adapt_property_only_properties(descriptor, obj_type)

        # Модули/формы по виду объекта (как в _parse_object_legacy):
        #   CommonForm — форма через _parse_common_form, модулей на уровне объекта нет;
        #   ScheduledJob/DefinedType — ни модулей, ни форм;
        #   CommonModule/CommonCommand/FunctionalOption — обычный file-walk (+CommandModule.bsl).
        if obj_type == 'CommonForm':
            modules = []
            with self._accumulate('forms'):
                forms = self._parse_common_form(name, folder_name, descriptor.uuid or '')
        elif obj_type in ('ScheduledJob', 'DefinedType'):
            modules = []
            forms = []
        else:
            with self._accumulate('modules'):
                modules = self._parse_modules(name, folder_name)
                if obj_type == 'CommonCommand':
                    cmd_path = self.root_dir / folder_name / name / 'Ext' / 'CommandModule.bsl'
                    if os.path.exists(_winlong(cmd_path)):
                        with open(_winlong(cmd_path), 'r', encoding='utf-8-sig') as f:
                            modules.append({'type': 'CommandModule', 'code': f.read()})
            default_forms = {
                'Element': properties.get('default_object_form') or properties.get('auxiliary_object_form'),
                'List': properties.get('default_list_form') or properties.get('auxiliary_list_form'),
                'Choice': properties.get('default_choice_form') or properties.get('auxiliary_choice_form'),
            }
            with self._accumulate('forms'):
                forms = self._parse_forms(name, folder_name, default_forms)

        # Команды: читают только CommonModule/FunctionalOption (паритет со списком исключений
        # старого пути). У остальных — [].
        if obj_type in ('CommonCommand', 'CommonForm', 'ScheduledJob', 'DefinedType'):
            commands = []
        else:
            root = ET.parse(_winlong(xml_file)).getroot()
            with self._accumulate('commands'):
                commands = self._parse_object_commands(root, name, folder_name, obj_type)

        with self._accumulate('dcs'):
            dcs_schemas = self._parse_dcs_schemas(name, folder_name)

        result = {
            'name': name,
            'type': obj_type,
            'uuid': descriptor.uuid or '',
            'properties': properties,
            'modules': modules,
            'forms': forms,
            'tabular_sections': [],
            'dimensions': [],
            'resources': [],
            'enum_values': [],
            'commands': commands,
            'dcs_schemas': dcs_schemas,
        }
        if obj_type == 'DefinedType':
            # Тип на уровне объекта: библиотечный `.Type` байт-идентичен старому
            # `_extract_type_slots(obj_elem)` (тот же контейнер Properties/Type).
            result['type_slots'] = descriptor.properties.get('Type') or []
        return result

    def _adapt_property_only_properties(self, descriptor, obj_type):
        """properties-dict property-only объекта. База — общий адаптер (синоним/комментарий/
        принадлежность + standard/custom_attributes; у этих типов реквизитов нет → custom=[]),
        поверх — мелкие свойства ScheduledJob/FunctionalOption. CommonModule/CommonCommand/
        CommonForm/DefinedType несут только базу (доп. флаги дескриптора — Global/Group/
        FormType… — старый путь не читал, паритет их тоже опускает)."""
        properties = self._adapt_descriptor_properties(descriptor, obj_type)
        if obj_type == 'ScheduledJob':
            self._add_scheduled_job_props(descriptor, properties)
        elif obj_type == 'FunctionalOption':
            self._add_functional_option_props(descriptor, properties)
        return properties

    @staticmethod
    def _add_scheduled_job_props(descriptor, properties):
        """MethodName/Description/Key (строки), Use/Predefined (bool), Restart* (int) —
        из свойств дескриптора; пустые/self-closing опускаются (паритет с _parse_properties)."""
        for src, key in (('MethodName', 'method_name'), ('Description', 'description'), ('Key', 'key')):
            value = descriptor.properties.get(src)
            if isinstance(value, str) and value.strip():
                properties[key] = value.strip()
        for src, key in (('Use', 'use'), ('Predefined', 'predefined')):
            value = descriptor.properties.get(src)
            if isinstance(value, str) and value.strip():
                properties[key] = value.strip().lower() == 'true'
        for src, key in (
            ('RestartCountOnFailure', 'restart_count_on_failure'),
            ('RestartIntervalOnFailure', 'restart_interval_on_failure'),
        ):
            value = descriptor.properties.get(src)
            if isinstance(value, str) and value.strip():
                try:
                    properties[key] = int(value.strip())
                except ValueError:
                    pass

    def _add_functional_option_props(self, descriptor, properties):
        """Location (строка), PrivilegedGetMode (bool), content_refs (ссылки состава) —
        из свойств дескриптора; паритет с ветвью FunctionalOption в _parse_properties."""
        location = descriptor.properties.get('Location')
        if isinstance(location, str) and location.strip():
            properties['location'] = location.strip()
        priv = descriptor.properties.get('PrivilegedGetMode')
        if isinstance(priv, str) and priv.strip():
            properties['privileged_get_mode'] = priv.strip().lower() == 'true'
        refs = self._content_object_refs(descriptor.properties.get('Content'))
        if refs:
            properties['content_refs'] = refs

    @staticmethod
    def _content_object_refs(content):
        """Ссылки состава функциональной опции из декодированного Content:
        `{'Object': ref | [refs]}` → [refs]. В реальных выгрузках Content — всегда плоские
        `xr:Object` (проверено на 1277 непустых случаях, 5 проектов), что совпадает с
        `.//Object` старого пути."""
        if not isinstance(content, dict):
            return []
        objs = content.get('Object')
        if isinstance(objs, list):
            return [o.strip() for o in objs if isinstance(o, str) and o.strip()]
        if isinstance(objs, str) and objs.strip():
            return [objs.strip()]
        return []

    def _adapt_descriptor_properties(self, descriptor, obj_type):
        """properties-dict дескриптора из библиотечного Node: синоним/комментарий/
        принадлежность + имена форм по умолчанию (последний сегмент пути) + custom_attributes
        (у регистров реквизиты уходят в obj['attributes'], поэтому здесь пусто).

        `standard_attributes` — всегда []: старый `_parse_standard_attributes` на реальных
        выгрузках тоже пуст (ищет теги `{MDClasses}Code/…`, тогда как стандартные реквизиты
        лежат как `xcf:StandardAttribute name="Code"` — паритет подтверждён на 600 объектах).
        """
        properties = {'standard_attributes': [], 'custom_attributes': []}

        synonym = self._node_synonym(descriptor)
        if synonym:
            properties['synonym'] = synonym
        comment = descriptor.properties.get('Comment')
        if comment:
            properties['comment'] = comment
        belonging = descriptor.properties.get('ObjectBelonging')
        if isinstance(belonging, str) and belonging.strip():
            properties['object_belonging'] = belonging.strip()
        extended = descriptor.properties.get('ExtendedConfigurationObject')
        if isinstance(extended, str) and extended.strip():
            properties['extended_configuration_object'] = extended.strip()

        # Имена форм по умолчанию (последний сегмент пути ObjectType.Name.Form.FormName) —
        # только те 6 тегов, что читает старый _parse_properties (не Folder-варианты).
        for tag, key in (
            ('DefaultObjectForm', 'default_object_form'),
            ('DefaultListForm', 'default_list_form'),
            ('DefaultChoiceForm', 'default_choice_form'),
            ('AuxiliaryObjectForm', 'auxiliary_object_form'),
            ('AuxiliaryListForm', 'auxiliary_list_form'),
            ('AuxiliaryChoiceForm', 'auxiliary_choice_form'),
        ):
            value = descriptor.properties.get(tag)
            if isinstance(value, str) and value.strip():
                path = value.strip()
                properties[key] = path.split('.')[-1] if '.' in path else path

        if obj_type not in REGISTER_TYPES:
            properties['custom_attributes'] = [
                self._adapt_attribute_node(c) for c in descriptor.children if c.tag == 'Attribute'
            ]
        return properties

    def _adapt_register_section(self, descriptor, child_tag):
        """Секция регистра (Dimension/Resource/Attribute) из детей Node →
        [{name, type_slots, title, comment}] (как `_parse_register_section`)."""
        return [
            {
                'name': c.properties.get('Name') or c.name or '',
                'type_slots': c.properties.get('Type') or [],
                'title': self._node_synonym(c),
                'comment': c.properties.get('Comment') or '',
            }
            for c in descriptor.children if c.tag == child_tag
        ]

    def _adapt_enum_value(self, node):
        """EnumValue-узел → dict как `_parse_enum_value_elem` (name/title/comment/order/
        object_belonging/extended_configuration_object)."""
        order = node.properties.get('Order')
        try:
            order = int(order) if order is not None and str(order).strip() != '' else None
        except (TypeError, ValueError):
            order = None
        belonging = node.properties.get('ObjectBelonging')
        belonging = belonging.strip() if isinstance(belonging, str) and belonging.strip() else None
        extended = node.properties.get('ExtendedConfigurationObject')
        extended = extended.strip() if isinstance(extended, str) and extended.strip() else None
        return {
            'name': node.properties.get('Name') or node.name or '',
            'title': self._node_synonym(node),
            'comment': node.properties.get('Comment') or '',
            'order': order,
            'object_belonging': belonging,
            'extended_configuration_object': extended,
        }

    def _parse_object_legacy(self, name, obj_type, folder_name):
        """Парсит отдельный объект метаданных"""
        xml_file = self.root_dir / folder_name / f"{name}.xml"

        if not os.path.exists(_winlong(xml_file)):
            return None

        tree = ET.parse(_winlong(xml_file))
        root = tree.getroot()

        # Получаем UUID
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        obj_elem = self._get_object_element(root, obj_type, md_ns)
        uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''

        # Получаем свойства
        with self._accumulate('properties'):
            properties = self._parse_properties(root, obj_type)

        # Получаем модули и формы
        if obj_type == 'CommonForm':
            modules = []
            with self._accumulate('forms'):
                forms = self._parse_common_form(name, folder_name, uuid)
        elif obj_type in ('ScheduledJob', 'DefinedType'):
            modules = []
            forms = []
        else:
            with self._accumulate('modules'):
                modules = self._parse_modules(name, folder_name)
                if obj_type == 'CommonCommand':
                    cmd_path = self.root_dir / folder_name / name / 'Ext' / 'CommandModule.bsl'
                    if os.path.exists(_winlong(cmd_path)):
                        with open(_winlong(cmd_path), 'r', encoding='utf-8-sig') as f:
                            modules.append({'type': 'CommandModule', 'code': f.read()})

            # Имена форм по умолчанию для определения form_kind
            default_forms = {
                'Element': properties.get('default_object_form') or properties.get('auxiliary_object_form'),
                'List': properties.get('default_list_form') or properties.get('auxiliary_list_form'),
                'Choice': properties.get('default_choice_form') or properties.get('auxiliary_choice_form'),
            }
            with self._accumulate('forms'):
                forms = self._parse_forms(name, folder_name, default_forms)

        # Парсим дополнительные структуры по типу объекта
        if obj_type == 'CommonForm':
            tabular_sections = []
            dimensions = []
            resources = []
            enum_values = []
        elif obj_type in REGISTER_TYPES:
            tabular_sections = []
            with self._accumulate('sections'):
                dimensions = self._parse_register_section(root, 'Dimensions', obj_type)
                resources = self._parse_register_section(root, 'Resources', obj_type)
                attributes = self._parse_register_section(root, 'Attributes', obj_type)
            enum_values = []
        elif obj_type == 'DefinedType':
            tabular_sections = []
            dimensions = []
            resources = []
            enum_values = []
        elif obj_type == 'Enum':
            tabular_sections = []
            dimensions = []
            resources = []
            with self._accumulate('sections'):
                enum_values = self._parse_enum_values(root)
        else:
            with self._accumulate('sections'):
                tabular_sections = self._parse_tabular_sections(root, obj_type)
            dimensions = []
            resources = []
            enum_values = []

        route_points = []
        route_transitions = []
        if obj_type == 'BusinessProcess':
            with self._accumulate('flowchart'):
                flowchart = self._parse_flowchart(name, folder_name)
            route_points = flowchart['route_points']
            route_transitions = flowchart['route_transitions']

        with self._accumulate('commands'):
            commands = [] if obj_type in ('CommonCommand', 'CommonForm', 'ScheduledJob', 'DefinedType') else self._parse_object_commands(root, name, folder_name, obj_type)

        # DCS schemas owned via Templates/ (new read path; self-guards on the dir, so
        # object types that never own templates just get []). See TemplatesDcsMixin.
        with self._accumulate('dcs'):
            dcs_schemas = self._parse_dcs_schemas(name, folder_name)

        result = {
            'name': name,
            'type': obj_type,
            'uuid': uuid,
            'properties': properties,
            'modules': modules,
            'forms': forms,
            'tabular_sections': tabular_sections,
            'dimensions': dimensions,
            'resources': resources,
            'enum_values': enum_values,
            'commands': commands,
            'dcs_schemas': dcs_schemas,
        }
        if obj_type in REGISTER_TYPES:
            result['attributes'] = attributes
        if obj_type == 'DefinedType':
            result['type_slots'] = (
                self._extract_type_slots(obj_elem) if obj_elem is not None else []
            )
        if obj_type == 'BusinessProcess':
            result['route_points'] = route_points
            result['route_transitions'] = route_transitions
        return result

    def _parse_properties(self, root, obj_type=None):
        """Извлекает свойства объекта"""
        props = {}
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        properties = root.find(f'.//{{{md_ns}}}Properties')

        if properties is not None:
            # Синоним
            ns = {'v8': 'http://v8.1c.ru/8.1/data/core'}
            synonym_elem = properties.find('.//v8:content', ns)
            if synonym_elem is not None and synonym_elem.text:
                props['synonym'] = synonym_elem.text

            # Комментарий
            comment_elem = properties.find(f'.//{{{md_ns}}}Comment')
            if comment_elem is None:
                comment_elem = properties.find('.//Comment')
            if comment_elem is not None and comment_elem.text:
                props['comment'] = comment_elem.text

            # Принадлежность (расширение: Own / Adopted)
            ob_elem = properties.find(f'{{{md_ns}}}ObjectBelonging')
            if ob_elem is not None and ob_elem.text:
                props['object_belonging'] = ob_elem.text.strip()
            eco_elem = properties.find(f'{{{md_ns}}}ExtendedConfigurationObject')
            if eco_elem is not None and eco_elem.text:
                props['extended_configuration_object'] = eco_elem.text.strip()

            # Имена форм по умолчанию (последний сегмент пути: ObjectType.Name.Form.FormName)
            for tag, key in (
                ('DefaultObjectForm', 'default_object_form'),
                ('DefaultListForm', 'default_list_form'),
                ('DefaultChoiceForm', 'default_choice_form'),
                ('AuxiliaryObjectForm', 'auxiliary_object_form'),
                ('AuxiliaryListForm', 'auxiliary_list_form'),
                ('AuxiliaryChoiceForm', 'auxiliary_choice_form'),
            ):
                elem = properties.find(f'{{{md_ns}}}{tag}')
                if elem is not None and elem.text and elem.text.strip():
                    path = elem.text.strip()
                    props[key] = path.split('.')[-1] if '.' in path else path

        # Регламентные задания: MethodName, Use, расписание перезапуска и т.д.
        if obj_type == 'ScheduledJob':
            props['standard_attributes'] = []
            props['custom_attributes'] = []
            if properties is not None:
                for tag, key in (
                    ('MethodName', 'method_name'),
                    ('Description', 'description'),
                    ('Key', 'key'),
                ):
                    elem = properties.find(f'{{{md_ns}}}{tag}')
                    if elem is not None and elem.text and elem.text.strip():
                        props[key] = elem.text.strip()
                for tag, key in (('Use', 'use'), ('Predefined', 'predefined')):
                    elem = properties.find(f'{{{md_ns}}}{tag}')
                    if elem is not None and elem.text:
                        props[key] = elem.text.strip().lower() == 'true'
                for tag, key in (
                    ('RestartCountOnFailure', 'restart_count_on_failure'),
                    ('RestartIntervalOnFailure', 'restart_interval_on_failure'),
                ):
                    elem = properties.find(f'{{{md_ns}}}{tag}')
                    if elem is not None and elem.text and elem.text.strip():
                        try:
                            props[key] = int(elem.text.strip())
                        except ValueError:
                            pass
            return props

        # Подсистемы: только свойства, без реквизитов
        if obj_type == 'Subsystem':
            props['standard_attributes'] = []
            props['custom_attributes'] = []
            return props

        # Функциональные опции: свои свойства (Location, PrivilegedGetMode, Content)
        if obj_type == 'FunctionalOption':
            props['standard_attributes'] = []
            props['custom_attributes'] = []
            loc_elem = properties.find(f'{{{md_ns}}}Location')
            if loc_elem is not None and loc_elem.text and loc_elem.text.strip():
                props['location'] = loc_elem.text.strip()
            priv_elem = properties.find(f'{{{md_ns}}}PrivilegedGetMode')
            if priv_elem is not None and priv_elem.text and priv_elem.text.strip():
                props['privileged_get_mode'] = priv_elem.text.strip().lower() == 'true'
            content_elem = properties.find(f'{{{md_ns}}}Content')
            if content_elem is not None:
                content_refs = []
                for obj_ref in content_elem.findall('.//{http://v8.1c.ru/8.3/xcf/readable}Object'):
                    if obj_ref.text and obj_ref.text.strip():
                        content_refs.append(obj_ref.text.strip())
                if content_refs:
                    props['content_refs'] = content_refs
            return props

        # Стандартные и кастомные реквизиты
        if obj_type == 'DefinedType':
            props['standard_attributes'] = []
            props['custom_attributes'] = []
        elif obj_type in REGISTER_TYPES:
            props['standard_attributes'] = self._parse_standard_attributes(root, obj_type)
            # Реквизиты регистра — в obj['attributes'] (_parse_register_section); не дублировать здесь.
            props['custom_attributes'] = []
        elif obj_type:
            props['standard_attributes'] = self._parse_standard_attributes(root, obj_type)
            props['custom_attributes'] = self._parse_custom_attributes(root, obj_type)
        else:
            props['standard_attributes'] = []
            props['custom_attributes'] = []

        return props

    def _parse_standard_attributes(self, root, obj_type):
        """Извлекает стандартные атрибуты объекта"""
        standard_attrs = []

        # Стандартные атрибуты по типам объектов
        standard_by_type = {
            'Catalog': ['Code', 'Description', 'IsFolder', 'Parent', 'Owner'],
            'Document': ['Date', 'Number', 'Posted', 'DeletionMark'],
            'InformationRegister': ['Recorder', 'Period', 'Active', 'LineNumber'],
            'AccumulationRegister': ['Recorder', 'LineNumber', 'Active', 'DeletionMark'],
            'AccountingRegister': ['Recorder', 'LineNumber'],
            'CalculationRegister': ['Recorder', 'LineNumber', 'Period'],
            'BusinessProcess': ['Date', 'Number', 'Posted', 'DeletionMark', 'State'],
            'Task': ['Date', 'Number', 'Posted', 'DeletionMark', 'Importance', 'Executed']
        }

        attrs_to_find = standard_by_type.get(obj_type, [])

        # Namespace для MDClasses
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        # Ищем в StandardAttributes с учетом namespace
        std_attrs_elem = root.find(f'.//{{{md_ns}}}StandardAttributes')

        for attr_name in attrs_to_find:
            # Ищем элемент с именем атрибута
            if std_attrs_elem is not None:
                attr_elem = std_attrs_elem.find(f'.//{{{md_ns}}}{attr_name}')
            else:
                attr_elem = root.find(f'.//{{{md_ns}}}{attr_name}')

            if attr_elem is not None:
                attr_data = {
                    'name': attr_name,
                    'type_slots': self._extract_type_slots(attr_elem),
                    'title': self._extract_synonym(attr_elem),
                    'comment': self._extract_comment(attr_elem),
                    'is_standard': True,
                    'standard_type': attr_name
                }
                standard_attrs.append(attr_data)

        return standard_attrs

    def _get_object_element(self, root, obj_type, md_ns):
        """Возвращает элемент объекта (Catalog, Document и т.д.). Учитывает формат корня MetaDataObject.Catalog."""
        obj_elem = root.find(f'{{{md_ns}}}{obj_type}')
        if obj_elem is not None:
            return obj_elem
        obj_elem = root.find(f'.//{{{md_ns}}}{obj_type}')
        if obj_elem is not None:
            return obj_elem
        # Корень файла может быть MetaDataObject.Catalog (расширения/выгрузка платформы)
        local_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        if local_tag == obj_type or local_tag == f'MetaDataObject.{obj_type}':
            return root
        return None

    def _get_attribute_name(self, attr_elem, md_ns):
        """Имя реквизита: атрибут name или Properties/Name (формат выгрузки 2.20)."""
        name = attr_elem.get('name', '')
        if name:
            return name
        props = attr_elem.find(f'{{{md_ns}}}Properties')
        if props is not None:
            name_elem = props.find(f'{{{md_ns}}}Name')
            if name_elem is not None and name_elem.text:
                return name_elem.text.strip()
        return ''

    def _parse_custom_attributes(self, root, obj_type=None):
        """Извлекает кастомные атрибуты: из Attributes или из ChildObjects (только Attribute, не TabularSection)."""
        attributes = []
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        if obj_type:
            obj_elem = self._get_object_element(root, obj_type, md_ns)
        else:
            obj_elem = None

        if obj_elem is None:
            return attributes

        # Вариант 1: классическая обёртка Attributes
        attrs_elem = obj_elem.find(f'{{{md_ns}}}Attributes')
        if attrs_elem is not None:
            for attr in attrs_elem.findall(f'{{{md_ns}}}Attribute'):
                attr_name = attr.get('name', '') or self._get_attribute_name(attr, md_ns)
                if attr_name:
                    attributes.append({
                        'name': attr_name,
                        'type_slots': self._extract_type_slots(attr),
                        'title': self._extract_synonym(attr),
                        'comment': self._extract_comment(attr),
                        'is_standard': False,
                        'standard_type': None
                    })
            return attributes

        # Вариант 2: выгрузка 2.20 — реквизиты в ChildObjects рядом с TabularSection, Form
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is not None:
            for child in child_objects:
                local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_tag != 'Attribute':
                    continue
                attr_name = self._get_attribute_name(child, md_ns)
                if attr_name:
                    attributes.append({
                        'name': attr_name,
                        'type_slots': self._extract_type_slots(child),
                        'title': self._extract_synonym(child),
                        'comment': self._extract_comment(child),
                        'is_standard': False,
                        'standard_type': None
                    })
        return attributes
