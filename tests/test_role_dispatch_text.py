"""Role MCP tools render human-readable text, not JSON (T-3)."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.dispatch.roles import (
    handle_find_role,
    handle_find_roles_for_object,
    handle_get_role_rights,
    handle_list_roles,
)


class _StubTools:
    def __init__(self, **payloads):
        self._payloads = payloads

    def find_role(self, *a, **k):
        return self._payloads['find_role']

    def list_roles(self, *a, **k):
        return self._payloads['list_roles']

    def get_role_rights(self, *a, **k):
        return self._payloads['get_role_rights']

    def find_roles_for_object(self, *a, **k):
        return self._payloads['find_roles_for_object']


def _text(handler, tools, arguments):
    result = asyncio.run(handler(tools, arguments))
    return result[0].text


def test_find_role_text():
    tools = _StubTools(find_role={
        'Альфа': {'Основная конфигурация (base)': [
            {'role_name': 'ПолныеПрава', 'role_qualified_name': 'Role.ПолныеПрава',
             'uuid': 'u', 'synonym': 'Полные права', 'source_layer': 'main', 'extension_name': None},
        ]},
    })
    text = _text(handle_find_role, tools, {'name': 'ПолныеПрава', 'project_filter': 'Альфа'})
    assert not text.lstrip().startswith('{')
    assert 'Role.ПолныеПрава (Полные права)' in text
    assert 'слой: основная' in text


def test_get_role_rights_summary_text():
    tools = _StubTools(get_role_rights={
        'role': {'name': 'ПолныеПрава', 'qualified_name': 'Role.ПолныеПрава', 'uuid': 'u', 'synonym': 'Полные права'},
        'settings': {'set_for_new_objects': True, 'set_for_attributes_by_default': True,
                     'independent_rights_of_child_objects': False},
        'merge': True, 'layers': ['Основная конфигурация'],
        'restriction_templates': [], 'access_restrictions': [],
        'access_restrictions_total_count': 0, 'access_restrictions_is_truncated': False,
        'response_mode': 'summary', 'role_profile': 'admin_full',
        'grant_stats': {'object_level': 10048, 'field_level': 0, 'total_rights': 10048},
        'grants': [], 'extension_delta_grants': [], 'is_truncated': True, 'total_count': 10048,
        'hint': 'Admin role; use object_name filter or response_mode=full for enumeration.',
    })
    text = _text(handle_get_role_rights, tools, {'role_name': 'ПолныеПрава', 'project_filter': 'Альфа'})
    assert '{' not in text
    assert 'сводка (admin_full)' in text
    assert 'всего 10048' in text
    assert 'Admin role' in text


def test_get_role_rights_full_grants_and_denied():
    tools = _StubTools(get_role_rights={
        'role': {'name': 'R', 'qualified_name': 'Role.R', 'uuid': 'u', 'synonym': ''},
        'settings': None, 'merge': False, 'layers': ['Основная конфигурация'],
        'restriction_templates': [], 'access_restrictions': [],
        'access_restrictions_total_count': 0, 'access_restrictions_is_truncated': False,
        'response_mode': 'full',
        'grants': [
            {'target_qname': 'Catalog.Номенклатура', 'right_name': 'Read', 'granted': True,
             'target_kind': 'object', 'db_name': 'Основная конфигурация'},
            {'target_qname': 'Catalog.Номенклатура', 'right_name': 'Delete', 'granted': False,
             'target_kind': 'object', 'db_name': 'Основная конфигурация'},
        ],
        'is_truncated': False, 'total_count': 2,
    })
    text = _text(handle_get_role_rights, tools, {'role_name': 'R', 'project_filter': 'Альфа'})
    assert 'Catalog.Номенклатура: Read' in text
    assert 'Catalog.Номенклатура: Delete (запрещено)' in text


def test_get_role_rights_not_found():
    tools = _StubTools(get_role_rights={'error': 'not_found', 'role_name': 'НетТакой'})
    text = _text(handle_get_role_rights, tools, {'role_name': 'НетТакой', 'project_filter': 'Альфа'})
    assert "Роль 'НетТакой' не найдена" in text


def test_find_roles_for_object_merge_text():
    tools = _StubTools(find_roles_for_object={
        'Альфа': {
            'merge': True, 'target': {'type': 'Catalog', 'name': 'Номенклатура'},
            'roles': [{'role_qualified_name': 'Role.A', 'role_name': 'A', 'uuid': 'u',
                       'right_name': 'Read', 'db_name': 'Основная конфигурация', 'extension_purpose': None}],
            'total_count': 1, 'is_truncated': False,
            'admin_roles_note': 'Role.ПолныеПрава grants broad access by policy; not enumerated per object.',
        },
    })
    text = _text(handle_find_roles_for_object, tools,
                 {'object_name': 'Номенклатура', 'project_filter': 'Альфа', 'merge': True})
    assert not text.lstrip().startswith('{')
    assert 'Catalog.Номенклатура' in text
    assert 'Role.A — Read' in text
    assert '⚠' in text
