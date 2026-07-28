"""Сквозная индексация подписок на события: дерево исходников → БД → инструменты.

Проверяется вся цепочка целиком, потому что ценность подписки размазана по трём местам:
строка в event_subscriptions, связь в metadata_relations (её читает find_referencing_objects)
и пометка процедуры-обработчика в module_procedures.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_tool.db_manager import DatabaseManager
from tests.conftest import build_configuration_tools

NS = ('xmlns="http://v8.1c.ru/8.3/MDClasses" '
      'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
      'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')


def _md(body):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject {NS} version="2.20">\n{body}\n</MetaDataObject>\n'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _build_source_tree(root):
    """Мини-конфигурация: документ, общий модуль с двумя процедурами и три подписки —
    на конкретный объект, на вид целиком и на неиндексируемый вид (журнал документов)."""
    _write(root / 'Configuration.xml', _md(
        ' <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>Тест</Name></Properties>\n'
        '  <ChildObjects>\n'
        '   <Document>Реализация</Document>\n'
        '   <CommonModule>МойМодуль</CommonModule>\n'
        '   <EventSubscription>ПриЗаписиРеализации</EventSubscription>\n'
        '   <EventSubscription>ПередЗаписьюВсехДокументов</EventSubscription>\n'
        '   <EventSubscription>ПоЖурналу</EventSubscription>\n'
        '  </ChildObjects>\n'
        ' </Configuration>'
    ))
    _write(root / 'Documents' / 'Реализация.xml', _md(
        ' <Document uuid="d0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>Реализация</Name></Properties>\n'
        ' </Document>'
    ))
    _write(root / 'CommonModules' / 'МойМодуль.xml', _md(
        ' <CommonModule uuid="a0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>МойМодуль</Name></Properties>\n'
        ' </CommonModule>'
    ))
    _write(root / 'CommonModules' / 'МойМодуль' / 'Ext' / 'Module.bsl',
           'Процедура ПриЗаписи(Источник, Отказ) Экспорт\nКонецПроцедуры\n'
           '\nПроцедура НикемНеВызывается() Экспорт\nКонецПроцедуры\n')

    def subscription(name, uuid, container, source, event, handler):
        _write(root / 'EventSubscriptions' / f'{name}.xml', _md(
            f' <EventSubscription uuid="{uuid}">\n'
            f'  <Properties><Name>{name}</Name>\n'
            f'   <Source><v8:{container}>{source}</v8:{container}></Source>\n'
            f'   <Event>{event}</Event>\n'
            f'   <Handler>{handler}</Handler>\n'
            f'  </Properties>\n'
            f' </EventSubscription>'
        ))

    subscription('ПриЗаписиРеализации', 'e0000000-0000-0000-0000-000000000001',
                 'Type', 'cfg:DocumentObject.Реализация', 'OnWrite',
                 'CommonModule.МойМодуль.ПриЗаписи')
    subscription('ПередЗаписьюВсехДокументов', 'e0000000-0000-0000-0000-000000000002',
                 'TypeSet', 'cfg:DocumentObject', 'BeforeWrite',
                 'CommonModule.МойМодуль.ПриЗаписи')
    subscription('ПоЖурналу', 'e0000000-0000-0000-0000-000000000003',
                 'Type', 'cfg:DocumentJournalManager.Продажи', 'OnWrite',
                 'CommonModule.МойМодуль.ПриЗаписи')


@pytest.fixture(scope='module')
def built_db(tmp_path_factory):
    root = tmp_path_factory.mktemp('src')
    _build_source_tree(root)
    db_path = root / 'test.db'
    manager = DatabaseManager(str(db_path))
    manager.connect()
    manager.create_database(str(root / 'Configuration.xml'))
    manager.close()
    return db_path


@pytest.fixture
def conn(built_db):
    connection = sqlite3.connect(built_db)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def test_subscriptions_indexed_as_objects(conn):
    rows = conn.execute(
        "SELECT name FROM metadata_objects WHERE object_type = 'EventSubscription' ORDER BY name"
    ).fetchall()
    assert [r['name'] for r in rows] == [
        'ПередЗаписьюВсехДокументов', 'ПоЖурналу', 'ПриЗаписиРеализации',
    ]


def test_handler_split_into_module_and_procedure(conn):
    row = conn.execute('''
        SELECT es.event, es.handler, es.handler_module, es.handler_procedure, es.source_kinds
        FROM event_subscriptions es JOIN metadata_objects o ON o.id = es.object_id
        WHERE o.name = 'ПриЗаписиРеализации'
    ''').fetchone()
    assert row['event'] == 'OnWrite'
    assert row['handler'] == 'CommonModule.МойМодуль.ПриЗаписи'
    assert row['handler_module'] == 'МойМодуль'
    assert row['handler_procedure'] == 'ПриЗаписи'
    assert row['source_kinds'] is None


def test_concrete_source_becomes_relation(conn):
    """Связь несёт и событие, и обработчик — обратный поиск отвечает «на что и чем»."""
    rows = conn.execute('''
        SELECT src.name AS src, dst.object_type AS dst_type, dst.name AS dst,
               mr.source_name, mr.source_detail
        FROM metadata_relations mr
        JOIN metadata_objects src ON src.id = mr.src_object_id
        JOIN metadata_objects dst ON dst.id = mr.dst_object_id
        WHERE mr.relation_kind = 'event_subscription'
    ''').fetchall()
    assert len(rows) == 1
    assert rows[0]['src'] == 'ПриЗаписиРеализации'
    assert (rows[0]['dst_type'], rows[0]['dst']) == ('Document', 'Реализация')
    assert rows[0]['source_name'] == 'OnWrite'
    assert rows[0]['source_detail'] == 'CommonModule.МойМодуль.ПриЗаписи'


def test_kind_wide_source_is_not_expanded(conn):
    """Подписка «на все документы» не разворачивается в связи (иначе — декартово
    произведение), но сам вид сохраняется строкой и виден агенту."""
    row = conn.execute('''
        SELECT es.source_kinds,
               (SELECT count(*) FROM metadata_relations mr WHERE mr.src_object_id = o.id) AS relations
        FROM event_subscriptions es JOIN metadata_objects o ON o.id = es.object_id
        WHERE o.name = 'ПередЗаписьюВсехДокументов'
    ''').fetchone()
    assert row['source_kinds'] == 'cfg:DocumentObject'
    assert row['relations'] == 0


def test_source_of_unindexed_kind_degrades_without_loss(conn):
    """Журналы документов не индексируются — связи нет, но подписка не теряется."""
    row = conn.execute('''
        SELECT es.handler,
               (SELECT count(*) FROM metadata_relations mr WHERE mr.src_object_id = o.id) AS relations
        FROM event_subscriptions es JOIN metadata_objects o ON o.id = es.object_id
        WHERE o.name = 'ПоЖурналу'
    ''').fetchone()
    assert row['handler'] == 'CommonModule.МойМодуль.ПриЗаписи'
    assert row['relations'] == 0


def test_handler_procedure_flagged(conn):
    rows = conn.execute(
        'SELECT name, used_in_event_subscription FROM module_procedures ORDER BY name'
    ).fetchall()
    flags = {r['name']: r['used_in_event_subscription'] for r in rows}
    assert flags == {'ПриЗаписи': 1, 'НикемНеВызывается': 0}


def test_get_object_structure_reports_event_and_sources(built_db, tmp_path):
    tools = build_configuration_tools(tmp_path, built_db)
    result = tools.get_object_structure('ПриЗаписиРеализации', project_filter='TestProject')
    structure = result['TestProject']['Main (base)']
    assert structure['type'] == 'EventSubscription'
    assert structure['event'] == 'OnWrite'
    assert structure['handler'] == 'CommonModule.МойМодуль.ПриЗаписи'
    assert structure['sources'] == [
        {'object_type': 'Document', 'name': 'Реализация', 'synonym': ''}
    ]
    # Своего кода у подписки нет — секции пустые, а не отсутствующие.
    assert structure['modules'] == [] and structure['forms'] == []


def test_find_referencing_objects_finds_subscription(built_db, tmp_path):
    """Главный сценарий: «что срабатывает при записи документа X»."""
    tools = build_configuration_tools(tmp_path, built_db)
    result = tools.find_referencing_objects(
        'Реализация', project_filter='TestProject', relation_kinds=['event_subscription'],
    )
    referencers = result['TestProject']['Main (base)']['referencers']
    assert len(referencers) == 1
    ref = referencers[0]
    assert ref['src_object']['type'] == 'EventSubscription'
    assert ref['src_object']['name'] == 'ПриЗаписиРеализации'
    assert ref['via'] == 'event_subscription'
    assert ref['source_name'] == 'OnWrite'


def test_sources_section_respects_cap(built_db, tmp_path):
    tools = build_configuration_tools(tmp_path, built_db)
    structure = tools.get_object_structure(
        'ПриЗаписиРеализации', project_filter='TestProject', sections=['modules'],
    )['TestProject']['Main (base)']
    assert 'sources' not in structure
