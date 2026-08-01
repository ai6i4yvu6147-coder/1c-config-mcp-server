"""P-8 (audit-2026-08): forms are parsed via a ProcessPoolExecutor when parse() runs — the
parallel path must produce byte-identical objects (and identical skipped_forms/
skipped_form_modules aggregation) to the sequential path (use_process_pool=False).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip('onec_metadata_schema')

from shared.xml_parser import ConfigurationParser

MD = 'http://v8.1c.ru/8.3/MDClasses'
LF = 'http://v8.1c.ru/8.3/xcf/logform'

_FORM_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="{LF}">
  <Events>
    <Event name="ПриСозданииНаСервере">Форма_ПриСоздании</Event>
  </Events>
  <ChildItems>
    <InputField name="Поле1" id="1">
      <DataPath>Объект.Реквизит1</DataPath>
    </InputField>
  </ChildItems>
  <AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>
</Form>
"""

_CONFIG_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{MD}">
  <Configuration>
    <Properties><Name>ТестКонфиг</Name></Properties>
    <ChildObjects>
      <Catalog>ТестСправочник</Catalog>
    </ChildObjects>
  </Configuration>
</MetaDataObject>
"""

_CATALOG_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{MD}">
  <Catalog uuid="00000000-0000-0000-0000-000000000001">
    <Properties><Name>ТестСправочник</Name></Properties>
    <ChildObjects/>
  </Catalog>
</MetaDataObject>
"""


def _build_fixture(base: Path):
    base.mkdir(parents=True, exist_ok=True)
    (base / 'Configuration.xml').write_text(_CONFIG_XML, encoding='utf-8')
    catalogs = base / 'Catalogs'
    catalogs.mkdir()
    (catalogs / 'ТестСправочник.xml').write_text(_CATALOG_XML, encoding='utf-8')
    obj_dir = catalogs / 'ТестСправочник'

    # Two valid forms, one with a module.
    for form_name in ('ФормаСписка', 'ФормаЭлемента'):
        form_ext_dir = obj_dir / 'Forms' / form_name / 'Ext'
        form_ext_dir.mkdir(parents=True)
        (form_ext_dir / 'Form.xml').write_text(_FORM_XML, encoding='utf-8')

    module_dir = obj_dir / 'Forms' / 'ФормаЭлемента' / 'Ext' / 'Form'
    module_dir.mkdir(parents=True)
    (module_dir / 'Module.bsl').write_text(
        'Процедура ПриОткрытии(Отказ) Экспорт\nКонецПроцедуры', encoding='utf-8-sig',
    )

    # One broken Form.xml -> skipped_forms.
    broken_dir = obj_dir / 'Forms' / 'СломаннаяФорма' / 'Ext'
    broken_dir.mkdir(parents=True)
    (broken_dir / 'Form.xml').write_text('<not valid xml', encoding='utf-8')

    # One valid form whose Module.bsl path is a directory, not a file -> skipped_form_modules.
    bad_module_dir = obj_dir / 'Forms' / 'ФормаСПлохимМодулем' / 'Ext'
    bad_module_dir.mkdir(parents=True)
    (bad_module_dir / 'Form.xml').write_text(_FORM_XML, encoding='utf-8')
    (bad_module_dir / 'Form' / 'Module.bsl').mkdir(parents=True)

    return base / 'Configuration.xml'


def _catalog(data):
    return next(o for o in data['objects'] if o['type'] == 'Catalog')


def _forms_by_name(data):
    return {f['name']: f for f in _catalog(data)['forms']}


class TestParallelFormParsing(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config_xml = _build_fixture(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pool_path_matches_sequential_path(self):
        seq_parser = ConfigurationParser(str(self.config_xml), use_process_pool=False)
        seq_data = seq_parser.parse()

        pool_parser = ConfigurationParser(str(self.config_xml), use_process_pool=True)
        pool_data = pool_parser.parse()

        self.assertIsNone(seq_parser._form_pool)  # never created — flag off
        # Pool is only created transiently inside parse(); by the time parse() returns it's
        # already shut down and reset.
        self.assertIsNone(pool_parser._form_pool)

        self.assertEqual(seq_data, pool_data)

        forms = _forms_by_name(pool_data)
        self.assertEqual(set(forms), {'ФормаСписка', 'ФормаЭлемента', 'ФормаСПлохимМодулем'})
        self.assertIsNone(forms['ФормаСписка']['module'])
        self.assertIn('ПриОткрытии', forms['ФормаЭлемента']['module'])
        self.assertIsNone(forms['ФормаСПлохимМодулем']['module'])  # module read failed

        self.assertEqual(len(seq_parser.skipped_forms), 1)
        self.assertIn('СломаннаяФорма', seq_parser.skipped_forms[0]['path'])
        self.assertEqual(len(pool_parser.skipped_forms), 1)
        self.assertIn('СломаннаяФорма', pool_parser.skipped_forms[0]['path'])

        self.assertEqual(len(seq_parser.skipped_form_modules), 1)
        self.assertIn('ФормаСПлохимМодулем', seq_parser.skipped_form_modules[0]['path'])
        self.assertEqual(len(pool_parser.skipped_form_modules), 1)
        self.assertIn('ФормаСПлохимМодулем', pool_parser.skipped_form_modules[0]['path'])

    def test_pool_is_torn_down_even_on_error(self):
        """If parse() raises, the pool must still be shut down (no leaked worker processes)."""
        broken_config = self.tmp / 'BadConfiguration.xml'
        broken_config.write_text('<not valid xml', encoding='utf-8')
        parser = ConfigurationParser(str(broken_config), use_process_pool=True)
        with self.assertRaises(Exception):
            parser.parse()
        self.assertIsNone(parser._form_pool)


if __name__ == '__main__':
    unittest.main()
