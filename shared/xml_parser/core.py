import os
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

from .xml_helpers import _winlong


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

    @contextmanager
    def _accumulate(self, stage_name):
        """Копит время выполнения блока в self.stage_seconds[stage_name] (суммарно за весь parse())."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stage_seconds[stage_name] = self.stage_seconds.get(stage_name, 0.0) + (time.perf_counter() - t0)

    def parse(self):
        """Парсит конфигурацию и возвращает структуру данных"""
        tree = ET.parse(_winlong(self.config_path))
        root = tree.getroot()

        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)

        if config is None:
            return {'name': '', 'objects': []}

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

        return {
            'name': config_name,
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
        """Парсит все подсистемы (включая вложенные) из каталога Subsystems/."""
        subsystems_root = self.root_dir / 'Subsystems'
        if not subsystems_root.is_dir():
            return []

        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        results = []
        for xml_file in sorted(subsystems_root.rglob('*.xml')):
            if 'Ext' in xml_file.parts:
                continue
            try:
                root = ET.parse(_winlong(xml_file)).getroot()
            except (ET.ParseError, OSError):
                # OSError includes FileNotFoundError from Windows MAX_PATH (260 char)
                # limitations on very deeply nested Subsystems trees.
                continue
            if self._get_object_element(root, 'Subsystem', md_ns) is None:
                continue

            qname = self._subsystem_qualified_name(xml_file)
            properties = self._parse_properties(root, 'Subsystem')
            obj_elem = self._get_object_element(root, 'Subsystem', md_ns)
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

            results.append({
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
            })
        return results

    def _parse_object(self, name, obj_type, folder_name):
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
        elif obj_type == 'ScheduledJob':
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
        register_types = ('InformationRegister', 'AccumulationRegister', 'AccountingRegister', 'CalculationRegister')
        if obj_type == 'CommonForm':
            tabular_sections = []
            dimensions = []
            resources = []
            enum_values = []
        elif obj_type in register_types:
            tabular_sections = []
            with self._accumulate('sections'):
                dimensions = self._parse_register_section(root, 'Dimensions', obj_type)
                resources = self._parse_register_section(root, 'Resources', obj_type)
                attributes = self._parse_register_section(root, 'Attributes', obj_type)
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
            commands = [] if obj_type in ('CommonCommand', 'CommonForm', 'ScheduledJob') else self._parse_object_commands(root, name, folder_name, obj_type)

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
        }
        if obj_type in register_types:
            result['attributes'] = attributes
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

        # Стандартные атрибуты
        if obj_type:
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
