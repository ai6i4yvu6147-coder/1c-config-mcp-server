"""Тесты type slots реквизитов и колонок форм (logform NS)."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser

LF = 'http://v8.1c.ru/8.3/xcf/logform'
V8 = 'http://v8.1c.ru/8.1/data/core'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'


def _parser():
    return ConfigurationParser(str(ROOT / 'nonexistent' / 'Configuration.xml'))


class TestExtractLogformTypeSlots(unittest.TestCase):
    def test_value_list_type_with_settings_inner_catalog(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="СписокТС">
  <Type><v8:Type>v8:ValueListType</v8:Type></Type>
  <Settings xsi:type="v8:TypeDescription" xmlns:xsi="{XSI}">
    <v8:Type>cfg:CatalogRef.ТранспортныеСредства</v8:Type>
  </Settings>
</Attribute>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0]['kind'], 'primitive')
        self.assertEqual(slots[0]['base_type'], 'ValueListType')
        self.assertEqual(slots[1]['kind'], 'object_ref')
        self.assertEqual(slots[1]['ref_name'], 'ТранспортныеСредства')

    def test_composite_document_ref(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Column xmlns="{LF}" xmlns:v8="{V8}" name="ДокументОтгрузки">
  <Type>
    <v8:Type>cfg:DocumentRef.ТД_ЗаявкаНаПродажу</v8:Type>
    <v8:Type>cfg:DocumentRef.ТД_Реализация</v8:Type>
  </Type>
</Column>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0]['ref_name'], 'ТД_ЗаявкаНаПродажу')
        self.assertEqual(slots[1]['ref_name'], 'ТД_Реализация')

    def test_value_table_wrapper(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="График">
  <Type><v8:Type>v8:ValueTable</v8:Type></Type>
</Attribute>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['base_type'], 'ValueTable')

    def test_dynamic_list_wrapper(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="Список">
  <Type><v8:Type>cfg:DynamicList</v8:Type></Type>
</Attribute>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['base_type'], 'DynamicList')

    def test_typeset_characteristic(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="Субконто">
  <Type>
    <v8:TypeSet>cfg:Characteristic.ДополнительныеРеквизитыИСведения</v8:TypeSet>
  </Type>
</Attribute>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['kind'], 'unknown')

    def test_number_with_qualifiers(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Column xmlns="{LF}" xmlns:v8="{V8}" name="Количество">
  <Type>
    <v8:Type>xs:decimal</v8:Type>
    <v8:NumberQualifiers>
      <v8:Digits>10</v8:Digits>
      <v8:FractionDigits>2</v8:FractionDigits>
    </v8:NumberQualifiers>
  </Type>
</Column>"""
        root = ET.fromstring(xml)
        slots = _parser()._extract_logform_type_slots(root)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['base_type'], 'Number')
        self.assertEqual(slots[0]['qualifiers']['digits'], 10)


class TestExtractFormColumns(unittest.TestCase):
    def test_direct_columns_and_additional_columns(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="График">
  <Type><v8:Type>v8:ValueTable</v8:Type></Type>
  <Columns>
    <Column name="Заявка">
      <Type><v8:Type>cfg:DocumentRef.ТД_Заявка</v8:Type></Type>
    </Column>
    <AdditionalColumns table="Объект.ТЧ">
      <Column name="ПолеОбъекта">
        <Type><v8:Type>xs:string</v8:Type></Type>
      </Column>
    </AdditionalColumns>
  </Columns>
</Attribute>"""
        root = ET.fromstring(xml)
        cols = _parser()._extract_columns(root)
        self.assertIsNotNone(cols)
        self.assertEqual(len(cols), 2)
        self.assertIsNone(cols[0]['table'])
        self.assertEqual(cols[0]['name'], 'Заявка')
        self.assertEqual(cols[0]['type_slots'][0]['ref_name'], 'ТД_Заявка')
        self.assertEqual(cols[1]['table'], 'Объект.ТЧ')
        self.assertEqual(cols[1]['name'], 'ПолеОбъекта')


class TestParseFormAttributes(unittest.TestCase):
    def test_attributes_use_type_slots(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="{LF}" xmlns:v8="{V8}">
  <Attributes>
    <Attribute name="СписокТС">
      <Type><v8:Type>v8:ValueListType</v8:Type></Type>
      <Settings xsi:type="v8:TypeDescription" xmlns:xsi="{XSI}">
        <v8:Type>cfg:CatalogRef.ТС</v8:Type>
      </Settings>
    </Attribute>
  </Attributes>
</Form>"""
        root = ET.fromstring(xml)
        attrs = _parser()._parse_form_attributes(root, {})
        self.assertEqual(len(attrs), 1)
        self.assertIn('type_slots', attrs[0])
        self.assertNotIn('type', attrs[0])
        self.assertEqual(len(attrs[0]['type_slots']), 2)


if __name__ == '__main__':
    unittest.main()
