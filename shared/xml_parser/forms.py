import os
import xml.etree.ElementTree as ET

from .xml_helpers import _winlong


class FormsMixin:
    """Logform (Form.xml) parsing: form properties, events, attributes, commands, UI item tree."""

    def _parse_forms(self, obj_name, folder_name, default_forms=None):
        """Парсит формы объекта. default_forms: {'Element': name|None, 'List': name|None, 'Choice': name|None} для form_kind."""
        forms = []
        forms_dir = self.root_dir / folder_name / obj_name / 'Forms'
        default_forms = default_forms or {}

        if not os.path.exists(_winlong(forms_dir)):
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

        if not os.path.exists(_winlong(form_xml)):
            return None

        try:
            form_name = form_name or form_dir.name
            if uuid is None:
                # UUID из файла метаданных формы (ИмяФормы.xml в каталоге формы объекта)
                form_meta_xml = form_dir / f'{form_name}.xml'
                uuid = ''
                if os.path.exists(_winlong(form_meta_xml)):
                    try:
                        meta_tree = ET.parse(_winlong(form_meta_xml))
                        meta_root = meta_tree.getroot()
                        form_elem = meta_root.find('.//{http://v8.1c.ru/8.3/MDClasses}Form')
                        if form_elem is not None:
                            uuid = form_elem.get('uuid', '')
                    except Exception:
                        pass

            # Парсим структуру формы из Form.xml
            tree = ET.parse(_winlong(form_xml))
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

        if not os.path.exists(_winlong(module_path)):
            return None

        try:
            with open(_winlong(module_path), 'r', encoding='utf-8-sig') as f:
                code = f.read()
            return code
        except:
            return None

    # Вспомогательные методы

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
