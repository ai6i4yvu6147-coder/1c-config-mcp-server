import unittest

from server.role_merge import (
    merge_grants,
    merge_restrictions,
    merge_role_settings,
    sort_layers_for_merge,
)


class TestRoleMerge(unittest.TestCase):
    def test_sort_layers(self):
        layers = [
            {'db_type': 'extension', 'extension_purpose': 'Patch', 'source_db_name': 'Z'},
            {'db_type': 'base', 'source_db_name': 'Main'},
            {'db_type': 'extension', 'extension_purpose': 'AddOn', 'source_db_name': 'A'},
        ]
        ordered = sort_layers_for_merge(layers)
        self.assertEqual(ordered[0]['db_type'], 'base')
        self.assertEqual(ordered[1]['extension_purpose'], 'AddOn')
        self.assertEqual(ordered[2]['extension_purpose'], 'Patch')

    def test_grant_overlay(self):
        layers = [
            {
                'source_db_name': 'Main',
                'grants': [
                    {'target_qname': 'Catalog.X', 'right_name': 'Read', 'granted': True},
                ],
            },
            {
                'source_db_name': 'Ext',
                'grants': [
                    {'target_qname': 'Catalog.X', 'right_name': 'Read', 'granted': False},
                ],
            },
        ]
        merged = merge_grants(layers)
        self.assertEqual(len(merged), 1)
        self.assertFalse(merged[0]['granted'])
        self.assertEqual(merged[0]['source_db_name'], 'Ext')

    def test_settings_replace(self):
        layers = [
            {'source_db_name': 'Main', 'role_settings': {'set_for_new_objects': True}},
            {'source_db_name': 'Ext', 'role_settings': {'set_for_new_objects': False}},
        ]
        settings = merge_role_settings(layers)
        self.assertFalse(settings['set_for_new_objects'])

    def test_restriction_keys(self):
        layers = [
            {
                'source_db_name': 'Main',
                'access_restrictions': [
                    {'target_qname': 'Catalog.X', 'right_name': 'Read', 'field_scope': None, 'restriction_text': 'A'},
                ],
            },
            {
                'source_db_name': 'Ext',
                'access_restrictions': [
                    {'target_qname': 'Catalog.X', 'right_name': 'Read', 'field_scope': 'Ref', 'restriction_text': 'B'},
                ],
            },
        ]
        merged = merge_restrictions(layers)
        self.assertEqual(len(merged), 2)


if __name__ == '__main__':
    unittest.main()
