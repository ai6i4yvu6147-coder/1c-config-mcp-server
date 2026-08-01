import os
import xml.etree.ElementTree as ET

from shared.form_property_flattener import (
    flatten_attribute,
    flatten_attribute_column,
    flatten_item,
)

from .xml_helpers import _winlong

# --- Standalone (no `self`) helpers -----------------------------------------------------
#
# P-8 (audit-2026-08): forms are 58% of parse time and fully independent of each other, so
# they're the one stage worth a ProcessPoolExecutor. A pool worker cannot touch `self` (own
# process, own memory), so the actual read_form()/flatten work below takes no parser state
# and returns errors instead of appending them to self.skipped_forms/self.skipped_form_modules
# — the caller (in-process or the pool-submitting side, after future.result()) does that
# merge. The FormsMixin methods further down are thin self-bearing wrappers over these same
# functions, used directly for the sequential path (no pool) and by tests.


def _read_form_uuid_standalone(form_dir, form_name):
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


def _parse_form_module_standalone(form_dir):
    """Читает модуль формы. Returns (code_or_None, error_message_or_None)."""
    module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
    if not os.path.exists(_winlong(module_path)):
        return None, None
    try:
        with open(_winlong(module_path), 'r', encoding='utf-8-sig') as f:
            return f.read(), None
    except Exception as e:
        return None, f"Ошибка чтения модуля формы {module_path}: {e}"


def _parse_one_form(form_dir, uuid=None, form_name=None):
    """Парсит одну форму единым движком (``onec_metadata_schema.read_form``), без обращения
    к состоянию parser-инстанса.

    Returns dict {'form_data': dict|None, 'form_error': str|None, 'module_error': str|None}.
    Отсутствие Form.xml — обычный no-op (всё None), не ошибка.
    """
    outcome = {'form_data': None, 'form_error': None, 'module_error': None}
    try:
        form_xml = form_dir / 'Ext' / 'Form.xml'
        if not os.path.exists(_winlong(form_xml)):
            return outcome
        form_name = form_name or form_dir.name
        if uuid is None:
            uuid = _read_form_uuid_standalone(form_dir, form_name)

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

        module_code, module_error = _parse_form_module_standalone(form_dir)
        outcome['module_error'] = module_error
        outcome['form_data'] = {
            'name': form_name,
            'uuid': uuid,
            'properties': model['properties'],
            'events': model['events'],
            'attributes': attributes,
            'commands': model['commands'],
            'items': items,
            'conditional_appearance': model['conditional_appearance'],
            'module': module_code,
        }
    except Exception as e:
        outcome['form_error'] = f"Ошибка парсинга формы {form_dir.name}: {e}"
    return outcome


def _assign_form_kind(form_data, default_forms):
    form_name = form_data['name']
    form_kind = None
    if default_forms.get('List') == form_name:
        form_kind = 'List'
    elif default_forms.get('Choice') == form_name:
        form_kind = 'Choice'
    elif default_forms.get('Element') == form_name:
        form_kind = 'Element'
    form_data['form_kind'] = form_kind


def _parse_forms_worker(root_dir, folder_name, obj_name, default_forms):
    """Module-level, picklable ProcessPoolExecutor worker: parses every form under
    <root_dir>/<folder_name>/<obj_name>/Forms/. No shared state — errors are collected and
    returned (not appended to a parser instance) for the caller to merge after
    ``future.result()``.

    Returns (forms, skipped_forms, skipped_form_modules) — same shapes
    ``self.skipped_forms``/``self.skipped_form_modules`` normally accumulate.
    """
    forms = []
    skipped_forms = []
    skipped_form_modules = []
    forms_dir = root_dir / folder_name / obj_name / 'Forms'
    if not os.path.exists(_winlong(forms_dir)):
        return forms, skipped_forms, skipped_form_modules

    default_forms = default_forms or {}
    for form_dir in forms_dir.iterdir():
        if not form_dir.is_dir():
            continue
        outcome = _parse_one_form(form_dir)
        if outcome['form_error']:
            print(outcome['form_error'])
            skipped_forms.append({'path': str(form_dir), 'error': outcome['form_error']})
        if outcome['module_error']:
            print(outcome['module_error'])
            module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
            skipped_form_modules.append({'path': str(module_path), 'error': outcome['module_error']})
        form_data = outcome['form_data']
        if form_data:
            _assign_form_kind(form_data, default_forms)
            forms.append(form_data)

    return forms, skipped_forms, skipped_form_modules


def _parse_common_form_worker(root_dir, folder_name, name, uuid):
    """Same contract as ``_parse_forms_worker``, for one CommonForm (single form, no
    form_kind — common forms aren't List/Element/Choice defaults of anything)."""
    forms = []
    skipped_forms = []
    skipped_form_modules = []
    form_dir = root_dir / folder_name / name
    outcome = _parse_one_form(form_dir, uuid=uuid, form_name=name)
    if outcome['form_error']:
        print(outcome['form_error'])
        skipped_forms.append({'path': str(form_dir), 'error': outcome['form_error']})
    if outcome['module_error']:
        print(outcome['module_error'])
        module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
        skipped_form_modules.append({'path': str(module_path), 'error': outcome['module_error']})
    if outcome['form_data']:
        forms.append(outcome['form_data'])
    return forms, skipped_forms, skipped_form_modules


class FormsMixin:
    """Logform (Form.xml) parsing: form properties, events, attributes, commands, UI item tree.

    P-8 (audit-2026-08): ``_submit_forms``/``_submit_common_form`` hand work to
    ``self._form_pool`` (a ``ProcessPoolExecutor`` set up by ``ConfigurationParserCore.parse``)
    when one is running, falling back to the sequential ``_parse_forms``/``_parse_common_form``
    below otherwise — same code either way (``_parse_forms_worker``/``_parse_one_form``), just
    called in-process vs. in a worker.
    """

    def _submit_forms(self, obj_name, folder_name, default_forms):
        """Как ``_parse_forms``, но возвращает ``Future`` вместо списка, если сейчас работает
        пул (``self._form_pool``) — резолвится позже, одним проходом, в ``_resolve_pending_forms``.
        Без Forms/ или без пула — работает как обычно, синхронно."""
        forms_dir = self.root_dir / folder_name / obj_name / 'Forms'
        if not os.path.exists(_winlong(forms_dir)):
            return []
        if self._form_pool is not None:
            return self._form_pool.submit(
                _parse_forms_worker, self.root_dir, folder_name, obj_name, default_forms
            )
        with self._accumulate('forms'):
            return self._parse_forms(obj_name, folder_name, default_forms)

    def _submit_common_form(self, name, folder_name, uuid):
        """Как ``_parse_common_form``, но через пул (см. ``_submit_forms``)."""
        form_dir = self.root_dir / folder_name / name
        if not os.path.exists(_winlong(form_dir / 'Ext' / 'Form.xml')):
            return []
        if self._form_pool is not None:
            return self._form_pool.submit(_parse_common_form_worker, self.root_dir, folder_name, name, uuid)
        with self._accumulate('forms'):
            return self._parse_common_form(name, folder_name, uuid)

    def _resolve_object_forms(self, obj):
        """Дожидается ``Future`` в ``obj['forms']`` (см. ``_submit_forms``/``_submit_common_form``)
        и сливает собранные по пути ошибки в ``self.skipped_forms``/``self.skipped_form_modules``.
        Возвращает тот же объект. Без пула ``obj['forms']`` уже обычный список — no-op.

        Резолв поштучный, а не батчем по всем объектам (`parser-streaming-pipeline`): объект
        отдаётся потребителю сразу, как только его формы готовы, и дальше не удерживается."""
        import concurrent.futures

        forms = obj.get('forms')
        if isinstance(forms, concurrent.futures.Future):
            with self._accumulate('forms'):
                forms_list, skipped_forms, skipped_form_modules = forms.result()
            obj['forms'] = forms_list
            self.skipped_forms.extend(skipped_forms)
            self.skipped_form_modules.extend(skipped_form_modules)
        return obj

    def _parse_forms(self, obj_name, folder_name, default_forms=None):
        """Парсит формы объекта синхронно (без пула). default_forms: {'Element': name|None,
        'List': name|None, 'Choice': name|None} для form_kind."""
        forms, skipped_forms, skipped_form_modules = _parse_forms_worker(
            self.root_dir, folder_name, obj_name, default_forms
        )
        self.skipped_forms.extend(skipped_forms)
        self.skipped_form_modules.extend(skipped_form_modules)
        return forms

    def _parse_common_form(self, name, folder_name, uuid):
        """Парсит общую форму синхронно: CommonForms/<Имя>/Ext/Form.xml, модуль — Ext/Form/Module.bsl."""
        forms, skipped_forms, skipped_form_modules = _parse_common_form_worker(
            self.root_dir, folder_name, name, uuid
        )
        self.skipped_forms.extend(skipped_forms)
        self.skipped_form_modules.extend(skipped_form_modules)
        return forms

    def _parse_form(self, form_dir, uuid=None, form_name=None):
        """Парсит одну форму единым движком (``onec_metadata_schema.read_form``).
        uuid/form_name — для CommonForm (метаданные в CommonForms/<Имя>.xml).

        skip-on-error (контракт P-2): битый Form.xml не валит всю сборку — ошибка пишется в
        ``self.skipped_forms`` и возвращается None. Отсутствие Form.xml — обычный no-op.
        """
        outcome = _parse_one_form(form_dir, uuid=uuid, form_name=form_name)
        if outcome['form_error']:
            print(outcome['form_error'])
            self.skipped_forms.append({'path': str(form_dir), 'error': outcome['form_error']})
        if outcome['module_error']:
            print(outcome['module_error'])
            module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
            self.skipped_form_modules.append({'path': str(module_path), 'error': outcome['module_error']})
        return outcome['form_data']

    def _read_form_uuid(self, form_dir, form_name):
        return _read_form_uuid_standalone(form_dir, form_name)

    def _parse_form_module(self, form_dir):
        """Извлекает модуль формы.

        skip-on-error (P-9, тот же контракт, что и у _parse_form): чтение не валит сборку,
        но потеря пишется в ``self.skipped_form_modules`` — раньше терялась молча."""
        code, error = _parse_form_module_standalone(form_dir)
        if error:
            print(error)
            module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
            self.skipped_form_modules.append({'path': str(module_path), 'error': error})
        return code
