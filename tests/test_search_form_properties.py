"""search_form_properties generalized to any property_path (T-4)."""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.indexer_version import INDEXER_VERSION
from tests.conftest import build_configuration_tools


_SCHEMA = '''
    CREATE TABLE metadata_objects (
        id INTEGER PRIMARY KEY, uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
        synonym TEXT, comment TEXT, object_belonging TEXT, extended_configuration_object TEXT,
        object_kind TEXT NOT NULL DEFAULT 'ConfigObject', is_primitive INTEGER NOT NULL DEFAULT 0,
        base_type TEXT, qualifier_1 TEXT, qualifier_2 TEXT, qualifier_3 TEXT
    );
    CREATE TABLE forms (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT, form_kind TEXT, uuid TEXT, properties_json TEXT
    );
    CREATE TABLE form_items (
        id INTEGER PRIMARY KEY, form_id INTEGER, parent_id INTEGER, name TEXT, item_type TEXT
    );
    CREATE TABLE form_entity_properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_kind TEXT NOT NULL, entity_id INTEGER NOT NULL,
        property_path TEXT NOT NULL, property_name TEXT NOT NULL,
        ordinal INTEGER NOT NULL DEFAULT 0, value_text TEXT, value_type TEXT,
        UNIQUE(entity_kind, entity_id, property_path, ordinal)
    );
'''

# (item_id, name, type, [(path, value)])
_ITEMS = [
    (1, 'ПолеА', 'InputField', [('Visible', 'false'), ('DataPath', 'Организация'), ('ReadOnly', 'true')]),
    (2, 'ПолеБ', 'InputField', [('Visible', 'true'), ('DataPath', 'Контрагент')]),
    (3, 'ПолеВ', 'CheckBoxField', [('Visible', 'false'), ('DataPath', 'ПризнакОрганизация')]),
    (4, 'Кнопка', 'Button', [('CommandName', 'Form.Command.Записать')]),
    (5, 'ПолеГ', 'InputField', [('ReadOnly', 'true')]),
]


def _setup(conn):
    conn.executescript(_SCHEMA)
    conn.execute("INSERT INTO metadata_objects (id, object_type, name) VALUES (1, 'Document', 'ТестДок')")
    conn.execute("INSERT INTO forms (id, object_id, form_name) VALUES (1, 1, 'Форма')")
    for item_id, name, itype, props in _ITEMS:
        conn.execute(
            "INSERT INTO form_items (id, form_id, parent_id, name, item_type) VALUES (?, 1, NULL, ?, ?)",
            (item_id, name, itype),
        )
        for path, value in props:
            conn.execute(
                "INSERT INTO form_entity_properties (entity_kind, entity_id, property_path, property_name, ordinal, value_text, value_type) "
                "VALUES ('item', ?, ?, ?, 0, ?, 'string')",
                (item_id, path, path.rsplit('.', 1)[-1], value),
            )


@pytest.fixture
def tools(tmp_path):
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(db_path)
    conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
    _setup(conn)
    conn.commit()
    conn.close()
    t = build_configuration_tools(tmp_path, db_path)
    t._require_project_exists = lambda pf, dbs: None
    yield t
    t.close_all()


def _payload(result):
    return result['TestProject']['Main (base)']


def test_search_arbitrary_property_readonly(tools):
    result = tools.search_form_properties('ReadOnly', 'true', project_filter='TestProject')
    payload = _payload(result)
    names = {e['element_name'] for e in payload['elements']}
    assert names == {'ПолеА', 'ПолеГ'}
    assert payload['total_count'] == 2
    assert payload['is_truncated'] is False


def test_boolean_synonym_normalized(tools):
    result = tools.search_form_properties('Visible', 'нет', project_filter='TestProject')
    names = {e['element_name'] for e in _payload(result)['elements']}
    assert names == {'ПолеА', 'ПолеВ'}


def test_contains_match(tools):
    result = tools.search_form_properties(
        'DataPath', 'Организация', project_filter='TestProject', value_match='contains',
    )
    names = {e['element_name'] for e in _payload(result)['elements']}
    assert names == {'ПолеА', 'ПолеВ'}  # Организация + ПризнакОрганизация


def test_command_name_search(tools):
    result = tools.search_form_properties(
        'CommandName', 'Записать', project_filter='TestProject', value_match='contains',
    )
    assert {e['element_name'] for e in _payload(result)['elements']} == {'Кнопка'}


def test_truncation(tools):
    result = tools.search_form_properties('ReadOnly', 'true', project_filter='TestProject', max_results=1)
    payload = _payload(result)
    assert payload['returned_count'] == 1
    assert payload['total_count'] == 2
    assert payload['is_truncated'] is True


def test_no_value_returns_all_with_property(tools):
    result = tools.search_form_properties('DataPath', project_filter='TestProject')
    assert _payload(result)['total_count'] == 3  # ПолеА, ПолеБ, ПолеВ


def test_empty_property_path_raises(tools):
    with pytest.raises(ValueError):
        tools.search_form_properties('', project_filter='TestProject')
