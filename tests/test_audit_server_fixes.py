"""Правки server/ по аудиту 2026-08 (T-8…T-12 и § 6.6).

Все четыре дефекта были «тихими»: ошибки не возникало, ответ выглядел валидным —
поэтому тесты проверяют именно то, что раньше молчало: произвольный выбор объекта при
совпадении имён, отсутствие потолка ответа, уход в LIKE при любом фильтре и сырую
ошибку SQLite наружу.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.tools.code import _fts_phrase, _fts_query_is_safe
from server.tools.relations import _fetch_referencing_role_grants, _resolve_config_object
from server.tool_schemas import (
    BSL_MODULE_TYPE_ENUM,
    MODULE_TYPE_ENUM,
    OBJECT_TYPE_ENUM,
    TOOL_SCHEMAS,
)
from shared.indexer_version import INDEXER_VERSION
from shared.metadata_type_resolver import REF_SUFFIX_TO_OBJECT_TYPE
from shared.xml_parser.core import CHILD_OBJECT_TYPES
from tests.conftest import build_configuration_tools


# --- T-8: неоднозначность точного имени ----------------------------------------------------

_OBJECTS_DDL = '''
    CREATE TABLE metadata_objects (
        id INTEGER PRIMARY KEY, uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
        synonym TEXT, comment TEXT, object_belonging TEXT, extended_configuration_object TEXT,
        object_kind TEXT NOT NULL DEFAULT 'ConfigObject'
    );
'''


@pytest.fixture
def objects_cursor():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(_OBJECTS_DDL)
    # «Взаиморасчеты» в ЕРП — разом Document, CommonModule, AccumulationRegister, Report и Role
    conn.executemany(
        "INSERT INTO metadata_objects (object_type, name, synonym) VALUES (?, ?, ?)",
        [
            ('Document', 'Взаиморасчеты', ''),
            ('CommonModule', 'Взаиморасчеты', ''),
            ('AccumulationRegister', 'Взаиморасчеты', ''),
            ('Catalog', 'Номенклатура', 'Взаиморасчеты'),
            ('Catalog', 'Склады', ''),
        ],
    )
    conn.commit()
    yield conn.cursor()
    conn.close()


def test_exact_name_shared_by_several_kinds_is_ambiguous(objects_cursor):
    """Раньше здесь стоял LIMIT 1 без ORDER BY: возвращался объект, который SQLite отдал
    первым, — выбор произволен и мог меняться между пересборками."""
    resolved = _resolve_config_object(objects_cursor, 'Взаиморасчеты')
    assert resolved['status'] == 'ambiguous'
    assert resolved['match_kind'] == 'exact'
    assert {c['type'] for c in resolved['candidates']} == {
        'Document', 'CommonModule', 'AccumulationRegister',
    }


def test_object_type_resolves_the_ambiguity(objects_cursor):
    resolved = _resolve_config_object(objects_cursor, 'Взаиморасчеты', 'CommonModule')
    assert resolved['status'] == 'found'
    assert resolved['row']['object_type'] == 'CommonModule'


def test_exact_name_beats_synonym(objects_cursor):
    """Каталог «Номенклатура» имеет синоним «Взаиморасчеты», но точное совпадение по имени
    сильнее: иначе синонимы плодили бы ложную неоднозначность."""
    resolved = _resolve_config_object(objects_cursor, 'Номенклатура')
    assert resolved['status'] == 'found'
    assert resolved['row']['name'] == 'Номенклатура'


def test_unique_exact_name_still_resolves(objects_cursor):
    resolved = _resolve_config_object(objects_cursor, 'Склады')
    assert resolved['status'] == 'found'
    assert resolved['row']['object_type'] == 'Catalog'


def test_partial_match_keeps_its_ambiguous_contract(objects_cursor):
    resolved = _resolve_config_object(objects_cursor, 'клад')  # только Склады
    assert resolved['status'] == 'found'
    resolved = _resolve_config_object(objects_cursor, 'расчеты')
    assert resolved['status'] == 'ambiguous'
    assert resolved['match_kind'] == 'partial'


def test_not_found_is_unchanged(objects_cursor):
    assert _resolve_config_object(objects_cursor, 'Такого нет')['status'] == 'not_found'


# --- § 6.6: голый except в role_grants -----------------------------------------------------

def test_role_grants_absent_table_is_silent(objects_cursor):
    """База, собранная до фазы 4, легально не имеет role_grants."""
    assert _fetch_referencing_role_grants(objects_cursor, 'Document.Взаиморасчеты') == []


def test_role_grants_real_error_is_not_swallowed(objects_cursor):
    """Таблица есть, но структура не та — это ошибка, а не «ссылок нет».

    Прежний `except Exception: return []` глушил такое молча.
    """
    objects_cursor.execute('CREATE TABLE role_grants (id INTEGER PRIMARY KEY)')
    with pytest.raises(sqlite3.OperationalError):
        _fetch_referencing_role_grants(objects_cursor, 'Document.Взаиморасчеты')


# --- T-10: экранирование FTS ---------------------------------------------------------------

@pytest.mark.parametrize('query', [
    'Товар-Услуга',          # OperationalError: no such column: Услуга
    'ОбщегоНазначения:X',    # OperationalError: no such column: ОбщегоНазначения
    'Тест AND',              # fts5: syntax error near ""
    'Провести*',
    '^Начало',
    'Справочники.Номенклатура',
    'Метод(Парам)',
    'Кавычка"внутри',
])
def test_fts_unsafe_queries_are_routed_away_from_fts(query):
    assert not _fts_query_is_safe(query)


@pytest.mark.parametrize('query', ['Провести', 'ОбработкаПроведения', 'Провести документ'])
def test_ordinary_queries_stay_on_fts(query):
    assert _fts_query_is_safe(query)


def test_fts_phrase_escapes_quotes():
    assert _fts_phrase('Тест') == '"Тест"'
    assert _fts_phrase('А "Б" В') == '"А ""Б"" В"'


# --- § 6.6: enum в JSON-схемах -------------------------------------------------------------

def _schema(name):
    for tool in TOOL_SCHEMAS:
        if tool.name == name:
            # mcp.types.Tool — pydantic-модель: конструируется по алиасу inputSchema,
            # читается по имени поля input_schema.
            return tool.input_schema['properties']
    raise AssertionError(f'нет tool {name}')


def test_object_type_enum_covers_everything_the_indexer_writes():
    """Забыли добавить вид в enum — агент не сможет им воспользоваться, хотя объекты
    такого вида в индексе есть."""
    missing = set(CHILD_OBJECT_TYPES) - set(OBJECT_TYPE_ENUM)
    assert not missing, f'виды парсера вне enum: {sorted(missing)}'


def test_object_type_enum_covers_reference_targets():
    """Резолвер типов умеет назвать вид по суффиксу ссылки — значит, по нему можно и
    фильтровать; расхождение этих двух списков уже приводило к тихой потере слотов."""
    missing = set(REF_SUFFIX_TO_OBJECT_TYPE.values()) - set(OBJECT_TYPE_ENUM)
    assert not missing, f'цели ссылок вне enum: {sorted(missing)}'


def test_bsl_module_enum_is_subset_of_module_enum():
    assert set(BSL_MODULE_TYPE_ENUM) < set(MODULE_TYPE_ENUM)
    # DcsQuery/MxlText ищутся, но не отдаются как код модуля
    assert {'DcsQuery', 'MxlText'} <= set(MODULE_TYPE_ENUM)
    assert not {'DcsQuery', 'MxlText'} & set(BSL_MODULE_TYPE_ENUM)


@pytest.mark.parametrize('tool_name,prop,expected', [
    ('search_code', 'module_type', MODULE_TYPE_ENUM),
    ('get_module_code', 'module_type', BSL_MODULE_TYPE_ENUM),
    ('get_module_procedures', 'module_type', BSL_MODULE_TYPE_ENUM),
    ('get_procedure_code', 'module_type', BSL_MODULE_TYPE_ENUM),
    ('list_objects', 'object_type', OBJECT_TYPE_ENUM),
    ('get_object_structure', 'object_type', OBJECT_TYPE_ENUM),
    ('find_referencing_objects', 'object_type', OBJECT_TYPE_ENUM),
    ('get_dcs_schema', 'object_type', OBJECT_TYPE_ENUM),
    ('find_roles_for_object', 'object_type', OBJECT_TYPE_ENUM),
])
def test_enumerated_params_declare_enum(tool_name, prop, expected):
    assert _schema(tool_name)[prop]['enum'] == expected


def test_form_element_type_declares_enum():
    assert _schema('get_functional_options')['element_type']['enum'] == [
        'FormAttribute', 'FormCommand', 'FormItem', 'FormAttributeColumn',
    ]


# --- T-9 / T-11 / T-12: интеграция на мини-базе --------------------------------------------

_TOOLS_DDL = '''
    CREATE TABLE metadata_objects (
        id INTEGER PRIMARY KEY, uuid TEXT, object_type TEXT NOT NULL, name TEXT NOT NULL,
        synonym TEXT, comment TEXT, object_belonging TEXT, extended_configuration_object TEXT,
        object_kind TEXT NOT NULL DEFAULT 'ConfigObject'
    );
    CREATE TABLE modules (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_id INTEGER, command_id INTEGER,
        module_type TEXT, code TEXT
    );
    CREATE TABLE module_procedures (
        id INTEGER PRIMARY KEY, module_id INTEGER, name TEXT, proc_type TEXT,
        start_line INTEGER, end_line INTEGER
    );
    CREATE TABLE object_commands (id INTEGER PRIMARY KEY, object_id INTEGER, name TEXT, synonym TEXT);
    CREATE TABLE forms (
        id INTEGER PRIMARY KEY, object_id INTEGER, form_name TEXT, form_kind TEXT,
        uuid TEXT, properties_json TEXT
    );
    CREATE TABLE form_attributes (
        id INTEGER PRIMARY KEY, form_id INTEGER, name TEXT, title TEXT, is_main INTEGER DEFAULT 0
    );
    CREATE TABLE form_commands (
        id INTEGER PRIMARY KEY, form_id INTEGER, name TEXT, title TEXT, action TEXT,
        shortcut TEXT, representation TEXT
    );
    CREATE TABLE form_items (
        id INTEGER PRIMARY KEY, form_id INTEGER, parent_id INTEGER, name TEXT, item_type TEXT
    );
    CREATE TABLE form_entity_properties (
        id INTEGER PRIMARY KEY, entity_kind TEXT NOT NULL, entity_id INTEGER NOT NULL,
        property_path TEXT NOT NULL, property_name TEXT NOT NULL, ordinal INTEGER NOT NULL DEFAULT 0,
        value_text TEXT, value_type TEXT
    );
    CREATE VIRTUAL TABLE code_search USING fts5(code, content='modules', content_rowid='id');
'''

# Одно и то же слово в двух модулях разного типа — чтобы проверить, что фильтр сужает
# выдачу, не выключая FTS.
_CODE_OBJECT = 'Процедура ОбработкаПроведения()\n\tПровести();\nКонецПроцедуры'
_CODE_MANAGER = 'Функция Провести()\n\tВозврат Истина;\nКонецФункции'


def _setup_tools_db(conn, n_forms=5):
    conn.executescript(_TOOLS_DDL)
    conn.execute("INSERT INTO metadata_objects (id, object_type, name) VALUES (1, 'Document', 'Реализация')")
    conn.execute("INSERT INTO modules (id, object_id, module_type, code) VALUES (1, 1, 'ObjectModule', ?)",
                 (_CODE_OBJECT,))
    conn.execute("INSERT INTO modules (id, object_id, module_type, code) VALUES (2, 1, 'ManagerModule', ?)",
                 (_CODE_MANAGER,))
    for form_id in range(1, n_forms + 1):
        conn.execute("INSERT INTO forms (id, object_id, form_name) VALUES (?, 1, ?)",
                     (form_id, f'Форма{form_id}'))
        conn.execute("INSERT INTO form_items (form_id, name, item_type) VALUES (?, 'Поле', 'InputField')",
                     (form_id,))
    conn.execute("INSERT INTO code_search(code_search) VALUES ('rebuild')")


@pytest.fixture
def tools(tmp_path):
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(db_path)
    conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
    _setup_tools_db(conn)
    conn.commit()
    conn.close()
    t = build_configuration_tools(tmp_path, db_path)
    t._require_project_exists = lambda pf, dbs: None
    yield t
    t.close_all()


def _payload(result):
    return result['TestProject']['Main (base)']


def test_find_form_limits_and_reports_truncation(tools):
    payload = _payload(tools.find_form(project_filter='TestProject', limit=2))
    assert payload['total_count'] == 5
    assert payload['returned_count'] == 2
    assert payload['is_truncated'] is True
    assert len(payload['forms']) == 2


def test_find_form_without_truncation(tools):
    payload = _payload(tools.find_form(project_filter='TestProject', limit=100))
    assert payload['total_count'] == 5
    assert payload['is_truncated'] is False


def test_find_form_limit_zero_means_no_limit(tools):
    payload = _payload(tools.find_form(project_filter='TestProject', limit=0))
    assert payload['returned_count'] == 5
    assert payload['is_truncated'] is False


def test_find_form_total_counts_only_matching_forms(tools):
    payload = _payload(tools.find_form(form_name='Форма1', project_filter='TestProject'))
    assert payload['total_count'] == 1
    assert payload['is_truncated'] is False


def test_module_type_filter_narrows_without_disabling_fts(tools):
    """Раньше любой фильтр уводил поиск в LIKE по всему коду (232 мс против 1.7 мс)."""
    both = _payload(tools.search_code('Провести', project_filter='TestProject'))['matches']
    assert {m['module_type'] for m in both} == {'ObjectModule', 'ManagerModule'}

    only_manager = _payload(tools.search_code(
        'Провести', project_filter='TestProject', module_type='ManagerModule'))['matches']
    assert {m['module_type'] for m in only_manager} == {'ManagerModule'}


def test_object_name_filter_narrows_without_disabling_fts(tools):
    hits = _payload(tools.search_code(
        'Провести', project_filter='TestProject', object_name='Реализация'))['matches']
    assert hits
    assert all(m['object_name'] == 'Реализация' for m in hits)

    assert tools.search_code(
        'Провести', project_filter='TestProject', object_name='НетТакого').get('_empty')


def test_search_code_reports_truncation_flag(tools):
    payload = _payload(tools.search_code('Провести', project_filter='TestProject'))
    assert payload['is_truncated'] is False
    assert payload['returned_count'] == len(payload['matches'])


def test_search_code_survives_fts_syntax_in_query(tools):
    """Дефис в поисковой фразе — совершенно обычный запрос, а не повод для OperationalError."""
    for query in ('Провести-Документ', 'Провести AND', 'Провести:X', 'Провести()'):
        tools.search_code(query, project_filter='TestProject')  # не должно бросать
