"""Tests for form XML property flattener."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.form_property_flattener import flatten_attribute, flatten_item

LF = 'http://v8.1c.ru/8.3/xcf/logform'
V8 = 'http://v8.1c.ru/8.1/data/core'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'


class TestFlattenAttribute(unittest.TestCase):
    def test_dynamic_list_query_text_and_fields(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="Список">
  <Type><v8:Type>cfg:DynamicList</v8:Type></Type>
  <Settings>
    <QueryText>ВЫБРАТЬ Ссылка ИЗ Документ.Тест</QueryText>
    <Field>
      <dataPath>Ссылка</dataPath>
      <field>Ссылка</field>
    </Field>
    <Field>
      <dataPath>Код</dataPath>
      <field>Код</field>
    </Field>
  </Settings>
</Attribute>"""
        root = ET.fromstring(xml)
        rows = flatten_attribute(root)
        paths = {(r['property_path'], r.get('ordinal', 0)): r['value_text'] for r in rows}
        self.assertEqual(paths[('Settings.QueryText', 0)], 'ВЫБРАТЬ Ссылка ИЗ Документ.Тест')
        self.assertEqual(paths[('Settings.Field.dataPath', 0)], 'Ссылка')
        self.assertEqual(paths[('Settings.Field.dataPath', 1)], 'Код')
        self.assertEqual(rows[0]['value_type'], 'longtext')

    def test_nested_conditional_appearance_items_get_unique_ordinals(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" name="Список">
  <Settings>
    <ListSettings>
      <conditionalAppearance>
        <item>
          <appearance>
            <item><parameter>Цвет</parameter><value>Красный</value></item>
            <item><parameter>Шрифт</parameter><value>Жирный</value></item>
          </appearance>
        </item>
        <item>
          <appearance>
            <item><parameter>Цвет</parameter><value>Синий</value></item>
          </appearance>
        </item>
      </conditionalAppearance>
    </ListSettings>
  </Settings>
</Attribute>"""
        root = ET.fromstring(xml)
        rows = flatten_attribute(root)
        param_rows = [
            r for r in rows
            if r['property_path'] == 'Settings.ListSettings.conditionalAppearance.item.appearance.item.parameter'
        ]
        value_rows = [
            r for r in rows
            if r['property_path'] == 'Settings.ListSettings.conditionalAppearance.item.appearance.item.value'
        ]
        self.assertEqual(len(param_rows), 3)
        self.assertEqual(len(value_rows), 3)
        self.assertEqual(len({r['ordinal'] for r in param_rows}), 3)
        self.assertEqual(len({r['ordinal'] for r in value_rows}), 3)

    def test_skips_type_and_columns(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Attribute xmlns="{LF}" xmlns:v8="{V8}" name="График">
  <Type><v8:Type>v8:ValueTable</v8:Type></Type>
  <Columns>
    <Column name="A"><Type><v8:Type>xs:string</v8:Type></Type></Column>
  </Columns>
  <Title><v8:item><v8:lang>ru</v8:lang><v8:content>Заголовок</v8:content></v8:item></Title>
</Attribute>"""
        root = ET.fromstring(xml)
        rows = flatten_attribute(root)
        names = [r['property_path'] for r in rows]
        self.assertNotIn('Type', names)
        self.assertFalse(any('Column' in p for p in names))
        self.assertIn('Title', names)


class TestFlattenItem(unittest.TestCase):
    def test_item_properties(self):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<InputField xmlns="{LF}" name="Поле1">
  <DataPath>Список.Поле</DataPath>
  <Visible>false</Visible>
  <Enabled>true</Enabled>
</InputField>"""
        root = ET.fromstring(xml)
        rows = flatten_item(root)
        by_path = {r['property_path']: r['value_text'] for r in rows}
        self.assertEqual(by_path['DataPath'], 'Список.Поле')
        self.assertEqual(by_path['Visible'], 'false')
        self.assertEqual(by_path['Enabled'], 'true')

    def test_localized_string_collapses_to_single_value(self):
        """Any `<Tag><item><lang/><content/></item>…</Tag>`, not just Title, collapses
        to one row; language-code and per-language duplicate rows are never emitted."""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<InputField xmlns="{LF}" xmlns:v8="{V8}" name="Поле1">
  <ToolTip>
    <v8:item><v8:lang>ru</v8:lang><v8:content>Быстрые отборы</v8:content></v8:item>
    <v8:item><v8:lang>en</v8:lang><v8:content>Quick filters</v8:content></v8:item>
  </ToolTip>
</InputField>"""
        root = ET.fromstring(xml)
        rows = flatten_item(root)
        by_path = {r['property_path']: r['value_text'] for r in rows}
        self.assertEqual(by_path['ToolTip'], 'Быстрые отборы')
        self.assertNotIn('ToolTip.item.lang', by_path)
        self.assertNotIn('ToolTip.item.content', by_path)
        self.assertEqual(len(rows), 1)

    def test_addition_source_is_skipped(self):
        """AdditionSource is pure structural wiring (echoes the owning item's own name
        + a fixed enum) and must never reach the EAV table."""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<SearchStringAddition xmlns="{LF}" name="СписокСтрокаПоиска">
  <AdditionSource>
    <Item>Список</Item>
    <Type>SearchStringRepresentation</Type>
  </AdditionSource>
  <HorizontalLocation>Left</HorizontalLocation>
</SearchStringAddition>"""
        root = ET.fromstring(xml)
        rows = flatten_item(root)
        paths = [r['property_path'] for r in rows]
        self.assertFalse(any(p.startswith('AdditionSource') for p in paths))
        self.assertIn('HorizontalLocation', paths)

    def test_unset_date_sentinel_is_dropped(self):
        """Period.startDate/endDate default to the platform's unset-date sentinel when no
        period filter is configured — never real data, must not reach the EAV table."""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Table xmlns="{LF}" xmlns:v8="{V8}" name="Список">
  <Period>
    <v8:variant xsi:type="v8:StandardPeriodVariant" xmlns:xsi="{XSI}">Custom</v8:variant>
    <v8:startDate>0001-01-01T00:00:00</v8:startDate>
    <v8:endDate>0001-01-01T00:00:00</v8:endDate>
  </Period>
</Table>"""
        root = ET.fromstring(xml)
        rows = flatten_item(root)
        by_path = {r['property_path']: r['value_text'] for r in rows}
        self.assertNotIn('Period.startDate', by_path)
        self.assertNotIn('Period.endDate', by_path)
        self.assertEqual(by_path['Period.variant'], 'Custom')


if __name__ == '__main__':
    unittest.main()
