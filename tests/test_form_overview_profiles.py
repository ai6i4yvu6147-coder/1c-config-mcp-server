"""Tests for form overview profiles."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.form_overview_profiles import (
    attribute_overview_hints,
    is_column_container,
    overview_paths_for_item,
)


class TestOverviewProfiles(unittest.TestCase):
    def test_table_is_column_container(self):
        self.assertTrue(is_column_container('Table'))
        self.assertFalse(is_column_container('InputField'))

    def test_field_like_paths(self):
        paths = overview_paths_for_item('InputField')
        self.assertIn('DataPath', paths)
        self.assertIn('ReadOnly', paths)

    def test_dynamic_list_hints(self):
        types = [{'kind': 'primitive', 'base_type': 'DynamicList'}]
        eav = [
            {'property_path': 'Settings.QueryText', 'property_name': 'QueryText',
             'ordinal': 0, 'value_text': 'ВЫБРАТЬ ' + 'X' * 100},
            {'property_path': 'Settings.Field.dataPath', 'property_name': 'dataPath',
             'ordinal': 0, 'value_text': 'A'},
            {'property_path': 'Settings.Field.dataPath', 'property_name': 'dataPath',
             'ordinal': 1, 'value_text': 'B'},
        ]
        hints = attribute_overview_hints(types, eav, 0)
        self.assertTrue(any('QueryText: present' in h for h in hints))
        self.assertTrue(any('columns: 2' in h for h in hints))


if __name__ == '__main__':
    unittest.main()
