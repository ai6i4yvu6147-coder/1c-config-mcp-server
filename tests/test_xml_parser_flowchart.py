"""Тесты парсинга Flowchart.xml (точки маршрута BusinessProcess)."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser

FLOWCHART_EXPORT = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\Логист расширение'
    r'\BusinessProcesses\ФТ_СогласованиеДоговора\Ext\Flowchart.xml'
)


def _parser(root_dir):
    config = root_dir / 'Configuration.xml'
    return ConfigurationParser(str(config))


class TestParseFlowchart(unittest.TestCase):
    @unittest.skipUnless(FLOWCHART_EXPORT.exists(), 'нет выгрузки Логист расширение')
    def test_real_flowchart_route_points(self):
        export_root = FLOWCHART_EXPORT.parent.parent.parent.parent
        parser = _parser(export_root)
        data = parser._parse_flowchart('ФТ_СогласованиеДоговора', 'BusinessProcesses')
        points = {p['name']: p for p in data['route_points']}

        self.assertIn('НаПодписанииУНас', points)
        self.assertIn('НаПодписанииУКонтрагента', points)
        self.assertEqual(points['НаПодписанииУНас']['type'], 'Activity')
        self.assertEqual(points['НаПодписанииУКонтрагента']['type'], 'Activity')
        self.assertIn('На подписании у нас', points['НаПодписанииУНас']['title'])

        transitions = data['route_transitions']
        self.assertTrue(transitions)
        from_names = {t['from'] for t in transitions}
        to_names = {t['to'] for t in transitions}
        self.assertTrue(
            'НаПодписанииУНас' in from_names or 'НаПодписанииУНас' in to_names
            or 'НаПодписанииУКонтрагента' in from_names or 'НаПодписанииУКонтрагента' in to_names
        )

    def test_missing_flowchart_returns_empty(self):
        parser = ConfigurationParser(str(ROOT / 'nonexistent' / 'Configuration.xml'))
        data = parser._parse_flowchart('NoSuchBP', 'BusinessProcesses')
        self.assertEqual(data['route_points'], [])
        self.assertEqual(data['route_transitions'], [])


if __name__ == '__main__':
    unittest.main()
