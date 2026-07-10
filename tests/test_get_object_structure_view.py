"""get_object_structure economy: max_attributes cap + sections filter (T-1)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import build_configuration_tools


_SCHEMA = '''
    CREATE TABLE metadata_objects (
        id INTEGER PRIMARY KEY, uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
        synonym TEXT, comment TEXT, object_belonging TEXT, extended_configuration_object TEXT,
        object_kind TEXT NOT NULL DEFAULT 'ConfigObject', is_primitive INTEGER NOT NULL DEFAULT 0,
        base_type TEXT, qualifier_1 TEXT, qualifier_2 TEXT, qualifier_3 TEXT
    );
    CREATE TABLE attributes (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, title TEXT, comment TEXT,
        is_standard INTEGER DEFAULT 0, standard_type TEXT, section TEXT NOT NULL DEFAULT 'Attribute'
    );
    CREATE TABLE metadata_type_slots (
        id INTEGER PRIMARY KEY, source_table TEXT, source_row_id INTEGER,
        src_object_id INTEGER, object_id INTEGER, ordinal INTEGER
    );
    CREATE TABLE tabular_sections (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, title TEXT, comment TEXT
    );
    CREATE TABLE tabular_section_columns (
        id INTEGER PRIMARY KEY, tabular_section_id INTEGER, column_name TEXT, title TEXT, comment TEXT
    );
    CREATE TABLE enum_values (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, enum_order INTEGER, title TEXT,
        comment TEXT, object_belonging TEXT, extended_configuration_object TEXT
    );
    CREATE TABLE modules (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_id INTEGER, command_id INTEGER,
        module_type TEXT, code TEXT
    );
    CREATE TABLE object_commands (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, synonym TEXT
    );
    CREATE TABLE forms (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT
    );
'''


def _setup(conn):
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO metadata_objects (id, object_type, name, object_kind) "
        "VALUES (1, 'Catalog', 'ТоварыБольшой', 'ConfigObject')"
    )
    for i in range(60):
        conn.execute(
            "INSERT INTO attributes (object_id, name, section, is_standard) VALUES (1, ?, 'Attribute', 0)",
            (f'Реквизит{i:02d}',),
        )
    conn.execute("INSERT INTO forms (object_id, form_name) VALUES (1, 'ФормаЭлемента')")


@pytest.fixture
def tools(tmp_path):
    import sqlite3
    from shared.indexer_version import INDEXER_VERSION
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


def _structure(result):
    return result['TestProject']['Main (base)']


def test_default_caps_attributes_at_50(tools):
    result = tools.get_object_structure('ТоварыБольшой', project_filter='TestProject')
    s = _structure(result)
    assert len(s['attributes']) == 50
    assert s['attributes_total_count'] == 60
    assert s['is_truncated'] is True


def test_max_attributes_zero_returns_all(tools):
    result = tools.get_object_structure('ТоварыБольшой', project_filter='TestProject', max_attributes=0)
    s = _structure(result)
    assert len(s['attributes']) == 60
    assert 'attributes_total_count' not in s
    assert 'is_truncated' not in s


def test_custom_cap(tools):
    result = tools.get_object_structure('ТоварыБольшой', project_filter='TestProject', max_attributes=10)
    s = _structure(result)
    assert len(s['attributes']) == 10
    assert s['attributes_total_count'] == 60


def test_sections_filter_keeps_only_requested(tools):
    result = tools.get_object_structure(
        'ТоварыБольшой', project_filter='TestProject', sections=['forms'],
    )
    s = _structure(result)
    assert s.get('forms') == ['ФормаЭлемента']
    assert 'attributes' not in s
    # identity kept
    assert s['name'] == 'ТоварыБольшой'
    assert s['type'] == 'Catalog'
