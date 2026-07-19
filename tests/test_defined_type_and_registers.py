"""DefinedType indexing and register attribute de-duplication."""

import sqlite3
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.metadata_type_resolver import MetadataTypeResolver, parse_cfg_type_string
from shared.xml_parser import ConfigurationParser

MD = 'http://v8.1c.ru/8.3/MDClasses'
V8 = 'http://v8.1c.ru/8.1/data/core'


def _parser():
    return ConfigurationParser(str(ROOT / 'nonexistent' / 'Configuration.xml'))


def _parse_register(tmp, xml):
    """Write a register descriptor to disk and parse it through the production single-engine
    path (`_parse_object` -> onec_metadata_schema), returning the object dict."""
    reg_dir = Path(tmp) / 'InformationRegisters'
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / 'РегТест.xml').write_text(xml, encoding='utf-8')
    parser = ConfigurationParser(str(Path(tmp) / 'Configuration.xml'))
    return parser._parse_object('РегТест', 'InformationRegister', 'InformationRegisters')


REGISTER_ATTR_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{MD}" xmlns:v8="{V8}">
  <InformationRegister uuid="00000000-0000-0000-0000-000000000001">
    <Properties>
      <Name>РегТест</Name>
    </Properties>
    <ChildObjects>
      <Attribute uuid="a1">
        <Properties>
          <Name>Рекв1</Name>
          <Type><v8:Type>xs:string</v8:Type></Type>
        </Properties>
      </Attribute>
      <Attribute uuid="a2">
        <Properties>
          <Name>Рекв2</Name>
          <Type><v8:Type>xs:boolean</v8:Type></Type>
        </Properties>
      </Attribute>
      <Dimension uuid="d1">
        <Properties>
          <Name>Изм1</Name>
          <Type><v8:TypeSet>cfg:DefinedType.МойТип</v8:TypeSet></Type>
        </Properties>
      </Dimension>
    </ChildObjects>
  </InformationRegister>
</MetaDataObject>"""

DEFINED_TYPE_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{MD}" xmlns:v8="{V8}">
  <DefinedType uuid="00000000-0000-0000-0000-000000000002">
    <Properties>
      <Name>МойТип</Name>
      <Synonym>
        <v8:item><v8:lang>ru</v8:lang><v8:content>Мой тип</v8:content></v8:item>
      </Synonym>
      <Type>
        <v8:Type>cfg:CatalogRef.Номенклатура</v8:Type>
        <v8:Type>cfg:CatalogRef.Контрагенты</v8:Type>
      </Type>
    </Properties>
  </DefinedType>
</MetaDataObject>"""


class TestRegisterAttributeDedup(unittest.TestCase):
    def test_register_custom_attributes_empty_attributes_once(self):
        """Register requisites land in obj['attributes'], not duplicated into
        properties['custom_attributes'] (single-engine `_adapt_register_section`)."""
        with tempfile.TemporaryDirectory() as tmp:
            obj = _parse_register(tmp, REGISTER_ATTR_XML)
        self.assertEqual(obj['properties']['custom_attributes'], [])
        self.assertEqual([a['name'] for a in obj['attributes']], ['Рекв1', 'Рекв2'])


class TestDefinedTypeParse(unittest.TestCase):
    def test_defined_type_type_slots(self):
        root = ET.fromstring(DEFINED_TYPE_XML)
        parser = _parser()
        obj_elem = parser._get_object_element(root, 'DefinedType', MD)
        slots = parser._extract_type_slots(obj_elem)
        raws = [s.get('raw') for s in slots]
        self.assertEqual(
            raws,
            ['cfg:CatalogRef.Номенклатура', 'cfg:CatalogRef.Контрагенты'],
        )

    def test_dimension_typeset_parses_defined_type_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj = _parse_register(tmp, REGISTER_ATTR_XML)
        dims = obj['dimensions']
        self.assertEqual(len(dims), 1)
        slot = dims[0]['type_slots'][0]
        self.assertEqual(slot['kind'], 'object_ref')
        self.assertEqual(slot['object_type_hint'], 'DefinedType')
        self.assertEqual(slot['ref_name'], 'МойТип')


class TestDefinedTypeIndexer(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.executescript('''
            CREATE TABLE metadata_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
                synonym TEXT, object_kind TEXT NOT NULL DEFAULT 'ConfigObject',
                is_primitive INTEGER NOT NULL DEFAULT 0,
                base_type TEXT, qualifier_1 TEXT, qualifier_2 TEXT, qualifier_3 TEXT
            );
            CREATE TABLE metadata_type_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL, source_row_id INTEGER NOT NULL,
                src_object_id INTEGER NOT NULL, object_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL, name TEXT NOT NULL
            );
        ''')
        cur.execute(
            "INSERT INTO metadata_objects (uuid, object_type, name, object_kind) "
            "VALUES ('u1', 'Catalog', 'Номенклатура', 'ConfigObject')"
        )
        cur.execute(
            "INSERT INTO metadata_objects (uuid, object_type, name, object_kind) "
            "VALUES ('u2', 'Catalog', 'Контрагенты', 'ConfigObject')"
        )
        cur.execute(
            "INSERT INTO metadata_objects (uuid, object_type, name, object_kind) "
            "VALUES ('u3', 'DefinedType', 'МойТип', 'ConfigObject')"
        )
        cur.execute(
            "INSERT INTO metadata_objects (uuid, object_type, name, object_kind) "
            "VALUES ('u4', 'InformationRegister', 'РегТест', 'ConfigObject')"
        )
        cur.execute("INSERT INTO attributes (object_id, name) VALUES (4, 'Изм1')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_defined_type_member_slots_and_dimension_ref(self):
        cur = self.conn.cursor()
        type_name_to_id = {}
        cur.execute("SELECT id, object_type, name FROM metadata_objects WHERE object_kind = 'ConfigObject'")
        for row in cur.fetchall():
            type_name_to_id[(row['object_type'], row['name'])] = row['id']

        resolver = MetadataTypeResolver()
        resolver.insert_slots(cur, [{
            'source_table': 'metadata_objects',
            'source_row_id': type_name_to_id[('DefinedType', 'МойТип')],
            'src_object_id': type_name_to_id[('DefinedType', 'МойТип')],
            'type_slots': [
                parse_cfg_type_string('cfg:CatalogRef.Номенклатура'),
                parse_cfg_type_string('cfg:CatalogRef.Контрагенты'),
            ],
        }], type_name_to_id)
        resolver.insert_slots(cur, [{
            'source_table': 'attributes',
            'source_row_id': 1,
            'src_object_id': type_name_to_id[('InformationRegister', 'РегТест')],
            'type_slots': [parse_cfg_type_string('cfg:DefinedType.МойТип')],
        }], type_name_to_id)
        self.conn.commit()

        cur.execute("SELECT COUNT(*) FROM metadata_type_slots WHERE source_table = 'metadata_objects'")
        self.assertEqual(cur.fetchone()[0], 2)
        cur.execute(
            "SELECT object_id FROM metadata_type_slots "
            "WHERE source_table = 'attributes' AND source_row_id = 1"
        )
        self.assertEqual(cur.fetchone()[0], type_name_to_id[('DefinedType', 'МойТип')])


if __name__ == '__main__':
    unittest.main()
