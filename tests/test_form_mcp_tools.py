"""MCP form tools against minimal v12 schema."""
import sqlite3
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import build_configuration_tools


def _setup_v12_form_db(conn: sqlite3.Connection) -> None:
    conn.executescript('''
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
        CREATE TABLE form_attributes (
            id INTEGER PRIMARY KEY, form_id INTEGER, name TEXT, title TEXT, is_main INTEGER
        );
        CREATE TABLE form_attribute_columns (
            id INTEGER PRIMARY KEY, form_attribute_id INTEGER, name TEXT, title TEXT, table_context TEXT
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
        CREATE TABLE form_commands (
            id INTEGER PRIMARY KEY, form_id INTEGER, name TEXT, title TEXT,
            action TEXT, shortcut TEXT, representation TEXT
        );
        CREATE TABLE form_events (
            id INTEGER PRIMARY KEY, form_id INTEGER, event_name TEXT, handler TEXT, call_type TEXT
        );
        CREATE TABLE form_item_events (
            id INTEGER PRIMARY KEY, item_id INTEGER, event_name TEXT, handler TEXT
        );
        CREATE TABLE metadata_type_slots (
            id INTEGER PRIMARY KEY, source_table TEXT, source_row_id INTEGER,
            src_object_id INTEGER, object_id INTEGER, ordinal INTEGER
        );
    ''')
    conn.execute("INSERT INTO metadata_objects VALUES (1,NULL,'Document','ТестДок',NULL,NULL,NULL,NULL,'ConfigObject',0,NULL,NULL,NULL,NULL)")
    conn.execute("INSERT INTO metadata_objects VALUES (2,NULL,'TypeDescriptor','DynamicList',NULL,NULL,NULL,NULL,'TypeDescriptor',1,'DynamicList',NULL,NULL,NULL)")
    conn.execute('INSERT INTO forms VALUES (1, 1, "ФормаСписка", "List", "", NULL)')
    conn.execute('INSERT INTO form_attributes VALUES (1, 1, "Список", "", 1)')
    query = 'ВЫБРАТЬ Ссылка ИЗ Документ.ТестДок ГДЕ Истина'
    conn.execute(
        "INSERT INTO form_entity_properties (entity_kind, entity_id, property_path, property_name, ordinal, value_text, value_type) "
        "VALUES ('attribute', 1, 'Settings.QueryText', 'QueryText', 0, ?, 'longtext')",
        (query,),
    )
    conn.execute(
        "INSERT INTO metadata_type_slots (source_table, source_row_id, src_object_id, object_id, ordinal) "
        "VALUES ('form_attributes', 1, 1, 2, 0)"
    )


class TestFormMcpTools(unittest.TestCase):
    def test_get_form_attribute_and_structure(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        try:
            db_path = Path(tmp.name) / 'test.db'
            conn = sqlite3.connect(db_path)
            _setup_v12_form_db(conn)
            conn.commit()
            conn.close()
            tools = build_configuration_tools(Path(tmp.name), db_path)
            tools._require_project_exists = lambda pf, dbs: None
            try:
                attr_result = tools.get_form_attribute(
                    'ТестДок', 'ФормаСписка', 'Список', project_filter='TestProject',
                )
                data = attr_result['TestProject']['Main (base)']
                paths = {p['path']: p['value'] for p in data['properties']}
                self.assertIn('Settings.QueryText', paths)
                self.assertIn('Документ.ТестДок', paths['Settings.QueryText'])

                structure = tools.get_form_structure(
                    'ТестДок', 'ФормаСписка', project_filter='TestProject',
                )
                attr = structure['TestProject']['Main (base)']['attributes'][0]
                self.assertTrue(any('QueryText: present' in h for h in attr['hints']))
                self.assertNotIn('query_text', attr)
            finally:
                for conn in tools.connections.values():
                    conn.close()
                tools.connections.clear()
        finally:
            tmp.cleanup()


if __name__ == '__main__':
    unittest.main()
