import os
import xml.etree.ElementTree as ET

from shared.form_property_flattener import (
    flatten_attribute,
    flatten_attribute_column,
    flatten_item,
)

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
        """Парсит одну форму единым движком (``onec_metadata_schema.read_form``).
        uuid/form_name — для CommonForm (метаданные в CommonForms/<Имя>.xml).

        skip-on-error (контракт P-2): битый Form.xml не валит всю сборку — ошибка пишется в
        ``self.skipped_forms`` и возвращается None. Отсутствие Form.xml — обычный no-op
        (``_read_form_record`` возвращает None до чтения, без записи в skipped_forms).
        """
        try:
            return self._read_form_record(form_dir, uuid=uuid, form_name=form_name)
        except Exception as e:
            print(f"Ошибка парсинга формы {form_dir.name}: {e}")
            self.skipped_forms.append({'path': str(form_dir), 'error': str(e)})
            return None

    def _read_form_uuid(self, form_dir, form_name):
        """UUID формы из соседнего файла метаданных ИмяФормы.xml (в самом Form.xml его нет)."""
        form_meta_xml = form_dir / f'{form_name}.xml'
        if not os.path.exists(_winlong(form_meta_xml)):
            return ''
        try:
            meta_root = ET.parse(_winlong(form_meta_xml)).getroot()
            form_elem = meta_root.find('.//{http://v8.1c.ru/8.3/MDClasses}Form')
            if form_elem is not None:
                return form_elem.get('uuid', '')
        except Exception:
            pass
        return ''

    def _read_form_record(self, form_dir, uuid=None, form_name=None):
        """Читает Form.xml единым движком (``read_form``) → запись формы для индексации.

        Движок владеет форматом (контейнеры, дерево items, слоты типов, титулы, ФО,
        conditional appearance) и отдаёт по каждой сущности нейтральное ``RawElement``-зеркало
        subtree — storage-политику не несёт. EAV (`entity_properties`) считает существующий
        C-MCP-флэттенер (skip/value_type/UNSET_DATE/ordinals) по этому зеркалу (байт-паритет
        со снятым legacy-путём подтверждён A/B — см. docs/forms-engine-migration.md).
        uuid/модуль — из соседних файлов."""
        form_xml = form_dir / 'Ext' / 'Form.xml'
        if not os.path.exists(_winlong(form_xml)):
            return None
        form_name = form_name or form_dir.name
        if uuid is None:
            uuid = self._read_form_uuid(form_dir, form_name)

        from onec_metadata_schema import read_form
        with open(_winlong(form_xml), 'rb') as f:
            model = read_form(f.read())

        attributes = []
        for a in model['attributes']:
            columns = None
            if a['columns'] is not None:
                columns = [{
                    'table': c['table'],
                    'name': c['name'],
                    'title': c['title'],
                    'type_slots': c['type_slots'],
                    'entity_properties': flatten_attribute_column(c['property_tree']),
                    'functional_options': c['functional_options'],
                } for c in a['columns']]
            attributes.append({
                'name': a['name'],
                'type_slots': a['type_slots'],
                'title': a['title'],
                'is_main': a['is_main'],
                'columns': columns,
                'entity_properties': flatten_attribute(a['property_tree']),
                'functional_options': a['functional_options'],
            })

        items = [{
            'name': i['name'],
            'id': i['id'],
            'type': i['type'],
            'parent_id': i['parent_id'],
            'entity_properties': flatten_item(i['property_tree']),
            'events': i['events'],
            'functional_options': i['functional_options'],
        } for i in model['items']]

        return {
            'name': form_name,
            'uuid': uuid,
            'properties': model['properties'],
            'events': model['events'],
            'attributes': attributes,
            'commands': model['commands'],
            'items': items,
            'conditional_appearance': model['conditional_appearance'],
            'module': self._parse_form_module(form_dir),
        }

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
