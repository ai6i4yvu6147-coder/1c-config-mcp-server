import sqlite3
from pathlib import Path

import pytest

from tests.conftest import METADATA_OBJECTS_DDL, build_configuration_tools
from shared.indexer_version import INDEXER_VERSION


def _create_test_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
    conn.executescript(METADATA_OBJECTS_DDL + '''
        CREATE TABLE attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            comment TEXT,
            is_standard INTEGER DEFAULT 0,
            standard_type TEXT,
            section TEXT NOT NULL DEFAULT 'Attribute'
        );
        CREATE TABLE tabular_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            comment TEXT
        );
        CREATE TABLE tabular_section_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tabular_section_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            title TEXT,
            comment TEXT
        );
        CREATE TABLE forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id INTEGER NOT NULL,
            form_name TEXT NOT NULL
        );
        CREATE TABLE form_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            is_main INTEGER DEFAULT 0,
            query_text TEXT
        );
        CREATE TABLE form_attribute_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_attribute_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            table_context TEXT
        );
        CREATE TABLE metadata_type_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_table TEXT NOT NULL,
            source_row_id INTEGER NOT NULL,
            src_object_id INTEGER NOT NULL,
            object_id INTEGER NOT NULL,
            ordinal INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE metadata_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            src_object_id INTEGER NOT NULL,
            dst_object_id INTEGER NOT NULL,
            relation_kind TEXT NOT NULL,
            source_name TEXT,
            source_detail TEXT
        );
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (1, 'Контрагенты', 'Catalog', 'ConfigObject');
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (2, 'Заказ', 'Document', 'ConfigObject');
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (3, 'Номенклатура', 'Catalog', 'ConfigObject');
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (4, 'Партнеры', 'Catalog', 'ConfigObject');
        INSERT INTO attributes (id, object_id, name, section)
        VALUES (1, 2, 'Покупатель', 'Attribute');
        INSERT INTO metadata_type_slots (source_table, source_row_id, src_object_id, object_id, ordinal)
        VALUES ('attributes', 1, 2, 1, 0);
        INSERT INTO tabular_sections (id, object_id, name)
        VALUES (1, 2, 'Строки');
        INSERT INTO tabular_section_columns (id, tabular_section_id, column_name)
        VALUES (1, 1, 'КонтрагентСтроки');
        INSERT INTO metadata_type_slots (source_table, source_row_id, src_object_id, object_id, ordinal)
        VALUES ('tabular_section_columns', 1, 2, 1, 0);
        INSERT INTO forms (id, object_id, form_name)
        VALUES (1, 3, 'ФормаЭлемента');
        INSERT INTO form_attributes (id, form_id, name)
        VALUES (1, 1, 'Владелец');
        INSERT INTO metadata_type_slots (source_table, source_row_id, src_object_id, object_id, ordinal)
        VALUES ('form_attributes', 1, 3, 1, 0);
        INSERT INTO form_attributes (id, form_id, name)
        VALUES (2, 1, 'Таблица');
        INSERT INTO form_attribute_columns (id, form_attribute_id, name)
        VALUES (1, 2, 'Ссылка');
        INSERT INTO metadata_type_slots (source_table, source_row_id, src_object_id, object_id, ordinal)
        VALUES ('form_attribute_columns', 1, 3, 1, 0);
    ''')
    conn.commit()
    conn.close()


@pytest.fixture
def tools_with_db(tmp_path):
    db_path = tmp_path / 'test.db'
    _create_test_db(db_path)
    tools = build_configuration_tools(tmp_path, db_path)
    yield tools
    tools.close_all()


def _payload(tools, name='Контрагенты'):
    results = tools.find_referencing_objects(name, project_filter='TestProject')
    return results['TestProject']['Main (base)']


def test_find_referencing_by_attribute(tools_with_db):
    payload = _payload(tools_with_db)
    assert payload['target']['name'] == 'Контрагенты'
    vias = {r['via'] for r in payload['referencers']}
    assert 'attribute' in vias
    attr = next(r for r in payload['referencers'] if r['via'] == 'attribute')
    assert attr['src_object']['name'] == 'Заказ'
    assert attr['field_name'] == 'Покупатель'


def test_find_referencing_by_tabular_section_column(tools_with_db):
    payload = _payload(tools_with_db)
    col = next(r for r in payload['referencers'] if r['via'] == 'tabular_section_column')
    assert col['src_object']['name'] == 'Заказ'
    assert col['tabular_section_name'] == 'Строки'
    assert col['field_name'] == 'КонтрагентСтроки'


def test_find_referencing_by_form_slots(tools_with_db):
    payload = _payload(tools_with_db)
    fa = next(r for r in payload['referencers'] if r['via'] == 'form_attribute')
    assert fa['src_object']['name'] == 'Номенклатура'
    assert fa['form_name'] == 'ФормаЭлемента'
    assert fa['field_name'] == 'Владелец'

    fac = next(r for r in payload['referencers'] if r['via'] == 'form_attribute_column')
    assert fac['form_attribute_name'] == 'Таблица'
    assert fac['field_name'] == 'Ссылка'


def test_find_referencing_total_count(tools_with_db):
    payload = _payload(tools_with_db)
    assert payload['total_count'] == 4
    assert payload['returned_count'] == 4
    assert payload['is_truncated'] is False


def test_find_referencing_truncation(tools_with_db):
    results = tools_with_db.find_referencing_objects(
        'Контрагенты', project_filter='TestProject', max_results=2
    )
    payload = results['TestProject']['Main (base)']
    assert payload['total_count'] == 4
    assert payload['returned_count'] == 2
    assert payload['is_truncated'] is True


def test_find_referencing_ambiguous(tools_with_db):
    # Cyrillic 'а' — partial match in several object names
    results = tools_with_db.find_referencing_objects('\u0430', project_filter='TestProject')
    payload = results['TestProject']['Main (base)']
    assert payload['ambiguous'] is True
    assert len(payload['candidates']) >= 2


def test_find_referencing_not_found(tools_with_db):
    results = tools_with_db.find_referencing_objects('Несуществующий', project_filter='TestProject')
    assert results == {}


def test_find_referencing_subsystem_member(tools_with_db):
    dbs = tools_with_db._get_active_databases()
    db_path = dbs[0]['db_path']
    conn = sqlite3.connect(db_path)
    conn.execute('''
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (5, 'ТД_ОперативныйУчет.Транспорт', 'Subsystem', 'ConfigObject')
    ''')
    conn.execute('''
        INSERT INTO metadata_relations (
            src_object_id, dst_object_id, relation_kind, source_name, source_detail
        )
        VALUES (5, 1, 'subsystem_member', 'Catalog.Контрагенты', 'Content')
    ''')
    conn.commit()
    conn.close()

    payload = _payload(tools_with_db)
    sub = next(r for r in payload['referencers'] if r['via'] == 'subsystem_member')
    assert sub['src_object']['type'] == 'Subsystem'
    assert sub['src_object']['name'] == 'ТД_ОперативныйУчет.Транспорт'
    assert sub['source_name'] == 'Catalog.Контрагенты'
    assert payload['total_count'] == 5


def test_find_referencing_relation_kinds_filter(tools_with_db):
    dbs = tools_with_db._get_active_databases()
    db_path = dbs[0]['db_path']
    conn = sqlite3.connect(db_path)
    conn.execute('''
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (5, 'РольТест', 'Role', 'ConfigObject')
    ''')
    conn.execute('''
        INSERT INTO metadata_relations (
            src_object_id, dst_object_id, relation_kind, source_name, source_detail
        )
        VALUES (5, 1, 'role_right', 'Catalog.Контрагенты', 'Right')
    ''')
    conn.execute('''
        INSERT INTO metadata_objects (id, name, object_type, object_kind)
        VALUES (6, 'ПодсистемаТест', 'Subsystem', 'ConfigObject')
    ''')
    conn.execute('''
        INSERT INTO metadata_relations (
            src_object_id, dst_object_id, relation_kind, source_name, source_detail
        )
        VALUES (6, 1, 'subsystem_member', 'Catalog.Контрагенты', 'Content')
    ''')
    conn.commit()
    conn.close()

    all_refs = tools_with_db.find_referencing_objects('Контрагенты', project_filter='TestProject')
    assert all_refs['TestProject']['Main (base)']['total_count'] == 6

    sub_only = tools_with_db.find_referencing_objects(
        'Контрагенты', project_filter='TestProject', relation_kinds=['subsystem_member']
    )
    refs = sub_only['TestProject']['Main (base)']['referencers']
    relation_vias = {
        r['via'] for r in refs
        if r['via'] not in (
            'attribute', 'tabular_section_column', 'form_attribute', 'form_attribute_column'
        )
    }
    assert relation_vias == {'subsystem_member'}
    assert sub_only['TestProject']['Main (base)']['total_count'] == 5
