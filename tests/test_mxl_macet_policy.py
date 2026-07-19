"""MXL macet indexing policy: off for configurations/extensions, on for external
reports/processors (mxl-macet-indexing).

At corpus scale a configuration owns ~22k layout-only MXL macets that slow the build with
little analytic value, so `_parse_spreadsheet_templates` self-gates on
`index_spreadsheet_templates` (default off). `parse()` flips it on only for external report /
external data processor roots, where the macet is typically the object's whole payload. DCS
(`_parse_dcs_schemas`) is never gated — query text is valuable everywhere.
See docs/mxl-macet-indexing.md.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip('onec_metadata_schema')

from shared.xml_parser import ConfigurationParser

_MD = 'http://v8.1c.ru/8.3/MDClasses'

_MXL_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="http://v8.1c.ru/8.2/data/spreadsheet"
          xmlns:v8="http://v8.1c.ru/8.1/data/core"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <columns><size>10</size></columns>
  <rowsItem><index>0</index><row>
    <c><i>2</i><c><f>1</f>
      <tl><v8:item><v8:lang>ru</v8:lang><v8:content>Организация: [ОрганизацияНаименование]</v8:content></v8:item></tl>
    </c></c>
  </row></rowsItem>
  <namedItem xsi:type="NamedItemCells"><name>Шапка</name>
    <area><type>Rows</type><beginRow>0</beginRow><endRow>0</endRow></area></namedItem>
</document>
"""


def _template_descriptor(name, template_type):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<MetaDataObject xmlns="{_MD}"><Template uuid="0000">'
        f'<Properties><Name>{name}</Name>'
        f'<TemplateType>{template_type}</TemplateType></Properties>'
        '</Template></MetaDataObject>'
    )


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _macet_on_disk(base: Path, template_name='ПФ_MXL_Основная'):
    """Write a SpreadsheetDocument template under base/Templates/ and return the parser."""
    tdir = base / 'Templates'
    _write(tdir / f'{template_name}.xml', _template_descriptor(template_name, 'SpreadsheetDocument'))
    _write(tdir / template_name / 'Ext' / 'Template.xml', _MXL_BODY)


# --- flag gate (the policy itself) -------------------------------------------------------

def test_macet_not_indexed_when_flag_off(tmp_path):
    _macet_on_disk(tmp_path / 'Reports' / 'Отчёт')
    parser = ConfigurationParser(str(tmp_path / 'Configuration.xml'))
    assert parser.index_spreadsheet_templates is False  # config default
    assert parser._parse_spreadsheet_templates('Отчёт', 'Reports') == []


def test_macet_indexed_when_flag_on(tmp_path):
    _macet_on_disk(tmp_path / 'Reports' / 'Отчёт')
    parser = ConfigurationParser(str(tmp_path / 'Configuration.xml'))
    parser.index_spreadsheet_templates = True
    macets = parser._parse_spreadsheet_templates('Отчёт', 'Reports')
    assert [m['template_name'] for m in macets] == ['ПФ_MXL_Основная']
    assert 'ОрганизацияНаименование' in macets[0]['text']
    assert 'Шапка' in macets[0]['text']


# --- dispatch: parse() sets the flag per root kind ---------------------------------------

def _config_root(name='Демо'):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<MetaDataObject xmlns="{_MD}"><Configuration>'
        f'<Properties><Name>{name}</Name></Properties><ChildObjects/>'
        '</Configuration></MetaDataObject>'
    )


def _external_report_root(name='ВнешнийОтчёт'):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<MetaDataObject xmlns="{_MD}"><ExternalReport uuid="1111">'
        f'<Properties><Name>{name}</Name></Properties>'
        '</ExternalReport></MetaDataObject>'
    )


def test_configuration_root_leaves_macets_off(tmp_path):
    cfg = tmp_path / 'Configuration.xml'
    cfg.write_text(_config_root(), encoding='utf-8')
    parser = ConfigurationParser(str(cfg))
    parser.parse()
    assert parser.index_spreadsheet_templates is False


def test_external_report_root_indexes_macets(tmp_path):
    name = 'ВнешнийОтчёт'
    root_xml = tmp_path / f'{name}.xml'
    root_xml.write_text(_external_report_root(name), encoding='utf-8')
    _macet_on_disk(tmp_path / name)  # <root>/<Name>/Templates/…

    parser = ConfigurationParser(str(root_xml))
    data = parser.parse()

    assert parser.index_spreadsheet_templates is True
    obj = data['objects'][0]
    assert obj['type'] == 'Report'
    macets = obj['spreadsheet_templates']
    assert [m['template_name'] for m in macets] == ['ПФ_MXL_Основная']
    assert 'ОрганизацияНаименование' in macets[0]['text']
