import os
import unittest
from pathlib import Path

from shared.xml_parser import ConfigurationParser

TD_OU = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\ТД_ОперативныйУчет'
)
KA_HAMBURG = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\КА Гамбург'
)


def _parse_export(config_dir: Path):
    config_xml = config_dir / 'Configuration.xml'
    if not config_xml.exists():
        config_xml = config_dir / 'Ext' / 'Configuration.xml'
    parser = ConfigurationParser(str(config_xml))
    return parser.parse()


def _subsystems(data):
    return [o for o in data['objects'] if o['type'] == 'Subsystem']


def _subsystem_by_name(data, qname):
    for obj in _subsystems(data):
        if obj['name'] == qname:
            return obj
    return None


@unittest.skipUnless(TD_OU.is_dir(), 'выгрузка ТД_ОперативныйУчет недоступна')
class TestSubsystemParserTdOu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _parse_export(TD_OU)

    def test_subsystem_count(self):
        self.assertGreater(len(_subsystems(self.data)), 10)

    def test_transport_content_refs(self):
        sub = _subsystem_by_name(self.data, 'ТД_ОперативныйУчет.Транспорт')
        self.assertIsNotNone(sub)
        self.assertIn('Catalog.ТранспортныеСредства', sub['content_refs'])

    def test_prodazhi_content_refs(self):
        sub = _subsystem_by_name(self.data, 'ТД_ОперативныйУчет.Продажи')
        self.assertIsNotNone(sub)
        self.assertIn('Document.ПутевойЛист', sub['content_refs'])

    def test_root_child_subsystems(self):
        sub = _subsystem_by_name(self.data, 'ТД_ОперативныйУчет')
        self.assertIsNotNone(sub)
        self.assertIn('Транспорт', sub['child_subsystem_names'])


@unittest.skipUnless(KA_HAMBURG.is_dir(), 'выгрузка КА Гамбург недоступна')
class TestSubsystemParserKaHamburg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config_xml = KA_HAMBURG / 'Configuration.xml'
        parser = ConfigurationParser(str(config_xml))
        cls.subsystems = parser._parse_subsystems()

    def test_subsystem_count_smoke(self):
        self.assertGreaterEqual(len(self.subsystems), 100)

    def test_zakupki_content_refs(self):
        sub = next((s for s in self.subsystems if s['name'] == 'Закупки'), None)
        self.assertIsNotNone(sub)
        self.assertTrue(sub['content_refs'])


if __name__ == '__main__':
    unittest.main()
