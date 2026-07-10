"""get_form_item drill-down curation vs verbose (T-2)."""

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
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT, form_kind TEXT,
        uuid TEXT, properties_json TEXT
    );
    CREATE TABLE form_items (
        id INTEGER PRIMARY KEY, form_id INTEGER, parent_id INTEGER, name TEXT, item_type TEXT
    );
    CREATE TABLE form_item_events (
        id INTEGER PRIMARY KEY, item_id INTEGER, event_name TEXT, handler TEXT
    );
    CREATE TABLE form_entity_properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_kind TEXT NOT NULL, entity_id INTEGER NOT NULL,
        property_path TEXT NOT NULL, property_name TEXT NOT NULL,
        ordinal INTEGER NOT NULL DEFAULT 0, value_text TEXT, value_type TEXT,
        UNIQUE(entity_kind, entity_id, property_path, ordinal)
    );
'''

_EAV = [
    ('DataPath', 'DataPath', 'Список', 'string'),
    ('Behavior', 'Behavior', 'Usual', 'string'),
    ('ToolTip.item.content', 'content', 'Всплывающая подсказка', 'string'),
    ('ToolTip.item.lang', 'lang', 'ru', 'string'),
    ('Period.startDate', 'startDate', '0001-01-01T00:00:00', 'string'),
]


def _setup(conn):
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO metadata_objects (id, object_type, name) VALUES (1, 'Document', 'ТестДок')"
    )
    conn.execute("INSERT INTO forms (id, object_id, form_name) VALUES (1, 1, 'Форма')")
    conn.execute("INSERT INTO form_items (id, form_id, parent_id, name, item_type) VALUES (1, 1, NULL, 'Список', 'Table')")
    for path, name, value, vt in _EAV:
        conn.execute(
            "INSERT INTO form_entity_properties (entity_kind, entity_id, property_path, property_name, ordinal, value_text, value_type) "
            "VALUES ('item', 1, ?, ?, 0, ?, ?)",
            (path, name, value, vt),
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


def _item(result):
    return result['TestProject']['Main (base)']


def test_curated_drops_noise_and_collapses_localized(tools):
    result = tools.get_form_item('ТестДок', 'Форма', 'Список', project_filter='TestProject')
    data = _item(result)
    paths = {p['path']: p['value'] for p in data['properties']}
    assert 'ToolTip.item.lang' not in paths
    assert 'Period.startDate' not in paths
    assert paths.get('ToolTip') == 'Всплывающая подсказка'  # collapsed
    # DataPath is a Table profile path -> ordered first
    assert data['properties'][0]['path'] == 'DataPath'
    assert data['properties_hidden'] == 2  # lang + unset date


def test_verbose_returns_all_rows(tools):
    result = tools.get_form_item(
        'ТестДок', 'Форма', 'Список', project_filter='TestProject', verbose=True,
    )
    data = _item(result)
    paths = {p['path'] for p in data['properties']}
    assert 'ToolTip.item.lang' in paths
    assert 'Period.startDate' in paths
    assert data['properties_hidden'] == 0
