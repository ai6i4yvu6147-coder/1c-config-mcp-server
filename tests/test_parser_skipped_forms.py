"""P-2: parse errors in a form must be counted, not just printed and dropped."""
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser


def _parser():
    return ConfigurationParser(str(ROOT / 'nonexistent' / 'Configuration.xml'))


class TestSkippedForms(unittest.TestCase):
    def test_broken_form_xml_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            form_dir = Path(tmp) / 'ФормаСписка'
            (form_dir / 'Ext').mkdir(parents=True)
            (form_dir / 'Ext' / 'Form.xml').write_text('<not valid xml', encoding='utf-8')

            parser = _parser()
            result = parser._parse_form(form_dir)

            self.assertIsNone(result)
            self.assertEqual(len(parser.skipped_forms), 1)
            self.assertIn(str(form_dir), parser.skipped_forms[0]['path'])
            self.assertTrue(parser.skipped_forms[0]['error'])

    def test_missing_form_xml_is_not_an_error(self):
        """No Ext/Form.xml at all is a normal no-op (e.g. directory without a form),
        not a parse failure — must not be counted as skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            form_dir = Path(tmp) / 'ПустаяПапка'
            form_dir.mkdir()

            parser = _parser()
            result = parser._parse_form(form_dir)

            self.assertIsNone(result)
            self.assertEqual(parser.skipped_forms, [])


if __name__ == '__main__':
    unittest.main()
