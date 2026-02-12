import xml.etree.ElementTree as ET
import os
import json
from pathlib import Path

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
            name_elem = properties.find('md:n', ns)
            if name_elem is not None:
                config_name = name_elem.text
        
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
            'Report': 'Reports',
            'DataProcessor': 'DataProcessors',
            'Enum': 'Enums',
            'BusinessProcess': 'BusinessProcesses',
            'Task': 'Tasks',
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
        obj_elem = root.find(f'.//{obj_type}')
        uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''
        
        # Получаем свойства
        properties = self._parse_properties(root)
        
        # Получаем модули
        modules = self._parse_modules(name, folder_name)
        
        # Получаем формы
        forms = self._parse_forms(name, folder_name)
        
        return {
            'name': name,
            'type': obj_type,
            'uuid': uuid,
            'properties': properties,
            'modules': modules,
            'forms': forms
        }
    
    def _parse_properties(self, root):
        """Извлекает свойства объекта"""
        props = {}
        properties = root.find('.//Properties')
        
        if properties is not None:
            # Синоним
            ns = {'v8': 'http://v8.1c.ru/8.1/data/core'}
            synonym_elem = properties.find('.//v8:content', ns)
            if synonym_elem is not None and synonym_elem.text:
                props['synonym'] = synonym_elem.text
                
            # Комментарий
            comment_elem = properties.find('.//Comment')
            if comment_elem is not None and comment_elem.text:
                props['comment'] = comment_elem.text
        
        return props
    
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
    
    def _parse_forms(self, obj_name, folder_name):
        """Парсит формы объекта"""
        forms = []
        forms_dir = self.root_dir / folder_name / obj_name / 'Forms'
        
        if not forms_dir.exists():
            return forms
        
        # Перебираем папки форм
        for form_dir in forms_dir.iterdir():
            if form_dir.is_dir():
                form_data = self._parse_form(form_dir)
                if form_data:
                    forms.append(form_data)
        
        return forms
    
    def _parse_form(self, form_dir):
        """Парсит одну форму"""
        form_xml = form_dir / 'Ext' / 'Form.xml'
        
        if not form_xml.exists():
            return None
        
        try:
            # Получаем UUID из файла метаданных формы (ИмяФормы.xml)
            form_name = form_dir.name
            form_meta_xml = form_dir / f'{form_name}.xml'
            uuid = ''
            
            if form_meta_xml.exists():
                try:
                    meta_tree = ET.parse(form_meta_xml)
                    meta_root = meta_tree.getroot()
                    # UUID в атрибуте элемента Form
                    form_elem = meta_root.find('.//{http://v8.1c.ru/8.3/MDClasses}Form')
                    if form_elem is not None:
                        uuid = form_elem.get('uuid', '')
                except:
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
                'type': self._extract_type_from_element(attr),
                'title': self._extract_localized_string(attr, 'Title'),
                'is_main': attr.find(f'{{{default_ns}}}MainAttribute') is not None,
                'columns': self._extract_columns(attr),
                'query_text': self._extract_query_text(attr)
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
                'picture': self._extract_picture(cmd),
                'representation': self._get_element_text(cmd, 'Representation')
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
            items.extend(self._parse_child_items(auto_cmd_bar, None))
        
        # Обрабатываем ChildItems
        child_items = root.find(f'{{{default_ns}}}ChildItems')
        if child_items is not None:
            items.extend(self._parse_child_items(child_items, None))
        
        return items
    
    def _parse_child_items(self, parent_elem, parent_id):
        """Рекурсивно парсит дочерние элементы"""
        items = []
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        
        # Типы элементов UI
        item_types = [
            'Button', 'InputField', 'Table', 'UsualGroup', 
            'ButtonGroup', 'Popup', 'LabelField', 'CheckBoxField',
            'RadioButtonField', 'Pages', 'Page', 'CommandBar',
            'LabelDecoration', 'PictureDecoration', 'SpreadSheetDocumentField'
        ]
        
        for item_type in item_types:
            for elem in parent_elem.findall(f'{{{default_ns}}}{item_type}'):
                item_data = {
                    'name': elem.get('name', ''),
                    'id': elem.get('id', ''),
                    'type': item_type,
                    'parent_id': parent_id,
                    'data_path': self._get_element_text(elem, 'DataPath'),
                    'title': self._extract_localized_string(elem, 'Title'),
                    'properties': self._extract_item_properties(elem),
                    'events': self._extract_item_events(elem)
                }
                
                items.append(item_data)
                
                # Рекурсивно обрабатываем вложенные элементы
                child_items_elem = elem.find(f'{{{default_ns}}}ChildItems')
                if child_items_elem is not None:
                    nested_items = self._parse_child_items(child_items_elem, item_data['id'])
                    items.extend(nested_items)
        
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
    
    def _extract_type_from_element(self, elem):
        """Извлекает тип из элемента Type"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        type_elem = elem.find(f'.//{{{default_ns}}}Type')
        if type_elem is None:
            return ''
        
        # Ищем v8:Type
        v8_type = type_elem.find('.//{http://v8.1c.ru/8.1/data/core}Type')
        if v8_type is not None and v8_type.text:
            return v8_type.text
        
        return ''
    
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
    
    def _extract_columns(self, attr_elem):
        """Извлекает колонки табличной части"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        columns_elem = attr_elem.find(f'{{{default_ns}}}Columns')
        if columns_elem is None:
            return None
        
        columns = []
        for add_col in columns_elem.findall(f'.//{{{default_ns}}}AdditionalColumns'):
            table_name = add_col.get('table', '')
            for col in add_col.findall(f'{{{default_ns}}}Column'):
                col_data = {
                    'table': table_name,
                    'name': col.get('name', ''),
                    'title': self._extract_localized_string(col, 'Title'),
                    'type': self._extract_type_from_element(col)
                }
                columns.append(col_data)
        
        return columns if columns else None
    
    def _extract_query_text(self, attr_elem):
        """Извлекает QueryText для ДинамическогоСписка"""
        default_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        query_elem = attr_elem.find(f'.//{{{default_ns}}}QueryText')
        if query_elem is not None and query_elem.text:
            return query_elem.text
        return None
    
    def _extract_picture(self, elem):
        """Извлекает ссылку на картинку"""
        pic_elem = elem.find('.//Picture')
        if pic_elem is None:
            return ''
        
        ref = pic_elem.find('.//{http://v8.1c.ru/8.3/xcf/readable}Ref')
        if ref is not None and ref.text:
            return ref.text
        
        return ''
    
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