"""Тесты resolver типов метаданных."""
import sqlite3
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.metadata_type_resolver import (
    MetadataTypeResolver,
    format_type_descriptor_name,
    format_types_for_text,
    normalize_descriptor_storage,
    parse_cfg_type_string,
    slot_to_mcp_type,
)


class TestParseCfgTypeString(unittest.TestCase):
    def test_catalog_ref(self):
        slot = parse_cfg_type_string('cfg:CatalogRef.Номенклатура')
        self.assertEqual(slot['kind'], 'object_ref')
        self.assertEqual(slot['ref_suffix'], 'CatalogRef')
        self.assertEqual(slot['ref_name'], 'Номенклатура')

    def test_primitive_boolean(self):
        slot = parse_cfg_type_string('xs:boolean')
        self.assertEqual(slot['kind'], 'primitive')
        self.assertEqual(slot['base_type'], 'Boolean')

    def test_defined_type_unknown(self):
        slot = parse_cfg_type_string('cfg:DefinedType.МойТип')
        self.assertEqual(slot['kind'], 'unknown')

    def test_document_ref_without_name_unknown(self):
        slot = parse_cfg_type_string('cfg:DocumentRef')
        self.assertEqual(slot['kind'], 'unknown')

    def test_value_list_type_wrapper(self):
        slot = parse_cfg_type_string('v8:ValueListType')
        self.assertEqual(slot['kind'], 'primitive')
        self.assertEqual(slot['base_type'], 'ValueListType')

    def test_dynamic_list_wrapper(self):
        slot = parse_cfg_type_string('cfg:DynamicList')
        self.assertEqual(slot['kind'], 'primitive')
        self.assertEqual(slot['base_type'], 'DynamicList')

    def test_document_object_hint(self):
        slot = parse_cfg_type_string('cfg:DocumentObject.Реализация')
        self.assertEqual(slot['kind'], 'object_ref')
        self.assertEqual(slot['object_type_hint'], 'Document')
        self.assertEqual(slot['ref_name'], 'Реализация')


class TestTypeDescriptor(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE metadata_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
                synonym TEXT, comment TEXT, object_belonging TEXT,
                extended_configuration_object TEXT,
                object_kind TEXT NOT NULL DEFAULT 'ConfigObject',
                is_primitive INTEGER NOT NULL DEFAULT 0,
                base_type TEXT, qualifier_1 TEXT, qualifier_2 TEXT, qualifier_3 TEXT
            )
        ''')
        cur.execute('''
            CREATE UNIQUE INDEX uq_metadata_objects_type_descriptor
            ON metadata_objects(object_kind, base_type, qualifier_1, qualifier_2, qualifier_3)
            WHERE object_kind = 'TypeDescriptor'
        ''')
        cur.execute('''
            CREATE TABLE metadata_type_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL, source_row_id INTEGER NOT NULL,
                src_object_id INTEGER NOT NULL, object_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL
            )
        ''')
        cur.execute('''
            INSERT INTO metadata_objects (uuid, object_type, name, object_kind)
            VALUES ('u1', 'Catalog', 'Контрагенты', 'ConfigObject')
        ''')
        cur.execute('''
            INSERT INTO metadata_objects (uuid, object_type, name, object_kind)
            VALUES ('u2', 'Document', 'Реализация', 'ConfigObject')
        ''')
        cur.execute("INSERT INTO attributes (object_id, name) VALUES (1, 'Owner')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_dedup_type_descriptor(self):
        resolver = MetadataTypeResolver()
        cur = self.conn.cursor()
        id1 = resolver.get_or_create_type_descriptor(cur, 'Number', '10', '2', 'Any')
        id2 = resolver.get_or_create_type_descriptor(cur, 'Number', '10', '2', 'Any')
        self.assertEqual(id1, id2)
        cur.execute("SELECT COUNT(*) FROM metadata_objects WHERE object_kind = 'TypeDescriptor'")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_dedup_equivalent_qualifier_variants(self):
        """None/0/int/str и второй resolver не должны плодить дубликаты TypeDescriptor."""
        cur = self.conn.cursor()
        variants = [
            ('Number', 10, None, None),
            ('Number', '10', None, None),
            ('Number', 10, 0, None),
            ('Number', '10', '0', None),
            ('String', None, None, None),
            ('String', '', '', ''),
        ]
        ids = []
        for args in variants:
            resolver = MetadataTypeResolver()
            ids.append(resolver.get_or_create_type_descriptor(cur, *args))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[2], ids[3])
        self.assertEqual(ids[0], ids[2])  # Number без fraction и с 0 — один дескриптор
        self.assertEqual(ids[4], ids[5])
        cur.execute("SELECT COUNT(*) FROM metadata_objects WHERE object_kind = 'TypeDescriptor'")
        self.assertEqual(cur.fetchone()[0], 2)

    def test_normalize_descriptor_storage(self):
        self.assertEqual(
            normalize_descriptor_storage('Number', 10, None, None),
            ('Number', '10', '0', ''),
        )
        self.assertEqual(
            normalize_descriptor_storage('String', None, None, None),
            ('String', '', '', ''),
        )

    def test_insert_slots_composite(self):
        resolver = MetadataTypeResolver()
        cur = self.conn.cursor()
        type_name_to_id = {('Catalog', 'Контрагенты'): 1, ('Document', 'Реализация'): 2}
        pending = [{
            'source_table': 'attributes',
            'source_row_id': 1,
            'src_object_id': 1,
            'type_slots': [
                parse_cfg_type_string('cfg:CatalogRef.Контрагенты'),
                parse_cfg_type_string('cfg:DocumentRef.Реализация'),
            ],
        }]
        resolver.insert_slots(cur, pending, type_name_to_id)
        cur.execute('SELECT COUNT(*) FROM metadata_type_slots')
        self.assertEqual(cur.fetchone()[0], 2)


class TestFormatHelpers(unittest.TestCase):
    def test_format_type_descriptor_name(self):
        self.assertEqual(format_type_descriptor_name('Number', '10', '2', 'Any'), 'Number(10,2)')

    def test_format_types_for_text(self):
        text = format_types_for_text([
            {'kind': 'object', 'object_type': 'Catalog', 'name': 'X'},
            {'kind': 'primitive', 'base_type': 'Number', 'qualifiers': {'digits': 10, 'fraction': 0}},
        ])
        self.assertEqual(text, 'Catalog.X | Number(10,0)')

    def test_slot_to_mcp_type_primitive(self):
        row = {
            'object_kind': 'TypeDescriptor',
            'base_type': 'Number',
            'qualifier_1': '10',
            'qualifier_2': '0',
            'qualifier_3': 'Any',
        }
        item = slot_to_mcp_type(row)
        self.assertEqual(item['kind'], 'primitive')
        self.assertEqual(item['base_type'], 'Number')
        self.assertEqual(item['qualifiers']['digits'], '10')


if __name__ == '__main__':
    unittest.main()
