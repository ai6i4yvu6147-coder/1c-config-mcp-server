"""Схема индекса: FK-индексы форм, форма FTS5 и статистика планировщика.

Проверяется не «индекс объявлен», а «планировщик его берёт на тех же формах запросов,
что стоят в server/tools/» — объявление само по себе ничего не гарантирует, а именно
эти пять индексов отсутствовали в схеме годами при живых соседях (аудит 2026-08, A-9).
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_tool.db_manager import DatabaseManager
from shared.indexer_version import INDEXER_VERSION

NS = ('xmlns="http://v8.1c.ru/8.3/MDClasses" '
      'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
      'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')


@pytest.fixture(scope='module')
def schema_conn(tmp_path_factory):
    """Пустая база со штатной схемой — для проверок DDL и планов запросов."""
    db_path = tmp_path_factory.mktemp('schema') / 'schema.db'
    manager = DatabaseManager(str(db_path))
    manager.connect()
    manager._create_schema()
    yield manager.conn
    manager.close()


def _plan(conn, sql, params=()):
    rows = conn.execute(f'EXPLAIN QUERY PLAN {sql}', params).fetchall()
    return ' | '.join(r['detail'] for r in rows)


# --- A-9: FK-индексы дочерних таблиц формы -------------------------------------------------

FORM_CHILD_QUERIES = [
    # формы запросов взяты из server/tools/ дословно по смыслу
    ('form_items', 'idx_form_items_form',
     'SELECT id FROM form_items WHERE form_id = 1'),
    ('form_attributes', 'idx_form_attributes_form',
     'SELECT id FROM form_attributes WHERE form_id = 1'),
    ('form_commands', 'idx_form_commands_form',
     'SELECT id FROM form_commands WHERE form_id = 1'),
    ('form_conditional_appearance', 'idx_form_conditional_appearance_form',
     'SELECT id FROM form_conditional_appearance WHERE form_id = 1'),
    ('modules', 'idx_modules_form',
     "SELECT id FROM modules WHERE form_id = 1 AND module_type = 'FormModule'"),
]


@pytest.mark.parametrize('table,index,sql', FORM_CHILD_QUERIES,
                         ids=[t for t, _, _ in FORM_CHILD_QUERIES])
def test_form_id_lookup_uses_an_index(schema_conn, table, index, sql):
    plan = _plan(schema_conn, sql)
    assert index in plan, f'{table}: полный скан вместо индекса — {plan}'
    assert f'SCAN {table}' not in plan, f'{table}: {plan}'


def test_find_form_child_counts_do_not_scan(schema_conn):
    """Три коррелированных COUNT из find_form — самый дорогой запрос проекта до A-9."""
    plan = _plan(schema_conn, '''
        SELECT f.id,
               (SELECT COUNT(*) FROM form_attributes WHERE form_id = f.id),
               (SELECT COUNT(*) FROM form_commands   WHERE form_id = f.id),
               (SELECT COUNT(*) FROM form_items      WHERE form_id = f.id)
        FROM forms f
    ''')
    for table in ('form_attributes', 'form_commands', 'form_items'):
        assert f'SCAN {table}' not in plan, f'{table} сканируется целиком: {plan}'


# --- A-10: композит metadata_type_slots ----------------------------------------------------

def test_type_slots_lookup_uses_composite_index(schema_conn):
    plan = _plan(
        schema_conn,
        "SELECT id FROM metadata_type_slots WHERE object_id = 1 AND source_table = 'attributes'",
    )
    assert 'ix_mts_object_source' in plan, plan


# --- A-6/A-7: форма FTS5 -------------------------------------------------------------------

def test_code_search_indexes_only_code(schema_conn):
    cols = [r[1] for r in schema_conn.execute('PRAGMA table_info(code_search)').fetchall()]
    assert cols == ['code'], f'служебные колонки снова в FTS: {cols}'


def _seed_module(conn, module_id, module_type, code):
    conn.execute(
        'INSERT INTO metadata_objects (id, object_type, name) VALUES (?, ?, ?)',
        (module_id, 'CommonModule', f'Модуль{module_id}'),
    )
    conn.execute(
        'INSERT INTO modules (id, object_id, module_type, code) VALUES (?, ?, ?, ?)',
        (module_id, module_id, module_type, code),
    )
    conn.execute('INSERT INTO code_search (rowid, code) VALUES (?, ?)', (module_id, code))


@pytest.fixture
def fts_conn(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'fts.db'))
    manager.connect()
    manager._create_schema()
    _seed_module(manager.conn, 1, 'FormModule', 'Процедура ПриОткрытии()\nКонецПроцедуры')
    _seed_module(manager.conn, 2, 'ObjectModule', 'Процедура ОбработкаПроведения()\nКонецПроцедуры')
    manager.conn.commit()
    yield manager.conn
    manager.close()


def test_module_type_value_is_not_matchable(fts_conn):
    """MATCH без имени колонки искал по служебным полям: 'FormModule' давал 11 880
    попаданий на ЕРП, из которых 0 содержали слово в коде — и они съедали лимит выдачи."""
    hits = fts_conn.execute(
        "SELECT rowid FROM code_search WHERE code_search MATCH 'FormModule'"
    ).fetchall()
    assert hits == []


def test_code_word_is_matchable(fts_conn):
    hits = fts_conn.execute(
        "SELECT rowid FROM code_search WHERE code_search MATCH 'ОбработкаПроведения'"
    ).fetchall()
    assert [h['rowid'] for h in hits] == [2]


def test_rebuild_and_snippet_work(fts_conn):
    """Контракт external content: колонки FTS обязаны существовать в modules.

    Прежняя схема объявляла object_name, которой в modules нет, — rebuild и snippet()
    падали с `no such column: T.object_name` (из-за чего рекомендация A-5 аудита
    2026-07 была неисполнима)."""
    fts_conn.execute("INSERT INTO code_search(code_search) VALUES ('rebuild')")
    fts_conn.execute("INSERT INTO code_search(code_search) VALUES ('integrity-check')")
    row = fts_conn.execute(
        "SELECT snippet(code_search, 0, '[', ']', '…', 8) AS s "
        "FROM code_search WHERE code_search MATCH 'ПриОткрытии'"
    ).fetchone()
    assert '[ПриОткрытии]' in row['s']


# --- A-8: ANALYZE в конце сборки -----------------------------------------------------------

def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _md(body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<MetaDataObject {NS} version="2.20">\n{body}\n</MetaDataObject>\n')


@pytest.fixture(scope='module')
def built_db(tmp_path_factory):
    """Минимальная реальная сборка — ANALYZE и user_version проверяются только на ней."""
    root = tmp_path_factory.mktemp('src')
    _write(root / 'Configuration.xml', _md(
        ' <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>Тест</Name></Properties>\n'
        '  <ChildObjects><CommonModule>МойМодуль</CommonModule></ChildObjects>\n'
        ' </Configuration>'
    ))
    _write(root / 'CommonModules' / 'МойМодуль.xml', _md(
        ' <CommonModule uuid="a0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>МойМодуль</Name></Properties>\n'
        ' </CommonModule>'
    ))
    _write(root / 'CommonModules' / 'МойМодуль' / 'Ext' / 'Module.bsl',
           'Процедура ПриЗаписи(Источник) Экспорт\nКонецПроцедуры\n')

    db_path = root / 'test.db'
    manager = DatabaseManager(str(db_path))
    manager.connect()
    manager.create_database(str(root / 'Configuration.xml'))
    manager.close()
    return db_path


def test_build_leaves_planner_statistics(built_db):
    conn = sqlite3.connect(built_db)
    try:
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'"
        ).fetchone(), 'ANALYZE после сборки не выполнялся — sqlite_stat1 нет'
        assert conn.execute('SELECT COUNT(*) FROM sqlite_stat1').fetchone()[0] > 0
    finally:
        conn.close()


def test_build_stamps_current_indexer_version(built_db):
    assert DatabaseManager.read_db_version(built_db) == INDEXER_VERSION
