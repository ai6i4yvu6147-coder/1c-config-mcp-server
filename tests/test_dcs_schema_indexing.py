"""Срез 1 (dcs-schema-indexing): DCS template discovery + dataset query text -> FTS.

Two halves: the parser mixin finds DataCompositionSchema templates (skipping MXL and
degrading past query-less schemas), and the insertion mixin lands each dataset query text
in code_search as a searchable DcsQuery row. See docs/dcs-schema-indexing.md.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip('onec_metadata_schema')

from shared.xml_parser import ConfigurationParser
from admin_tool.db_manager.insert_objects import ObjectInsertionMixin
from tests.conftest import build_configuration_tools, create_test_db, METADATA_OBJECTS_DDL

_MD = 'http://v8.1c.ru/8.3/MDClasses'


def _descriptor(name, template_type):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<MetaDataObject xmlns="{_MD}"><Template uuid="0000">'
        f'<Properties><Name>{name}</Name>'
        f'<TemplateType>{template_type}</TemplateType></Properties>'
        '</Template></MetaDataObject>'
    )


def _dcs_body(query=None):
    query_elem = f'<query>{query}</query>' if query is not None else ''
    return (
        '<DataCompositionSchema '
        'xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dataSource><name>ИсточникДанных1</name><dataSourceType>Local</dataSourceType></dataSource>'
        '<dataSet xsi:type="DataSetQuery"><name>Набор1</name>'
        '<field xsi:type="DataSetFieldField"><dataPath>Ссылка</dataPath></field>'
        f'{query_elem}</dataSet>'
        '</DataCompositionSchema>'
    )


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _object_with_templates(tmp: Path, folder, name, templates):
    """templates: list of (template_name, descriptor_type, body_or_None)."""
    tdir = tmp / folder / name / 'Templates'
    for tname, ttype, body in templates:
        _write(tdir / f'{tname}.xml', _descriptor(tname, ttype))
        if body is not None:
            _write(tdir / tname / 'Ext' / 'Template.xml', body)
    return ConfigurationParser(str(tmp / 'Configuration.xml'))


# --- parser: discovery -------------------------------------------------------------------

def test_discovers_dcs_and_skips_mxl(tmp_path):
    parser = _object_with_templates(tmp_path, 'Catalogs', 'Номенклатура', [
        ('СхемаСКД', 'DataCompositionSchema', _dcs_body('ВЫБРАТЬ Ссылка ИЗ Справочник.Номенклатура')),
        ('ПечатнаяФорма', 'SpreadsheetDocument', '<document/>'),
    ])
    schemas = parser._parse_dcs_schemas('Номенклатура', 'Catalogs')
    assert [s['template_name'] for s in schemas] == ['СхемаСКД']  # MXL skipped
    assert schemas[0]['query_texts'] == ['ВЫБРАТЬ Ссылка ИЗ Справочник.Номенклатура']
    assert schemas[0]['shape']['has_query'] is True
    assert parser.skipped_dcs == []


def test_no_templates_dir_is_empty(tmp_path):
    (tmp_path / 'Catalogs' / 'Пустой').mkdir(parents=True)
    parser = ConfigurationParser(str(tmp_path / 'Configuration.xml'))
    assert parser._parse_dcs_schemas('Пустой', 'Catalogs') == []


def test_query_less_schema_degrades(tmp_path):
    # ~14%+ of real schemas (catalog filter rules) have no <query>: found, but no FTS text.
    parser = _object_with_templates(tmp_path, 'Catalogs', 'Договоры', [
        ('Отборы', 'DataCompositionSchema', _dcs_body(query=None)),
    ])
    schemas = parser._parse_dcs_schemas('Договоры', 'Catalogs')
    assert len(schemas) == 1
    assert schemas[0]['query_texts'] == []
    assert schemas[0]['shape']['has_query'] is False
    assert parser.skipped_dcs == []


def test_broken_schema_is_skipped_not_fatal(tmp_path):
    parser = _object_with_templates(tmp_path, 'Catalogs', 'Битый', [
        ('СхемаСКД', 'DataCompositionSchema', '<DataCompositionSchema><dataSet'),  # malformed
    ])
    schemas = parser._parse_dcs_schemas('Битый', 'Catalogs')
    assert schemas == []
    assert len(parser.skipped_dcs) == 1
    assert parser.skipped_dcs[0]['template'] == 'СхемаСКД'
    assert parser.skipped_dcs[0]['error']


# --- insertion: query text -> code_search FTS --------------------------------------------

_INSERT_SCHEMA = '''
    CREATE TABLE modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, object_id INTEGER, form_id INTEGER,
        command_id INTEGER, module_type TEXT NOT NULL, code TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE code_search USING fts5(
        code, content='modules', content_rowid='id'
    );
    CREATE TABLE dcs_schema (
        id INTEGER PRIMARY KEY AUTOINCREMENT, object_id INTEGER NOT NULL,
        template_name TEXT NOT NULL, has_query INTEGER NOT NULL DEFAULT 0,
        dataset_count INTEGER NOT NULL DEFAULT 0, field_count INTEGER NOT NULL DEFAULT 0,
        parameter_count INTEGER NOT NULL DEFAULT 0, calculated_count INTEGER NOT NULL DEFAULT 0,
        total_count INTEGER NOT NULL DEFAULT 0, has_grouping INTEGER NOT NULL DEFAULT 0,
        filter_item_count INTEGER NOT NULL DEFAULT 0, schema_json TEXT NOT NULL
    );
'''

_OBJ = {
    'name': 'Номенклатура',
    'dcs_schemas': [
        {'template_name': 'СхемаСКД',
         'query_texts': ['ВЫБРАТЬ Ссылка ИЗ Справочник.Номенклатура'],
         'schema': {'datasets': [{'name': 'Набор1', 'query': 'ВЫБРАТЬ Ссылка', 'fields': []}]},
         'shape': {'has_query': True, 'dataset_count': 1, 'field_count': 3,
                   'parameter_count': 2, 'calculated_count': 0, 'total_count': 1,
                   'has_grouping': True, 'filter_item_count': 4}},
        {'template_name': 'Отборы', 'query_texts': [],  # query-less -> no FTS row
         'schema': {'datasets': []},
         'shape': {'has_query': False, 'dataset_count': 0, 'field_count': 0,
                   'parameter_count': 0, 'calculated_count': 0, 'total_count': 0,
                   'has_grouping': False, 'filter_item_count': 0}},
    ],
}


def test_query_text_becomes_searchable_dcs_query_row():
    conn = sqlite3.connect(':memory:')
    conn.executescript(_INSERT_SCHEMA)
    cursor = conn.cursor()
    ObjectInsertionMixin()._insert_dcs_schemas(cursor, 42, _OBJ)

    rows = cursor.execute(
        "SELECT m.object_id, m.module_type, m.code FROM code_search cs "
        "JOIN modules m ON m.id = cs.rowid WHERE code_search MATCH 'Номенклатура'"
    ).fetchall()
    assert len(rows) == 1  # only the schema with a <query> yields an FTS row
    object_id, module_type, code = rows[0]
    assert object_id == 42
    assert module_type == 'DcsQuery'
    assert 'Справочник.Номенклатура' in code
    conn.close()


def test_dcs_schema_document_and_shape_hints_stored():
    conn = sqlite3.connect(':memory:')
    conn.executescript(_INSERT_SCHEMA)
    cursor = conn.cursor()
    ObjectInsertionMixin()._insert_dcs_schemas(cursor, 42, _OBJ)

    rows = cursor.execute(
        "SELECT template_name, has_query, field_count, total_count, has_grouping, "
        "filter_item_count, schema_json FROM dcs_schema WHERE object_id = 42 "
        "ORDER BY template_name"
    ).fetchall()
    assert len(rows) == 2  # both schemas stored (Срез 2), query-less one included
    otbory, skd = rows
    assert otbory[0] == 'Отборы' and otbory[1] == 0  # has_query False
    assert skd[0] == 'СхемаСКД'
    assert skd[1] == 1 and skd[2] == 3 and skd[3] == 1  # has_query, field_count, total_count
    assert skd[4] == 1 and skd[5] == 4  # has_grouping, filter_item_count
    import json
    assert json.loads(skd[6])['datasets'][0]['name'] == 'Набор1'
    conn.close()


# --- get_dcs_schema tool -----------------------------------------------------------------

_TOOL_DDL = METADATA_OBJECTS_DDL + '''
    CREATE TABLE dcs_schema (
        id INTEGER PRIMARY KEY AUTOINCREMENT, object_id INTEGER NOT NULL,
        template_name TEXT NOT NULL, has_query INTEGER NOT NULL DEFAULT 0,
        dataset_count INTEGER NOT NULL DEFAULT 0, field_count INTEGER NOT NULL DEFAULT 0,
        parameter_count INTEGER NOT NULL DEFAULT 0, calculated_count INTEGER NOT NULL DEFAULT 0,
        total_count INTEGER NOT NULL DEFAULT 0, has_grouping INTEGER NOT NULL DEFAULT 0,
        filter_item_count INTEGER NOT NULL DEFAULT 0, schema_json TEXT NOT NULL
    );
    INSERT INTO metadata_objects (id, object_type, name, object_kind)
        VALUES (1, 'Catalog', 'Номенклатура', 'ConfigObject');
    INSERT INTO dcs_schema (object_id, template_name, has_query, dataset_count, field_count,
        parameter_count, calculated_count, total_count, has_grouping, filter_item_count, schema_json)
        VALUES
        (1, 'СхемаСКД', 1, 1, 3, 2, 0, 1, 1, 4,
         '{"datasets":[{"name":"Набор1","kind":"DataSetQuery","query":"ВЫБРАТЬ Ссылка","fields":[]}],"parameters":[],"calculated_fields":[],"total_fields":[],"settings_variants":[],"dataset_links":[],"data_sources":[]}'),
        (1, 'Отборы', 0, 0, 0, 0, 0, 0, 0, 0, '{"datasets":[]}');
'''


@pytest.fixture
def dcs_tools(tmp_path):
    db_path = tmp_path / 'test.db'
    create_test_db(db_path, _TOOL_DDL)
    t = build_configuration_tools(tmp_path, db_path)
    yield t
    t.close_all()


def test_get_dcs_schema_overview_lists_all(dcs_tools):
    res = dcs_tools.get_dcs_schema('Номенклатура', project_filter='TestProject')
    payload = res['TestProject']['Main (base)']
    assert payload['type'] == 'Catalog' and payload['object'] == 'Номенклатура'
    names = {s['template_name'] for s in payload['schemas']}
    assert names == {'СхемаСКД', 'Отборы'}
    # overview only: no full document attached when the object has >1 schema
    assert all('schema' not in s for s in payload['schemas'])
    skd = next(s for s in payload['schemas'] if s['template_name'] == 'СхемаСКД')
    assert skd['has_query'] is True and skd['field_count'] == 3 and skd['has_grouping'] is True
    otbory = next(s for s in payload['schemas'] if s['template_name'] == 'Отборы')
    assert otbory['has_query'] is False  # stored filter rule, not a data query


def test_get_dcs_schema_template_attaches_document(dcs_tools):
    res = dcs_tools.get_dcs_schema('Номенклатура', project_filter='TestProject',
                                   template='СхемаСКД')
    payload = res['TestProject']['Main (base)']
    assert len(payload['schemas']) == 1
    doc = payload['schemas'][0]['schema']  # single target -> full document attached
    assert doc['datasets'][0]['name'] == 'Набор1'
    assert doc['datasets'][0]['query'] == 'ВЫБРАТЬ Ссылка'


def test_get_dcs_schema_unknown_object_is_empty(dcs_tools):
    assert dcs_tools.get_dcs_schema('НетТакого', project_filter='TestProject') == {}
