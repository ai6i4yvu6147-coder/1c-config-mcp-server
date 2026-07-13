"""Integration tests for role MCP tools (layer naming, merge)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from admin_tool.db_manager import DatabaseManager
from server.tools import ConfigurationTools

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'roles' / 'Configuration.xml'


def _build_db(db_path: Path) -> None:
    db = DatabaseManager(db_path)
    db.connect(journal_mode='DELETE')
    db.create_database(str(FIXTURE))
    db.close()
    conn = sqlite3.connect(db_path)
    conn.execute('''
        INSERT INTO metadata_objects (name, object_type, object_kind)
        VALUES ('БанковскиеСчета', 'Catalog', 'ConfigObject')
    ''')
    conn.commit()
    conn.close()


def _tools_with_databases(tmp_path: Path, db_specs):
    """db_specs: list of (db_name, db_type, db_path, extension_purpose or None)."""
    tools = ConfigurationTools(
        projects_file=str(tmp_path / 'projects.json'),
        databases_dir=str(tmp_path),
    )
    active = []
    for db_name, db_type, db_path, purpose in db_specs:
        if purpose:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT OR REPLACE INTO index_metadata (key, value) VALUES ('extension_purpose', ?)",
                (purpose,),
            )
            conn.commit()
            conn.close()
        active.append({
            'project_name': 'RolesProject',
            'db_name': db_name,
            'db_type': db_type,
            'db_path': str(db_path),
        })
    tools._get_active_databases = lambda project_filter=None, include_outdated=False: active
    return tools


class TestRoleToolsLayerNaming(unittest.TestCase):
    def test_get_role_rights_layers_use_registry_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / 'main.db'
            _build_db(db_path)
            tools = _tools_with_databases(tmp_path, [
                ('Основная конфигурация', 'base', db_path, None),
            ])
            payload = tools.get_role_rights(
                'ФТ_Бюджетирование',
                project_filter='RolesProject',
            )
            self.assertEqual(payload['layers'], ['Основная конфигурация'])
            self.assertNotIn('RolesFixture', payload['layers'])
            tools.close_all()

    def test_grants_emit_db_name_not_config_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / 'main.db'
            _build_db(db_path)
            tools = _tools_with_databases(tmp_path, [
                ('Основная конфигурация', 'base', db_path, None),
            ])
            payload = tools.get_role_rights(
                'ФТ_Бюджетирование',
                project_filter='RolesProject',
                object_name='БанковскиеСчета',
                response_mode='full',
            )
            self.assertTrue(payload['grants'])
            for grant in payload['grants']:
                self.assertEqual(grant.get('db_name'), 'Основная конфигурация')
                self.assertNotIn('source_db_name', grant)
            tools.close_all()

    def test_restriction_templates_filtered_to_object_name(self):
        """restriction_templates must not dump role-wide templates unrelated to the filtered object.

        Fixture role ФТ_Бюджетирование declares a restrictionTemplate ("ДляОбъекта(ПолеОбъекта)")
        that no restriction in the role actually calls (its one restricted grant, on
        Catalog.БанковскиеСчета, uses literal inline conditions, not a "#ДляОбъекта(" macro call).
        Previously get_role_rights returned every restriction_templates row for the role
        unconditionally; it must now reflect actual usage instead.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / 'main.db'
            _build_db(db_path)
            tools = _tools_with_databases(tmp_path, [
                ('Основная конфигурация', 'base', db_path, None),
            ])
            payload = tools.get_role_rights(
                'ФТ_Бюджетирование',
                project_filter='RolesProject',
                object_name='БанковскиеСчета',
                response_mode='full',
            )
            self.assertEqual(payload['restriction_templates'], [])

            payload_unfiltered = tools.get_role_rights(
                'ФТ_Бюджетирование',
                project_filter='RolesProject',
                response_mode='full',
            )
            self.assertEqual(payload_unfiltered['restriction_templates'], [])
            tools.close_all()


class TestFindRolesForObjectMerge(unittest.TestCase):
    def test_merge_returns_flat_project_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            main_path = tmp_path / 'main.db'
            ext_path = tmp_path / 'ext.db'
            _build_db(main_path)
            _build_db(ext_path)

            conn = sqlite3.connect(ext_path)
            conn.execute('''
                INSERT INTO metadata_objects (id, name, object_type, object_kind)
                VALUES (100, 'ФТ_ТолькоВРасширении', 'Role', 'ConfigObject')
            ''')
            conn.execute('''
                INSERT INTO role_grants (
                    role_object_id, target_qname, target_kind, parent_object_qname,
                    right_name, granted, source_db_name
                )
                VALUES (100, 'Catalog.БанковскиеСчета', 'object', 'Catalog.БанковскиеСчета', 'Read', 1, 'RolesFixture')
            ''')
            conn.commit()
            conn.close()

            tools = _tools_with_databases(tmp_path, [
                ('Основная конфигурация', 'base', main_path, None),
                ('Бюджетирование', 'extension', ext_path, 'AddOn'),
            ])

            per_layer = tools.find_roles_for_object(
                'БанковскиеСчета',
                project_filter='RolesProject',
            )
            self.assertIn('Основная конфигурация (base)', per_layer['RolesProject'])
            self.assertIn('Бюджетирование (extension)', per_layer['RolesProject'])

            merged = tools.find_roles_for_object(
                'БанковскиеСчета',
                project_filter='RolesProject',
                merge=True,
            )
            project = merged['RolesProject']
            self.assertTrue(project.get('merge'))
            role_names = {r['role_name'] for r in project['roles']}
            self.assertIn('ФТ_Бюджетирование', role_names)
            self.assertIn('ФТ_ТолькоВРасширении', role_names)
            for role in project['roles']:
                self.assertIn('db_name', role)
                self.assertNotIn('source_db_name', role)
            ext_only = next(r for r in project['roles'] if r['role_name'] == 'ФТ_ТолькоВРасширении')
            self.assertEqual(ext_only['db_name'], 'Бюджетирование')
            tools.close_all()


if __name__ == '__main__':
    unittest.main()
