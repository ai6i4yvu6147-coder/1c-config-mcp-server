"""Тесты извлечения типа реквизита (в т.ч. составной: несколько v8:Type)."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser

MD = 'http://v8.1c.ru/8.3/MDClasses'
V8 = 'http://v8.1c.ru/8.1/data/core'


def _parser():
    return ConfigurationParser(str(ROOT / 'nonexistent' / 'Configuration.xml'))


class TestExtractAttributeType(unittest.TestCase):
    def test_composite_multiple_v8_type_direct_children(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{MD}" xmlns:v8="{V8}">
  <Properties>
    <Name>ДокументОснование</Name>
    <Type>
      <v8:Type>cfg:DocumentRef.A</v8:Type>
      <v8:Type>cfg:DocumentRef.B</v8:Type>
    </Type>
  </Properties>
</Attribute>"""
        root = ET.fromstring(xml)
        self.assertEqual(
            _parser()._extract_attribute_type(root),
            'cfg:DocumentRef.A, cfg:DocumentRef.B',
        )

    def test_single_simple_type(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{MD}" xmlns:v8="{V8}">
  <Properties>
    <Name>Флаг</Name>
    <Type>
      <v8:Type>xs:boolean</v8:Type>
    </Type>
  </Properties>
</Attribute>"""
        root = ET.fromstring(xml)
        self.assertEqual(_parser()._extract_attribute_type(root), 'xs:boolean')

    def test_dedupe_preserves_order(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{MD}" xmlns:v8="{V8}">
  <Properties>
    <Name>X</Name>
    <Type>
      <v8:Type>cfg:DocumentRef.A</v8:Type>
      <v8:Type>cfg:DocumentRef.A</v8:Type>
      <v8:Type>cfg:DocumentRef.B</v8:Type>
    </Type>
  </Properties>
</Attribute>"""
        root = ET.fromstring(xml)
        self.assertEqual(
            _parser()._extract_attribute_type(root),
            'cfg:DocumentRef.A, cfg:DocumentRef.B',
        )

    def test_typeset_text_inside_type(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{MD}" xmlns:v8="{V8}">
  <Properties>
    <Name>Y</Name>
    <Type>
      <v8:TypeSet>cfg:DefinedType.МойТип</v8:TypeSet>
    </Type>
  </Properties>
</Attribute>"""
        root = ET.fromstring(xml)
        self.assertEqual(
            _parser()._extract_attribute_type(root),
            'cfg:DefinedType.МойТип',
        )

    def test_value_type_refs(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Dimension xmlns="{MD}" xmlns:v8="{V8}">
  <Properties>
    <Name>D1</Name>
    <ValueType>
      <v8:Ref>cfg:CatalogRef.Номенклатура</v8:Ref>
      <v8:Ref>cfg:CatalogRef.ХарактеристикиНоменклатуры</v8:Ref>
    </ValueType>
  </Properties>
</Dimension>"""
        root = ET.fromstring(xml)
        self.assertEqual(
            _parser()._extract_attribute_type(root),
            'cfg:CatalogRef.Номенклатура, cfg:CatalogRef.ХарактеристикиНоменклатуры',
        )


if __name__ == '__main__':
    unittest.main()
