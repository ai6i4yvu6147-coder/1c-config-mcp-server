"""T-5: search_code's DynamicList QueryText EAV probe must respect module_type and be bounded."""

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
    CREATE TABLE modules (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_id INTEGER, command_id INTEGER,
        module_type TEXT, code TEXT
    );
    CREATE TABLE module_procedures (
        id INTEGER PRIMARY KEY, module_id INTEGER, name TEXT, proc_type TEXT,
        start_line INTEGER, end_line INTEGER
    );
    CREATE TABLE object_commands (
        id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, synonym TEXT
    );
    CREATE TABLE forms (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT
    );
    CREATE TABLE form_attributes (
        id INTEGER PRIMARY KEY, form_id INTEGER, name TEXT, title TEXT, is_main INTEGER DEFAULT 0
    );
    CREATE TABLE form_entity_properties (
        id INTEGER PRIMARY KEY, entity_kind TEXT NOT NULL, entity_id INTEGER NOT NULL,
        property_path TEXT NOT NULL, property_name TEXT NOT NULL, ordinal INTEGER NOT NULL DEFAULT 0,
        value_text TEXT, value_type TEXT
    );
    CREATE VIRTUAL TABLE code_search USING fts5(code, content='modules', content_rowid='id');
'''


def _setup(conn):
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO metadata_objects (id, object_type, name, object_kind) "
        "VALUES (1, 'Catalog', 'Товары', 'ConfigObject')"
    )
    conn.execute(
        "INSERT INTO modules (id, object_id, module_type, code) "
        "VALUES (1, 1, 'ObjectModule', 'Процедура Тест() КонецПроцедуры')"
    )
    conn.execute("INSERT INTO forms (id, object_id, form_name) VALUES (1, 1, 'ФормаСписка')")
    conn.execute("INSERT INTO form_attributes (id, form_id, name) VALUES (1, 1, 'Список')")
    conn.execute(
        "INSERT INTO form_entity_properties (entity_kind, entity_id, property_path, property_name, value_text) "
        "VALUES ('attribute', 1, 'Settings.QueryText', 'QueryText', 'ВЫБРАТЬ Тест ИЗ Справочник.Товары')"
    )
    conn.execute("INSERT INTO code_search(code_search) VALUES ('rebuild')")


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


def _entries(result):
    return result['TestProject']['Main (base)']


def test_query_text_probe_runs_without_module_type(tools):
    result = tools.search_code('Тест', project_filter='TestProject')
    kinds = {e.get('match_kind') for e in _entries(result)}
    assert 'form_query' in kinds


def test_query_text_probe_runs_for_form_module(tools):
    result = tools.search_code('Тест', project_filter='TestProject', module_type='FormModule')
    kinds = {e.get('match_kind') for e in _entries(result)}
    assert 'form_query' in kinds


def test_query_text_probe_skipped_for_other_module_type(tools):
    result = tools.search_code('Тест', project_filter='TestProject', module_type='ObjectModule')
    kinds = {e.get('match_kind') for e in _entries(result)}
    assert 'form_query' not in kinds
    # the ObjectModule code match itself must still be present
    assert any(e.get('object_name') == 'Товары' for e in _entries(result))
