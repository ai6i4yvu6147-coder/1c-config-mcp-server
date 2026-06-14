import xml.etree.ElementTree as ET
import os
import json
from pathlib import Path

from .metadata_type_resolver import parse_cfg_type_string

class ConfigurationParser:
    """Парсер XML-выгрузки конфигурации 1С"""
    
    def __init__(self, config_path):
        """
        Args:
            config_path: Путь к файлу Configuration.xml
        """
        self.config_path = Path(config_path)
        self.root_dir = self.config_path.parent
        
    def parse(self):
        """Парсит конфигурацию и возвращает структуру данных"""
        tree = ET.parse(self.config_path)
        root = tree.getroot()
        
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)
        
        if config is None:
            return {'name': '', 'objects': []}
        
        properties = config.find('md:Properties', ns)
        config_name = ''
        if properties is not None:
            # Имя конфигурации: в формате 2.20 — Properties/Name, в старом — возможно md:n
            name_elem = properties.find('md:Name', ns) or properties.find('md:n', ns)
            if name_elem is not None and name_elem.text:
                config_name = name_elem.text.strip()
        
        objects = self._parse_child_objects(config, ns)
        
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
    
    def _parse_object(self, name, obj_type, folder_name):
        """Парсит отдельный объект метаданных"""
        xml_file = self.root_dir / folder_name / f"{name}.xml"

        if not xml_file.exists():
            return None

        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Получаем UUID
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        obj_elem = self._get_object_element(root, obj_type, md_ns)
        uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''

        # Получаем свойства
        properties = self._parse_properties(root, obj_type)

        # Получаем модули и формы
        if obj_type == 'CommonForm':
            modules = []
            forms = self._parse_common_form(name, folder_name, uuid)
        elif obj_type == 'ScheduledJob':
            modules = []
            forms = []
        else:
            modules = self._parse_modules(name, folder_name)
            if obj_type == 'CommonCommand':
                cmd_path = self.root_dir / folder_name / name / 'Ext' / 'CommandModule.bsl'
                if cmd_path.exists():
                    with open(cmd_path, 'r', encoding='utf-8-sig') as f:
                        modules.append({'type': 'CommandModule', 'code': f.read()})

            # Имена форм по умолчанию для определения form_kind
            default_forms = {
                'Element': properties.get('default_object_form') or properties.get('auxiliary_object_form'),
                'List': properties.get('default_list_form') or properties.get('auxiliary_list_form'),
                'Choice': properties.get('default_choice_form') or properties.get('auxiliary_choice_form'),
            }
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
            dimensions = self._parse_register_section(root, 'Dimensions', obj_type)
            resources = self._parse_register_section(root, 'Resources', obj_type)
            attributes = self._parse_register_section(root, 'Attributes', obj_type)
            enum_values = []
        elif obj_type == 'Enum':
            tabular_sections = []
            dimensions = []
            resources = []
            enum_values = self._parse_enum_values(root)
        else:
            tabular_sections = self._parse_tabular_sections(root, obj_type)
            dimensions = []
            resources = []
            enum_values = []

        route_points = []
        route_transitions = []
        if obj_type == 'BusinessProcess':
            flowchart = self._parse_flowchart(name, folder_name)
            route_points = flowchart['route_points']
            route_transitions = flowchart['route_transitions']

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
    
    def _dedupe_type_strings_preserve_order(self, items):
        seen = set()
        out = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _find_metadata_type_container(self, elem, md_ns):
        """Контейнер типа в метаданных: обычно Properties/Type (MDClasses)."""
        props = elem.find(f'{{{md_ns}}}Properties')
        if props is not None:
            t = props.find(f'{{{md_ns}}}Type')
            if t is not None:
                return t
        return elem.find(f'.//{{{md_ns}}}Type')

    def _v8_child_text(self, parent, v8_ns, local_name):
        elem = parent.find(f'{{{v8_ns}}}{local_name}')
        if elem is not None and elem.text is not None:
            return elem.text.strip()
        return None

    def _extract_qualifiers_from_type_container(self, type_elem, v8_ns):
        """Извлекает квалификаторы примитива из контейнера Type."""
        num_q = type_elem.find(f'{{{v8_ns}}}NumberQualifiers')
        if num_q is not None:
            digits = self._v8_child_text(num_q, v8_ns, 'Digits')
            fraction = self._v8_child_text(num_q, v8_ns, 'FractionDigits')
            return {
                'digits': int(digits) if digits is not None else None,
                'fraction': int(fraction) if fraction is not None else None,
                'allowed_sign': self._v8_child_text(num_q, v8_ns, 'AllowedSign'),
            }
        str_q = type_elem.find(f'{{{v8_ns}}}StringQualifiers')
        if str_q is not None:
            length = self._v8_child_text(str_q, v8_ns, 'Length')
            return {
                'length': int(length) if length is not None else None,
                'allowed_length': self._v8_child_text(str_q, v8_ns, 'AllowedLength'),
            }
        date_q = type_elem.find(f'{{{v8_ns}}}DateQualifiers')
        if date_q is not None:
            return {
                'date_fractions': self._v8_child_text(date_q, v8_ns, 'DateFractions'),
            }
        return None

    def _slot_from_type_string(self, type_str, qualifiers=None):
        slot = parse_cfg_type_string(type_str)
        if slot.get('kind') == 'primitive' and qualifiers:
            slot = dict(slot)
            slot['qualifiers'] = qualifiers
        return slot

    def _extract_type_slots(self, elem):
        """Извлекает структурированные слоты типа атрибута/колонки."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        v8_ns = 'http://v8.1c.ru/8.1/data/core'

        type_elem = self._find_metadata_type_container(elem, md_ns)
        if type_elem is not None:
            direct = []
            for child in list(type_elem):
                if child.tag == f'{{{v8_ns}}}Type' and child.text and child.text.strip():
                    direct.append(child.text.strip())
            if direct:
                qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
                slots = []
                for type_str in self._dedupe_type_strings_preserve_order(direct):
                    slot = self._slot_from_type_string(
                        type_str,
                        qualifiers if len(direct) == 1 else None,
                    )
                    slots.append(slot)
                return slots

            from_set = []
            for ts in type_elem.findall(f'.//{{{v8_ns}}}TypeSet'):
                if ts.text and ts.text.strip():
                    from_set.append(ts.text.strip())
                for t in ts.findall(f'.//{{{v8_ns}}}Type'):
                    if t.text and t.text.strip():
                        from_set.append(t.text.strip())
            if from_set:
                qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
                slots = []
                for type_str in self._dedupe_type_strings_preserve_order(from_set):
                    slot = parse_cfg_type_string(type_str)
                    if qualifiers and slot.get('kind') == 'primitive':
                        slot = dict(slot)
                        slot['qualifiers'] = qualifiers
                    slots.append(slot)
                return slots

        value_type = elem.find(f'.//{{{md_ns}}}ValueType')
        if value_type is not None:
            refs = []
            for ref in value_type.findall(f'.//{{{v8_ns}}}Ref'):
                if ref.text and ref.text.strip():
                    refs.append(ref.text.strip())
            if refs:
                return [
                    self._slot_from_type_string(type_str)
                    for type_str in self._dedupe_type_strings_preserve_order(refs)
                ]

        v8_type = elem.find(f'.//{{{v8_ns}}}Type')
        if v8_type is not None and v8_type.text and v8_type.text.strip():
            return [self._slot_from_type_string(v8_type.text.strip())]

        return []

    def _extract_attribute_type(self, elem):
        """Извлекает тип атрибута как строку (legacy helper для тестов)."""
        slots = self._extract_type_slots(elem)
        raws = [s.get('raw') for s in slots if s.get('raw')]
        if raws:
            return ', '.join(self._dedupe_type_strings_preserve_order(raws))
        return ''
    
    def _extract_synonym(self, elem):
        """Извлекает синоним атрибута"""
        v8_ns = 'http://v8.1c.ru/8.1/data/core'
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        
        # Ищем в v8:content с учетом namespace
        synonym_elem = elem.find(f'.//{{{v8_ns}}}content')
        if synonym_elem is not None and synonym_elem.text:
            return synonym_elem.text
        
        # Ищем в Synonym с учетом namespace
        syn_elem = elem.find(f'.//{{{md_ns}}}Synonym')
        if syn_elem is not None:
            syn_content = syn_elem.find(f'.//{{{v8_ns}}}content')
            if syn_content is not None and syn_content.text:
                return syn_content.text
        
        return ''

    def _extract_comment(self, elem):
        """Извлекает комментарий атрибута/табличной части/значения перечисления из Properties/Comment."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        props = elem.find(f'{{{md_ns}}}Properties')
        if props is None:
            return ''
        comment_elem = props.find(f'{{{md_ns}}}Comment')
        if comment_elem is None:
            comment_elem = props.find('Comment')
        if comment_elem is not None and comment_elem.text:
            return comment_elem.text
        return ''
    
    def _parse_tabular_sections(self, root, obj_type):
        """Извлекает табличные части: из TabularSections или из ChildObjects (формат выгрузки 2.20)."""
        result = []
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return result

        # Вариант 1: контейнер TabularSections
        ts_container = obj_elem.find(f'{{{md_ns}}}TabularSections')
        if ts_container is not None:
            for ts_elem in ts_container.findall(f'{{{md_ns}}}TabularSection'):
                ts_name = ts_elem.get('name', '') or self._get_attribute_name(ts_elem, md_ns)
                if not ts_name:
                    continue
                ts_title = self._extract_synonym(ts_elem)
                columns = []
                attrs_elem = ts_elem.find(f'{{{md_ns}}}Attributes')
                if attrs_elem is not None:
                    for attr in attrs_elem.findall(f'{{{md_ns}}}Attribute'):
                        col_name = attr.get('name', '') or self._get_attribute_name(attr, md_ns)
                        if col_name:
                            columns.append({
                                'name': col_name,
                                'type_slots': self._extract_type_slots(attr),
                                'title': self._extract_synonym(attr),
                                'comment': self._extract_comment(attr),
                            })
                result.append({'name': ts_name, 'title': ts_title, 'comment': self._extract_comment(ts_elem), 'columns': columns})
            return result

        # Вариант 2: выгрузка 2.20 — табличные части в ChildObjects как TabularSection
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return result
        for child in child_objects:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag != 'TabularSection':
                continue
            ts_name = child.get('name', '') or self._get_attribute_name(child, md_ns)
            if not ts_name:
                continue
            ts_title = self._extract_synonym(child)
            columns = []
            ts_child_objects = child.find(f'{{{md_ns}}}ChildObjects')
            if ts_child_objects is not None:
                for col_elem in ts_child_objects:
                    col_local = col_elem.tag.split('}')[-1] if '}' in col_elem.tag else col_elem.tag
                    if col_local != 'Attribute':
                        continue
                    col_name = self._get_attribute_name(col_elem, md_ns)
                    if col_name:
                        columns.append({
                            'name': col_name,
                            'type_slots': self._extract_type_slots(col_elem),
                            'title': self._extract_synonym(col_elem),
                            'comment': self._extract_comment(col_elem),
                        })
            result.append({'name': ts_name, 'title': ts_title, 'comment': self._extract_comment(child), 'columns': columns})
        return result

    def _parse_register_section(self, root, section_tag, obj_type):
        """Извлекает секцию регистра: Dimensions, Resources или Attributes.
        Поддерживает классический формат (контейнеры Dimensions/Resources) и формат 2.20 (Dimension/Resource в ChildObjects).
        """
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        singular_map = {
            'Dimensions': 'Dimension',
            'Resources': 'Resource',
            'Attributes': 'Attribute',
        }
        child_tag = singular_map.get(section_tag, section_tag[:-1])

        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return []

        container = obj_elem.find(f'{{{md_ns}}}{section_tag}')
        if container is not None:
            result = []
            for elem in container.findall(f'{{{md_ns}}}{child_tag}'):
                elem_name = elem.get('name', '') or self._get_attribute_name(elem, md_ns)
                if elem_name:
                    result.append({
                        'name': elem_name,
                        'type_slots': self._extract_type_slots(elem),
                        'title': self._extract_synonym(elem),
                        'comment': self._extract_comment(elem),
                    })
            return result

        # Формат 2.20: Dimension/Resource лежат в ChildObjects без обёрток Dimensions/Resources
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for elem in child_objects.findall(f'{{{md_ns}}}{child_tag}'):
            elem_name = elem.get('name', '') or self._get_attribute_name(elem, md_ns)
            if elem_name:
                result.append({
                    'name': elem_name,
                    'type_slots': self._extract_type_slots(elem),
                    'title': self._extract_synonym(elem),
                    'comment': self._extract_comment(elem),
                })
        return result

    def _parse_enum_value_elem(self, ev_elem, md_ns):
        """Из одного элемента EnumValue собирает словарь для БД."""
        ev_name = ev_elem.get('name', '') or self._get_attribute_name(ev_elem, md_ns)
        if not ev_name:
            return None
        ev_title = self._extract_synonym(ev_elem)
        ev_order = None
        ev_belonging = None
        ev_extended = None
        props_elem = ev_elem.find(f'{{{md_ns}}}Properties')
        if props_elem is not None:
            order_elem = props_elem.find(f'{{{md_ns}}}Order')
            if order_elem is not None and order_elem.text:
                try:
                    ev_order = int(order_elem.text)
                except ValueError:
                    pass
            ob_elem = props_elem.find(f'{{{md_ns}}}ObjectBelonging')
            if ob_elem is not None and ob_elem.text:
                ev_belonging = ob_elem.text.strip()
            eco_elem = props_elem.find(f'{{{md_ns}}}ExtendedConfigurationObject')
            if eco_elem is not None and eco_elem.text:
                ev_extended = eco_elem.text.strip()
        return {
            'name': ev_name,
            'title': ev_title,
            'comment': self._extract_comment(ev_elem),
            'order': ev_order,
            'object_belonging': ev_belonging,
            'extended_configuration_object': ev_extended,
        }

    def _parse_enum_values(self, root):
        """Извлекает значения перечисления. Поддерживает контейнер EnumValues и формат 2.20 (EnumValue в ChildObjects)."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        obj_elem = self._get_object_element(root, 'Enum', md_ns)
        if obj_elem is None:
            return []

        ev_container = obj_elem.find(f'{{{md_ns}}}EnumValues')
        if ev_container is not None:
            result = []
            for ev_elem in ev_container.findall(f'{{{md_ns}}}EnumValue'):
                ev = self._parse_enum_value_elem(ev_elem, md_ns)
                if ev:
                    result.append(ev)
            return result

        # Формат 2.20: значения перечисления в ChildObjects без обёртки EnumValues
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for ev_elem in child_objects.findall(f'{{{md_ns}}}EnumValue'):
            ev = self._parse_enum_value_elem(ev_elem, md_ns)
            if ev:
                result.append(ev)
        return result

    def _parse_flowchart(self, name, folder_name):
        """Точки маршрута и переходы бизнес-процесса из Ext/Flowchart.xml."""
        flowchart_path = self.root_dir / folder_name / name / 'Ext' / 'Flowchart.xml'
        empty = {'route_points': [], 'route_transitions': []}
        if not flowchart_path.exists():
            return empty

        sch_ns = 'http://v8.1c.ru/8.3/xcf/scheme'
        tree = ET.parse(flowchart_path)
        root = tree.getroot()
        items = root.find(f'{{{sch_ns}}}Items')
        if items is None:
            return empty

        route_points = []
        route_transitions = []
        for child in items:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag == 'ConnectionLine':
                transition = self._parse_flowchart_transition(child, sch_ns)
                if transition:
                    route_transitions.append(transition)
                continue
            point = self._parse_flowchart_point(child, local_tag, sch_ns)
            if point:
                route_points.append(point)

        return {'route_points': route_points, 'route_transitions': route_transitions}

    def _parse_flowchart_point(self, elem, point_type, sch_ns):
        """Одна точка маршрута (Start, Activity, Condition, …)."""
        props = elem.find(f'{{{sch_ns}}}Properties')
        if props is None:
            return None
        name_elem = props.find(f'{{{sch_ns}}}Name')
        point_name = name_elem.text.strip() if name_elem is not None and name_elem.text else ''
        if not point_name:
            return None

        tab_order = self._flowchart_int(props.find(f'{{{sch_ns}}}TabOrder'))
        point = {
            'name': point_name,
            'type': point_type,
            'title': self._extract_synonym(props),
            'uuid': elem.get('uuid', '') or '',
            'tab_order': tab_order,
            'true_port': None,
            'false_port': None,
            'group': None,
        }
        if point_type == 'Condition':
            point['true_port'] = self._flowchart_int(props.find(f'{{{sch_ns}}}TruePortIndex'))
            point['false_port'] = self._flowchart_int(props.find(f'{{{sch_ns}}}FalsePortIndex'))
        elif point_type == 'Activity':
            group_elem = props.find(f'{{{sch_ns}}}Group')
            if group_elem is not None and group_elem.text:
                point['group'] = group_elem.text.strip().lower() == 'true'
        return point

    def _parse_flowchart_transition(self, elem, sch_ns):
        """Переход между точками (ConnectionLine)."""
        props = elem.find(f'{{{sch_ns}}}Properties')
        if props is None:
            return None
        decorative = props.find(f'{{{sch_ns}}}DecorativeLine')
        if decorative is not None and decorative.text and decorative.text.strip().lower() == 'true':
            return None
        connect = props.find(f'{{{sch_ns}}}Connect')
        if connect is None:
            return None
        from_elem = connect.find(f'{{{sch_ns}}}From')
        to_elem = connect.find(f'{{{sch_ns}}}To')
        if from_elem is None or to_elem is None:
            return None
        from_item = from_elem.find(f'{{{sch_ns}}}Item')
        to_item = to_elem.find(f'{{{sch_ns}}}Item')
        if from_item is None or to_item is None or not from_item.text or not to_item.text:
            return None
        from_port_elem = from_elem.find(f'{{{sch_ns}}}PortIndex')
        return {
            'from': from_item.text.strip(),
            'to': to_item.text.strip(),
            'from_port': self._flowchart_int(from_port_elem),
            'title': self._extract_synonym(props),
        }

    def _flowchart_int(self, elem):
        if elem is None or not elem.text:
            return None
        try:
            return int(elem.text.strip())
        except ValueError:
            return None

    def _parse_object_commands(self, root, obj_name, folder_name, obj_type):
        """Команды объекта: ChildObjects/Command в XML + модуль Commands/<Name>/Ext/CommandModule.bsl."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return []
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for child in child_objects:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag != 'Command':
                continue
            cmd_uuid = child.get('uuid', '') or ''
            props = child.find(f'{{{md_ns}}}Properties')
            cmd_name = ''
            synonym = ''
            ob = None
            eco = None
            if props is not None:
                name_elem = props.find(f'{{{md_ns}}}Name')
                if name_elem is not None and name_elem.text:
                    cmd_name = name_elem.text.strip()
            if not cmd_name:
                cmd_name = child.get('name', '') or self._get_attribute_name(child, md_ns)
            if not cmd_name:
                continue
            synonym = self._extract_synonym(child)
            if props is not None:
                ob_elem = props.find(f'{{{md_ns}}}ObjectBelonging')
                if ob_elem is not None and ob_elem.text:
                    ob = ob_elem.text.strip()
                eco_elem = props.find(f'{{{md_ns}}}ExtendedConfigurationObject')
                if eco_elem is not None and eco_elem.text:
                    eco = eco_elem.text.strip()
            module_path = self.root_dir / folder_name / obj_name / 'Commands' / cmd_name / 'Ext' / 'CommandModule.bsl'
            module_code = None
            if module_path.exists():
                with open(module_path, 'r', encoding='utf-8-sig') as f:
                    module_code = f.read()
            result.append({
                'name': cmd_name,
                'synonym': synonym,
                'uuid': cmd_uuid,
                'object_belonging': ob,
                'extended_configuration_object': eco,
                'module_code': module_code,
            })
        return result

    def _parse_modules(self, obj_name, folder_name):
        """Извлекает код модулей объекта"""
        modules = []
        obj_dir = self.root_dir / folder_name / obj_name / 'Ext'
        
        if not obj_dir.exists():
            return modules
        
        # Типы модулей
        module_files = {
            'Module.bsl': 'Module',
            'ManagerModule.bsl': 'ManagerModule',
            'ObjectModule.bsl': 'ObjectModule',
        }
        
        for file_name, module_type in module_files.items():
            module_path = obj_dir / file_name
            if module_path.exists():
                with open(module_path, 'r', encoding='utf-8-sig') as f:
                    code = f.read()
                modules.append({
                    'type': module_type,
                    'code': code
                })
        
        return modules
    
    def _parse_forms(self, obj_name, folder_name, default_forms=None):
        """Парсит формы объекта. default_forms: {'Element': name|None, 'List': name|None, 'Choice': name|None} для form_kind."""
        forms = []
        forms_dir = self.root_dir / folder_name / obj_name / 'Forms'
        default_forms = default_forms or {}

        if not forms_dir.exists():
            return forms

        for form_dir in forms_dir.iterdir():
            if form_dir.is_dir():
                form_data = self._parse_form(form_dir)
                if form_data:
                    form_name = form_data['name']
                    form_kind = None
                    if default_forms.get('List') == form_name:
                        form_kind = 'List'
                    elif default_forms.get('Choice') == form_name:
                        form_kind = 'Choice'
                    elif default_forms.get('Element') == form_name:
                        form_kind = 'Element'
                    form_data['form_kind'] = form_kind
                    forms.append(form_data)

        return forms

    def _parse_common_form(self, name, folder_name, uuid):
        """Парсит общую форму: CommonForms/<Имя>/Ext/Form.xml, модуль — Ext/Form/Module.bsl."""
        form_dir = self.root_dir / folder_name / name
        form_data = self._parse_form(form_dir, uuid=uuid, form_name=name)
        if form_data:
            return [form_data]
        return []
    
    def _parse_form(self, form_dir, uuid=None, form_name=None):
        """Парсит одну форму. uuid/form_name — для CommonForm (метаданные в CommonForms/<Имя>.xml)."""
        form_xml = form_dir / 'Ext' / 'Form.xml'
        
        if not form_xml.exists():
            return None
        
        try:
            form_name = form_name or form_dir.name
            if uuid is None:
                # UUID из файла метаданных формы (ИмяФормы.xml в каталоге формы объекта)
                form_meta_xml = form_dir / f'{form_name}.xml'
                uuid = ''
                if form_meta_xml.exists():
                    try:
                        meta_tree = ET.parse(form_meta_xml)
                        meta_root = meta_tree.getroot()
                        form_elem = meta_root.find('.//{http://v8.1c.ru/8.3/MDClasses}Form')
                        if form_elem is not None:
                            uuid = form_elem.get('uuid', '')
                    except Exception:
                        pass
            
            # Парсим структуру формы из Form.xml
            tree = ET.parse(form_xml)
            root = tree.getroot()
            
            # Namespace для форм
            ns = {'lf': 'http://v8.1c.ru/8.3/xcf/logform'}
            
            # Properties формы (корневые элементы)
            properties = self._parse_form_properties(root, ns)
            
            # Events формы
            events = self._parse_form_events(root, ns)
            
            # Attributes
            attributes = self._parse_form_attributes(root, ns)
            
            # Commands
            commands = self._parse_form_commands(root, ns)
            
            # ChildItems (элементы UI)
            items = self._parse_form_items(root, ns)
            
            # ConditionalAppearance
            conditional_appearance = self._parse_form_conditional_appearance(root, ns)
            
            # Модуль формы
            module = self._parse_form_module(form_dir)
            
            return {
                'name': form_name,
                'uuid': uuid,
                'properties': properties,
                'events': events,
                'attributes': attributes,
                'commands': commands,
                'items': items,
                'conditional_appearance': conditional_appearance,
                'module': module
            }
        except Exception as e:
            print(f"Ошибка парсинга формы {form_dir.name}: {e}")
            return None
    
    def _parse_form_properties(self, root, ns):
        """Извлекает свойства формы"""
        properties = {}
        
        # Namespace по умолчанию для Form.xml
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        
        # Список интересующих свойств
        prop_names = [
            'AutoSave', 'AutoTitle', 'CommandBarLocation', 
            'VerticalScroll', 'AutoTime', 'UsePostingMode',
            'RepostOnWrite', 'AutoSaveDataInSettings'
        ]
        
        for prop_name in prop_names:
            elem = root.find(f'{{{default_ns}}}{prop_name}')
            if elem is not None and elem.text:
                properties[prop_name] = elem.text
        
        return properties
    
    def _parse_form_events(self, root, ns):
        """Извлекает события формы"""
        events = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        events_elem = root.find(f'{{{default_ns}}}Events')
        
        if events_elem is None:
            return events
        
        for event in events_elem.findall(f'{{{default_ns}}}Event'):
            event_data = {
                'name': event.get('name', ''),
                'handler': event.text or '',
                'call_type': event.get('callType', '')
            }
            events.append(event_data)
        
        return events
    
    def _parse_form_attributes(self, root, ns):
        """Извлекает реквизиты формы"""
        attributes = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        attrs_elem = root.find(f'{{{default_ns}}}Attributes')
        
        if attrs_elem is None:
            return attributes
        
        for attr in attrs_elem.findall(f'{{{default_ns}}}Attribute'):
            attr_data = {
                'name': attr.get('name', ''),
                'type_slots': self._extract_logform_type_slots(attr),
                'title': self._extract_localized_string(attr, 'Title'),
                'is_main': attr.find(f'{{{default_ns}}}MainAttribute') is not None,
                'columns': self._extract_columns(attr),
                'query_text': self._extract_query_text(attr),
                'functional_options': self._extract_form_functional_options(attr, default_ns),
            }
            attributes.append(attr_data)
        
        return attributes
    
    def _parse_form_commands(self, root, ns):
        """Извлекает команды формы"""
        commands = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        cmds_elem = root.find(f'{{{default_ns}}}Commands')
        
        if cmds_elem is None:
            return commands
        
        for cmd in cmds_elem.findall(f'{{{default_ns}}}Command'):
            cmd_data = {
                'name': cmd.get('name', ''),
                'title': self._extract_localized_string(cmd, 'Title'),
                'action': self._get_element_text(cmd, 'Action'),
                'shortcut': self._get_element_text(cmd, 'Shortcut'),
                'representation': self._get_element_text(cmd, 'Representation'),
                'functional_options': self._extract_form_functional_options(cmd, default_ns),
            }
            commands.append(cmd_data)
        
        return commands
    
    def _parse_form_items(self, root, ns):
        """Извлекает элементы UI формы"""
        items = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        
        # Обрабатываем AutoCommandBar
        auto_cmd_bar = root.find(f'{{{default_ns}}}AutoCommandBar')
        if auto_cmd_bar is not None:
            # Внутри AutoCommandBar реальные элементы лежат в контейнерах ChildItems/Items,
            # сам AutoCommandBar — не элемент дерева UI.
            auto_child = auto_cmd_bar.find(f'{{{default_ns}}}ChildItems')
            if auto_child is not None:
                items.extend(self._parse_child_items(auto_child, None))
            auto_items = auto_cmd_bar.find(f'{{{default_ns}}}Items')
            if auto_items is not None:
                items.extend(self._parse_child_items(auto_items, None))
        
        # Обрабатываем ChildItems
        child_items = root.find(f'{{{default_ns}}}ChildItems')
        if child_items is not None:
            items.extend(self._parse_child_items(child_items, None))
        
        return items
    
    def _parse_child_items(self, parent_elem, parent_id):
        """Рекурсивно парсит дочерние элементы в порядке появления в документе."""
        items = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        
        # Множество поддерживаемых типов элементов UI (для быстрой проверки)
        item_types_set = {
            'Button', 'InputField', 'Table', 'UsualGroup',
            'ButtonGroup', 'Popup', 'LabelField', 'CheckBoxField',
            'RadioButtonField', 'Pages', 'Page', 'CommandBar',
            'LabelDecoration', 'PictureDecoration', 'SpreadSheetDocumentField',
            'HTMLDocumentField', 'FormattedDocumentField', 'FlowchartField',
            'PlannerField', 'GanttChartField', 'ExtendedTooltip', 'SearchControl',
        }
        
        for elem in parent_elem:
            local_tag = elem.tag.split('}')[-1] if elem.tag else ''
            if local_tag not in item_types_set:
                continue
            props = self._extract_item_properties(elem)
            visible = None
            enabled = None
            if props:
                v = props.get('Visible', '').strip().lower()
                visible = True if v == 'true' else False if v == 'false' else None
                e = props.get('Enabled', '').strip().lower()
                enabled = True if e == 'true' else False if e == 'false' else None
            cmd_name_raw = self._get_element_text(elem, 'CommandName')
            item_data = {
                'name': elem.get('name', ''),
                'id': elem.get('id', ''),
                'type': local_tag,
                'parent_id': parent_id,
                'data_path': self._get_element_text(elem, 'DataPath'),
                'title': self._extract_localized_string(elem, 'Title'),
                'visible': visible,
                'enabled': enabled,
                'events': self._extract_item_events(elem),
                'functional_options': self._extract_form_functional_options(elem, default_ns),
                'command_name': cmd_name_raw.strip() if cmd_name_raw else '',
            }
            items.append(item_data)
            # В логформе дочерние элементы могут лежать в разных контейнерах:
            # - ChildItems (обычное дерево UI)
            # - Items (часто внутри CommandBar/панелей команд)
            # Не обрабатывая Items, мы "теряем" кнопки командной панели.
            child_items_elem = elem.find(f'{{{default_ns}}}ChildItems')
            if child_items_elem is not None:
                items.extend(self._parse_child_items(child_items_elem, item_data['id']))
            items_elem = elem.find(f'{{{default_ns}}}Items')
            if items_elem is not None:
                items.extend(self._parse_child_items(items_elem, item_data['id']))
        return items
    
    def _parse_form_conditional_appearance(self, root, ns):
        """Извлекает условное оформление"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        cond_app_elem = root.find(f'.//{{{default_ns}}}ConditionalAppearance')
        
        if cond_app_elem is None:
            return None
        
        # Сохраняем как XML строку
        return ET.tostring(cond_app_elem, encoding='unicode')
    
    def _parse_form_module(self, form_dir):
        """Извлекает модуль формы"""
        module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
        
        if not module_path.exists():
            return None
        
        try:
            with open(module_path, 'r', encoding='utf-8-sig') as f:
                code = f.read()
            return code
        except:
            return None
    
    # Вспомогательные методы
    
    def _find_logform_type_container(self, elem, logform_ns):
        """Контейнер Type в logform (прямой потомок или вложенный)."""
        t = elem.find(f'{{{logform_ns}}}Type')
        if t is not None:
            return t
        return elem.find(f'.//{{{logform_ns}}}Type')

    def _extract_slots_from_v8_type_container(self, type_elem, v8_ns):
        """Слоты из контейнера с v8:Type / v8:TypeSet (logform или Settings)."""
        direct = []
        for child in list(type_elem):
            local_tag = child.tag.split('}')[-1] if child.tag else ''
            if local_tag == 'Type' and child.text and child.text.strip():
                direct.append(child.text.strip())
        if direct:
            qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
            slots = []
            for type_str in self._dedupe_type_strings_preserve_order(direct):
                slot = self._slot_from_type_string(
                    type_str,
                    qualifiers if len(direct) == 1 else None,
                )
                slots.append(slot)
            return slots

        from_set = []
        for ts in type_elem.findall(f'.//{{{v8_ns}}}TypeSet'):
            if ts.text and ts.text.strip():
                from_set.append(ts.text.strip())
            for t in ts.findall(f'.//{{{v8_ns}}}Type'):
                if t.text and t.text.strip():
                    from_set.append(t.text.strip())
        if from_set:
            qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
            slots = []
            for type_str in self._dedupe_type_strings_preserve_order(from_set):
                slot = parse_cfg_type_string(type_str)
                if qualifiers and slot.get('kind') == 'primitive':
                    slot = dict(slot)
                    slot['qualifiers'] = qualifiers
                slots.append(slot)
            return slots
        return []

    def _extract_logform_type_slots(self, elem):
        """Структурированные слоты типа реквизита/колонки формы (logform NS)."""
        logform_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        v8_ns = 'http://v8.1c.ru/8.1/data/core'

        slots = []
        type_elem = self._find_logform_type_container(elem, logform_ns)
        if type_elem is not None:
            slots.extend(self._extract_slots_from_v8_type_container(type_elem, v8_ns))

        settings_elem = elem.find(f'{{{logform_ns}}}Settings')
        if settings_elem is not None:
            slots.extend(self._extract_slots_from_v8_type_container(settings_elem, v8_ns))

        return slots

    def _extract_localized_string(self, elem, tag_name):
        """Извлекает локализованную строку"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        tag_elem = elem.find(f'{{{default_ns}}}{tag_name}')
        if tag_elem is None:
            return ''
        
        # Ищем v8:content
        content = tag_elem.find('.//{http://v8.1c.ru/8.1/data/core}content')
        if content is not None and content.text:
            return content.text
        
        return ''
    
    def _get_element_text(self, elem, tag_name):
        """Получает текст элемента"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        child = elem.find(f'{{{default_ns}}}{tag_name}')
        return child.text if child is not None and child.text else ''

    def _extract_form_functional_options(self, elem, default_ns='http://v8.1c.ru/8.3/xcf/logform'):
        """Извлекает список FunctionalOptions/Item из элемента формы (Attribute, Command или UI element).
        Item может быть UUID или строка вида FunctionalOption.Имя."""
        fo_elem = elem.find(f'{{{default_ns}}}FunctionalOptions')
        if fo_elem is None:
            return []
        result = []
        for item in fo_elem.findall(f'{{{default_ns}}}Item'):
            if item.text and item.text.strip():
                result.append(item.text.strip())
        return result
    
    def _extract_columns(self, attr_elem):
        """Извлекает колонки ValueTable (Column) и AdditionalColumns (DocumentObject)."""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        columns_elem = attr_elem.find(f'{{{default_ns}}}Columns')
        if columns_elem is None:
            return None

        columns = []
        for col in columns_elem.findall(f'{{{default_ns}}}Column'):
            columns.append({
                'table': None,
                'name': col.get('name', ''),
                'title': self._extract_localized_string(col, 'Title'),
                'type_slots': self._extract_logform_type_slots(col),
            })
        for add_col in columns_elem.findall(f'{{{default_ns}}}AdditionalColumns'):
            table_name = add_col.get('table', '') or None
            for col in add_col.findall(f'{{{default_ns}}}Column'):
                columns.append({
                    'table': table_name,
                    'name': col.get('name', ''),
                    'title': self._extract_localized_string(col, 'Title'),
                    'type_slots': self._extract_logform_type_slots(col),
                })

        return columns if columns else None
    
    def _extract_query_text(self, attr_elem):
        """Извлекает QueryText для ДинамическогоСписка"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        query_elem = attr_elem.find(f'.//{{{default_ns}}}QueryText')
        if query_elem is not None and query_elem.text:
            return query_elem.text
        return None
    
    def _extract_item_properties(self, elem):
        """Извлекает свойства элемента UI"""
        properties = {}
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        
        # Список часто используемых свойств
        prop_names = [
            'Visible', 'Enabled', 'Width', 'Height', 
            'HorizontalStretch', 'VerticalStretch', 
            'ReadOnly', 'TitleLocation', 'Group',
            'Representation', 'CommandSource', 'Type'
        ]
        
        for prop_name in prop_names:
            prop_elem = elem.find(f'{{{default_ns}}}{prop_name}')
            if prop_elem is not None and prop_elem.text:
                properties[prop_name] = prop_elem.text
        
        return properties
    
    def _extract_item_events(self, elem):
        """Извлекает события элемента"""
        events = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        events_elem = elem.find(f'{{{default_ns}}}Events')
        
        if events_elem is None:
            return events
        
        for event in events_elem.findall(f'{{{default_ns}}}Event'):
            events.append({
                'name': event.get('name', ''),
                'handler': event.text or ''
            })
        
        return events


def _local_tag(tag):
    """Локальное имя тега без namespace (для сравнения)."""
    if not tag:
        return ''
    return tag.split('}')[-1] if '}' in tag else tag


def get_configuration_name(config_path):
    """
    Возвращает имя конфигурации из Configuration.xml (без полного парсинга).
    Используется для подстановки имени базы в GUI при выборе выгрузки.
    """
    path = Path(config_path)
    if not path.exists() or path.suffix.lower() != '.xml':
        return ''
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        config = root.find(f'{{{md_ns}}}Configuration')
        if config is None:
            config = root.find('.//{http://v8.1c.ru/8.3/MDClasses}Configuration')
        if config is None:
            return ''
        properties = config.find(f'{{{md_ns}}}Properties')
        if properties is None:
            properties = config.find(f'.//{{{md_ns}}}Properties')
        if properties is None:
            return ''
        for child in properties:
            if _local_tag(child.tag) in ('Name', 'n') and child.text:
                return child.text.strip()
    except (ET.ParseError, OSError):
        pass
    return ''


def get_configuration_type(config_path):
    """
    Возвращает тип конфигурации: 'extension' или 'base'.
    Расширение определяется по наличию ConfigurationExtensionPurpose в Configuration.xml.
    """
    path = Path(config_path)
    if not path.exists() or path.suffix.lower() != '.xml':
        return 'base'
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)
        if config is None:
            return 'base'
        properties = config.find('md:Properties', ns)
        if properties is None:
            return 'base'
        purpose_elem = properties.find('md:ConfigurationExtensionPurpose', ns)
        if purpose_elem is not None and purpose_elem.text and purpose_elem.text.strip():
            return 'extension'
    except (ET.ParseError, OSError):
        pass
    return 'base'


def test_parser(config_path):
    """Тестовая функция"""
    parser = ConfigurationParser(config_path)
    data = parser.parse()
    
    print(f"\nКонфигурация: {data['name']}")
    print(f"Объектов найдено: {len(data['objects'])}")
    
    for obj in data['objects'][:5]:
        print(f"  {obj['type']}: {obj['name']}")
        if obj['modules']:
            print(f"    Модулей: {len(obj['modules'])}")