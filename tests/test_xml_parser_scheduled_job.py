"""Тесты парсинга ScheduledJob (регламентные задания)."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser

MAIN_EXPORT = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\Логист основная'
)
EXT_EXPORT = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\Логист расширение'
)


def _parser(root_dir):
    config = root_dir / 'Configuration.xml'
    return ConfigurationParser(str(config))


class TestParseScheduledJob(unittest.TestCase):
    @unittest.skipUnless(MAIN_EXPORT.exists(), 'нет выгрузки Логист основная')
    def test_main_export_single_scheduled_job(self):
        sj_dir = MAIN_EXPORT / 'ScheduledJobs'
        xml_files = list(sj_dir.glob('*.xml'))
        self.assertGreaterEqual(len(xml_files), 180)
        name = xml_files[0].stem
        parser = _parser(MAIN_EXPORT)
        job = parser._parse_object(name, 'ScheduledJob', 'ScheduledJobs')
        self.assertIsNotNone(job)
        props = job['properties']
        self.assertTrue(props['method_name'].startswith('CommonModule.'))
        self.assertIn('use', props)
        self.assertIsInstance(props['use'], bool)
        self.assertIn('predefined', props)
        self.assertIn('restart_count_on_failure', props)
        self.assertIn('restart_interval_on_failure', props)
        self.assertEqual(job['modules'], [])
        self.assertEqual(job['forms'], [])
        self.assertEqual(job['commands'], [])

    @unittest.skipUnless(EXT_EXPORT.exists(), 'нет выгрузки Логист расширение')
    def test_extension_export_scheduled_job(self):
        parser = _parser(EXT_EXPORT)
        jobs = [o for o in parser.parse()['objects'] if o['type'] == 'ScheduledJob']
        self.assertEqual(len(jobs), 1)
        props = jobs[0]['properties']
        self.assertTrue(props.get('method_name', '').startswith('CommonModule.'))
        self.assertIn('use', props)


if __name__ == '__main__':
    unittest.main()
