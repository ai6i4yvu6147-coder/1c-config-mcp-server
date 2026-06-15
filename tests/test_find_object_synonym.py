from pathlib import Path

import pytest

from tests.conftest import METADATA_OBJECTS_DDL, build_configuration_tools, create_test_db


def _create_test_db(path: Path) -> None:
    create_test_db(path, METADATA_OBJECTS_DDL + '''
        CREATE TABLE scheduled_jobs (
            object_id INTEGER PRIMARY KEY,
            method_name TEXT,
            description TEXT,
            key TEXT,
            use INTEGER,
            predefined INTEGER,
            restart_count_on_failure INTEGER,
            restart_interval_on_failure INTEGER
        );
        CREATE TABLE forms (id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT);
        CREATE TABLE modules (
            id INTEGER PRIMARY KEY,
            object_id INTEGER,
            form_id INTEGER,
            command_id INTEGER,
            module_type TEXT
        );
        INSERT INTO metadata_objects (name, object_type, synonym, object_kind)
        VALUES ('Контрагенты', 'Catalog', 'Справочник контрагентов', 'ConfigObject');
        INSERT INTO metadata_objects (name, object_type, synonym, object_kind)
        VALUES ('Партнеры', 'Catalog', 'Справочник партнёров', 'ConfigObject');
        INSERT INTO metadata_objects (id, name, object_type, synonym, object_kind)
        VALUES (3, 'ОбновлениеИндексов', 'ScheduledJob', 'Обновление индексов', 'ConfigObject');
        INSERT INTO scheduled_jobs (object_id, method_name, use)
        VALUES (3, 'CommonModule.Индексы.Обновить', 1);
    ''')


@pytest.fixture
def tools_with_db(tmp_path):
    db_path = tmp_path / 'test.db'
    _create_test_db(db_path)
    tools = build_configuration_tools(tmp_path, db_path)
    yield tools
    tools.close_all()


def test_find_object_by_synonym_partial(tools_with_db):
    results = tools_with_db.find_object('контрагент', project_filter='TestProject')
    items = results['TestProject']['Main (base)']
    assert len(items) == 1
    assert items[0]['name'] == 'Контрагенты'
    assert items[0]['synonym'] == 'Справочник контрагентов'


def test_find_object_by_name_still_works(tools_with_db):
    results = tools_with_db.find_object('Партнеры', project_filter='TestProject')
    items = results['TestProject']['Main (base)']
    assert len(items) == 1
    assert items[0]['name'] == 'Партнеры'


def test_get_object_structure_exact_synonym(tools_with_db):
    results = tools_with_db.get_object_structure(
        'Обновление индексов',
        project_filter='TestProject',
    )
    structure = results['TestProject']['Main (base)']
    assert structure['name'] == 'ОбновлениеИндексов'
    assert structure['type'] == 'ScheduledJob'
    assert structure['method_name'] == 'CommonModule.Индексы.Обновить'


def test_get_object_structure_ambiguous_by_synonym(tools_with_db):
    results = tools_with_db.get_object_structure(
        'Справочник',
        project_filter='TestProject',
    )
    payload = results['TestProject']['Main (base)']
    assert payload['ambiguous'] is True
    assert len(payload['candidates']) >= 2
