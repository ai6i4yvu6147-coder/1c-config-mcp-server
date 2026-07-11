"""get_object_structure for DefinedType and register dedup in tools layer."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.metadata_type_resolver import format_types_for_text
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
    CREATE TABLE modules (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_id INTEGER, command_id INTEGER,
        module_type TEXT, code TEXT
    );
    CREATE TABLE object_commands (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, synonym TEXT
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
    CREATE TABLE forms (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT
    );
'''


def _setup_register_and_defined_type(conn):
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO metadata_objects (id, uuid, object_type, name, synonym, object_kind) "
        "VALUES (1, 'u-dt', 'DefinedType', 'Пользователь', 'Пользователь', 'ConfigObject')"
    )
    conn.execute(
        "INSERT INTO metadata_objects (id, uuid, object_type, name, object_kind) "
        "VALUES (2, 'u-reg', 'InformationRegister', 'Трудозатраты', 'ConfigObject')"
    )
    conn.execute(
        "INSERT INTO metadata_objects (id, uuid, object_type, name, object_kind) "
        "VALUES (3, '', 'Catalog', 'Пользователи', 'ConfigObject')"
    )
    conn.execute(
        "INSERT INTO metadata_objects (id, uuid, object_type, name, object_kind) "
        "VALUES (10, '', 'Catalog', 'ВидыРабот', 'ConfigObject')"
    )
    conn.executemany(
        "INSERT INTO metadata_type_slots "
        "(source_table, source_row_id, src_object_id, object_id, ordinal) VALUES (?, ?, ?, ?, ?)",
        [
            ('metadata_objects', 1, 1, 3, 0),
            ('attributes', 1, 2, 1, 0),
            ('attributes', 2, 2, 10, 0),
        ],
    )
    conn.execute(
        "INSERT INTO attributes (id, object_id, name, section) VALUES (1, 2, 'Исполнитель', 'Dimension')"
    )
    conn.execute(
        "INSERT INTO attributes (id, object_id, name, section) VALUES (2, 2, 'Описание', 'Attribute')"
    )


@pytest.fixture
def tools(tmp_path):
    import sqlite3
    from shared.indexer_version import INDEXER_VERSION
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(db_path)
    conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
    _setup_register_and_defined_type(conn)
    conn.commit()
    conn.close()
    t = build_configuration_tools(tmp_path, db_path)
    t._require_project_exists = lambda pf, dbs: None
    yield t
    t.close_all()


def test_get_object_structure_defined_type_members(tools):
    result = tools.get_object_structure('Пользователь', project_filter='TestProject')
    structure = result['TestProject']['Main (base)']
    assert structure['type'] == 'DefinedType'
    assert len(structure['types']) == 1
    assert structure['types'][0]['object_type'] == 'Catalog'
    assert structure['types'][0]['name'] == 'Пользователи'


def test_get_object_structure_register_dimension_resolves_defined_type(tools):
    result = tools.get_object_structure('Трудозатраты', project_filter='TestProject')
    structure = result['TestProject']['Main (base)']
    dims = {d['name']: d for d in structure['dimensions']}
    assert format_types_for_text(dims['Исполнитель']['types']) == 'DefinedType.Пользователь'
    assert len(structure['attributes']) == 1
    assert structure['attributes'][0]['name'] == 'Описание'
    assert structure['attributes'][0]['types'][0]['name'] == 'ВидыРабот'
