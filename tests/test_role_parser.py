import sqlite3
import tempfile
import unittest
from pathlib import Path

from admin_tool.db_manager import DatabaseManager
from shared.indexer_version import INDEXER_VERSION
from shared.xml_parser import ConfigurationParser
from shared.xml_parser.role_qname import classify_target_qname

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'roles' / 'Configuration.xml'


def _roles(data):
    return [o for o in data['objects'] if o['type'] == 'Role']


def _role_by_name(data, name):
    for obj in _roles(data):
        if obj['name'] == name:
            return obj
    return None


class TestRoleQname(unittest.TestCase):
    def test_object_level(self):
        kind, parent = classify_target_qname('Catalog.Контрагенты')
        self.assertEqual(kind, 'object')
        self.assertEqual(parent, 'Catalog.Контрагенты')

    def test_attribute_level(self):
        kind, parent = classify_target_qname('Report.ФТ_ОтчетБДДС.Attribute.ВариантОтчета')
        self.assertEqual(kind, 'attribute')
        self.assertEqual(parent, 'Report.ФТ_ОтчетБДДС')

    def test_configuration(self):
        kind, parent = classify_target_qname('Configuration.RolesFixture')
        self.assertEqual(kind, 'configuration')
        self.assertEqual(parent, 'Configuration.RolesFixture')


class TestRoleParserFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parser = ConfigurationParser(str(FIXTURE))
        cls.data = parser.parse()

    def test_role_count(self):
        self.assertEqual(len(_roles(self.data)), 5)

    def test_adopted_without_rights(self):
        role = _role_by_name(self.data, 'ДобавлениеИзменениеДанныхБухгалтерии')
        self.assertIsNotNone(role)
        self.assertEqual(role['properties'].get('object_belonging'), 'Adopted')
        self.assertIsNone(role['role_settings'])
        self.assertEqual(role['role_grants'], [])

    def test_field_restriction(self):
        role = _role_by_name(self.data, 'ЧтениеИнформацииОВерсияхОбъектов')
        self.assertIsNotNone(role)
        restr = role['role_access_restrictions']
        self.assertEqual(len(restr), 1)
        self.assertEqual(restr[0]['field_scope'], 'ВерсияОбъекта')

    def test_dual_restrictions(self):
        role = _role_by_name(self.data, 'ФТ_Бюджетирование')
        self.assertIsNotNone(role)
        bank = [
            r for r in role['role_access_restrictions']
            if r['target_qname'] == 'Catalog.БанковскиеСчета' and r['right_name'] == 'Read'
        ]
        self.assertEqual(len(bank), 2)
        scopes = {r['field_scope'] for r in bank}
        self.assertIn(None, scopes)
        self.assertIn('Ref', scopes)

    def test_poznacheniyam_verbatim(self):
        role = _role_by_name(self.data, 'ЧтениеЭЛН')
        self.assertIsNotNone(role)
        restr = role['role_access_restrictions']
        self.assertTrue(any('#ПоЗначениям' in (r['restriction_text'] or '') for r in restr))

    def test_restriction_templates(self):
        role = _role_by_name(self.data, 'ФТ_Бюджетирование')
        self.assertGreaterEqual(len(role['role_restriction_templates']), 1)


class TestRoleIndexFixture(unittest.TestCase):
    def test_build_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'roles.db'
            db = DatabaseManager(db_path)
            db.connect(journal_mode='DELETE')
            db.create_database(str(FIXTURE))
            db.close()

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            ver = conn.execute('PRAGMA user_version').fetchone()[0]
            self.assertEqual(ver, INDEXER_VERSION)

            role_count = conn.execute(
                "SELECT COUNT(*) FROM metadata_objects WHERE object_type = 'Role'"
            ).fetchone()[0]
            self.assertEqual(role_count, 5)

            grants = conn.execute('SELECT COUNT(*) FROM role_grants').fetchone()[0]
            self.assertGreater(grants, 0)

            restr = conn.execute('SELECT COUNT(*) FROM role_access_restrictions').fetchone()[0]
            self.assertGreaterEqual(restr, 3)

            meta = dict(conn.execute('SELECT key, value FROM index_metadata').fetchall())
            self.assertEqual(meta.get('config_name'), 'RolesFixture')
            conn.close()


if __name__ == '__main__':
    unittest.main()
