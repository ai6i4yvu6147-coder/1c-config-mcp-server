"""parser-streaming-pipeline: разбор идёт потоком и вставляется по одному объекту.

Проверяется двумя срезами:
1. поток отдаёт ровно то же и в том же порядке, что и `parse()` целиком;
2. сборка БД поверх потока сохраняет всё, что раньше делалось вторым проходом по готовому
   дереву, — `fo_form_usage` (ссылки на ФО с элементов форм), `fo_content_ref`, слоты типов
   форм и связи подсистем/подписок. Именно это откладывается до конца прохода, поэтому
   тесты целятся туда.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip('onec_metadata_schema')

from admin_tool.db_manager import DatabaseManager
from shared.xml_parser import ConfigurationParser

NS = ('xmlns="http://v8.1c.ru/8.3/MDClasses" '
      'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
      'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')
LF = 'http://v8.1c.ru/8.3/xcf/logform'


def _md(body):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject {NS} version="2.20">\n{body}\n</MetaDataObject>\n'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


_FORM_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="{LF}" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config">
  <Attributes>
    <Attribute name="Объект">
      <MainAttribute>true</MainAttribute>
    </Attribute>
  </Attributes>
  <ChildItems>
    <InputField name="Поле1" id="1">
      <DataPath>Объект.Реквизит1</DataPath>
      <FunctionalOptions>
        <Item>FunctionalOption.ИспользоватьСкидки</Item>
      </FunctionalOptions>
    </InputField>
  </ChildItems>
  <AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>
</Form>
"""


def _build_source_tree(root):
    """Мини-конфигурация со всем, что при потоковой вставке разъезжается по времени:
    ФО (используется на элементе формы и имеет Content), форма у справочника, подсистема
    с Content, подписка на событие, роль, общий модуль-обработчик."""
    _write(root / 'Configuration.xml', _md(
        ' <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>ТестПоток</Name></Properties>\n'
        '  <ChildObjects>\n'
        '   <Catalog>Номенклатура</Catalog>\n'
        '   <CommonModule>МойМодуль</CommonModule>\n'
        '   <FunctionalOption>ИспользоватьСкидки</FunctionalOption>\n'
        '   <EventSubscription>ПриЗаписиНоменклатуры</EventSubscription>\n'
        '  </ChildObjects>\n'
        ' </Configuration>'
    ))

    _write(root / 'Catalogs' / 'Номенклатура.xml', _md(
        ' <Catalog uuid="d0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>Номенклатура</Name></Properties>\n'
        ' </Catalog>'
    ))
    _write(root / 'Catalogs' / 'Номенклатура' / 'Ext' / 'ManagerModule.bsl',
           'Функция ЕстьСкидка() Экспорт\n\tВозврат Истина;\nКонецФункции\n')
    _write(root / 'Catalogs' / 'Номенклатура' / 'Forms' / 'ФормаЭлемента' / 'Ext' / 'Form.xml',
           _FORM_XML)
    _write(root / 'Catalogs' / 'Номенклатура' / 'Forms' / 'ФормаЭлемента' / 'Ext' / 'Form' / 'Module.bsl',
           '&НаСервере\nПроцедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)\nКонецПроцедуры\n')

    _write(root / 'CommonModules' / 'МойМодуль.xml', _md(
        ' <CommonModule uuid="a0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>МойМодуль</Name></Properties>\n'
        ' </CommonModule>'
    ))
    _write(root / 'CommonModules' / 'МойМодуль' / 'Ext' / 'Module.bsl',
           'Процедура ПриЗаписи(Источник, Отказ) Экспорт\nКонецПроцедуры\n')

    _write(root / 'FunctionalOptions' / 'ИспользоватьСкидки.xml', _md(
        ' <FunctionalOption uuid="f0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>ИспользоватьСкидки</Name>\n'
        '   <Content><xr:Object xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">'
        'Catalog.Номенклатура</xr:Object></Content>\n'
        '  </Properties>\n'
        ' </FunctionalOption>'
    ))

    _write(root / 'EventSubscriptions' / 'ПриЗаписиНоменклатуры.xml', _md(
        ' <EventSubscription uuid="e0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>ПриЗаписиНоменклатуры</Name>\n'
        '   <Source><v8:Type>cfg:CatalogObject.Номенклатура</v8:Type></Source>\n'
        '   <Event>OnWrite</Event>\n'
        '   <Handler>CommonModule.МойМодуль.ПриЗаписи</Handler>\n'
        '  </Properties>\n'
        ' </EventSubscription>'
    ))

    _write(root / 'Subsystems' / 'Продажи.xml', _md(
        ' <Subsystem uuid="50000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>Продажи</Name>\n'
        '   <Content><xr:Item xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">'
        'Catalog.Номенклатура</xr:Item></Content>\n'
        '  </Properties>\n'
        ' </Subsystem>'
    ))

    _write(root / 'Roles' / 'ПолныеПрава.xml', _md(
        ' <Role uuid="b0000000-0000-0000-0000-000000000001">\n'
        '  <Properties><Name>ПолныеПрава</Name></Properties>\n'
        ' </Role>'
    ))

    return root / 'Configuration.xml'


@pytest.fixture(scope='module')
def source_tree(tmp_path_factory):
    return _build_source_tree(tmp_path_factory.mktemp('streaming-src'))


@pytest.fixture(scope='module')
def streamed_db(source_tree, tmp_path_factory):
    path = tmp_path_factory.mktemp('streaming-db') / 'streamed.db'
    DatabaseManager.build_from_xml_atomic(path, str(source_tree))
    return path


@pytest.fixture
def conn(streamed_db):
    connection = sqlite3.connect(str(streamed_db))
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


class TestStreamContract:
    def test_stream_matches_full_parse(self, source_tree):
        """Поток отдаёт те же объекты в том же порядке, что и `parse()` целиком."""
        full = ConfigurationParser(str(source_tree), use_process_pool=False).parse()

        parser = ConfigurationParser(str(source_tree), use_process_pool=False)
        header, objects = parser.parse_streaming()
        streamed = list(objects)

        assert header['name'] == full['name'] == 'ТестПоток'
        assert header['extension_purpose'] == full['extension_purpose']
        assert streamed == full['objects']
        assert [o['name'] for o in streamed] == [
            'Номенклатура', 'МойМодуль', 'ИспользоватьСкидки',
            'ПриЗаписиНоменклатуры', 'Продажи', 'ПолныеПрава',
        ]

    def test_pool_path_streams_the_same(self, source_tree):
        """Окно пула форм не меняет ни состав, ни порядок выдачи."""
        seq = list(ConfigurationParser(str(source_tree), use_process_pool=False).parse_streaming()[1])

        parser = ConfigurationParser(str(source_tree), use_process_pool=True)
        pooled = list(parser.parse_streaming()[1])

        assert pooled == seq
        assert parser._form_pool is None  # генератор вычерпан → пул закрыт в finally

    def test_expected_object_count_matches_stream(self, source_tree):
        header, objects = ConfigurationParser(str(source_tree), use_process_pool=False).parse_streaming()
        assert header['expected_object_count'] == len(list(objects))

    def test_closing_a_partially_consumed_stream_shuts_the_pool_down(self, source_tree):
        """Потребитель может бросить поток на середине (ошибка вставки) — пул обязан закрыться."""
        parser = ConfigurationParser(str(source_tree), use_process_pool=True)
        _header, objects = parser.parse_streaming()

        first = next(objects)
        assert first['name'] == 'Номенклатура'
        assert parser._form_pool is not None

        objects.close()
        assert parser._form_pool is None


class TestStreamingBuild:
    """Сборка БД поверх потока: то, что раньше делалось вторым проходом, на месте."""

    def test_objects_and_forms_inserted(self, conn):
        names = {r['name'] for r in conn.execute(
            "SELECT name FROM metadata_objects WHERE object_kind = 'ConfigObject'")}
        assert {'Номенклатура', 'МойМодуль', 'ИспользоватьСкидки',
                'ПриЗаписиНоменклатуры', 'Продажи', 'ПолныеПрава'} <= names

        form = conn.execute('''
            SELECT f.form_name, o.name AS owner
            FROM forms f JOIN metadata_objects o ON o.id = f.object_id
        ''').fetchone()
        assert (form['form_name'], form['owner']) == ('ФормаЭлемента', 'Номенклатура')

    def test_form_module_is_linked_to_its_form(self, conn):
        """Модуль формы вставляется в том же шаге, что и объект, — form_id обязан указывать
        на форму этого объекта, а не «съехать» на соседний."""
        row = conn.execute('''
            SELECT m.module_type, f.form_name, o.name AS owner
            FROM modules m
            JOIN forms f ON f.id = m.form_id
            JOIN metadata_objects o ON o.id = m.object_id
            WHERE m.module_type = 'FormModule'
        ''').fetchone()
        assert (row['module_type'], row['form_name'], row['owner']) == (
            'FormModule', 'ФормаЭлемента', 'Номенклатура')

    def test_deferred_fo_form_usage_resolved(self, conn):
        """Ссылка на ФО стоит на элементе формы справочника, а сама ФО вставляется позже —
        разрешение отложено до конца прохода."""
        row = conn.execute('''
            SELECT fo.name AS fo_name, u.element_type, u.element_name,
                   owner.name AS owner, f.form_name
            FROM fo_form_usage u
            JOIN metadata_objects fo ON fo.id = u.functional_option_id
            JOIN metadata_objects owner ON owner.id = u.owner_object_id
            JOIN forms f ON f.id = u.form_id
        ''').fetchall()
        assert len(row) == 1
        assert (row[0]['fo_name'], row[0]['element_type'], row[0]['element_name'],
                row[0]['owner'], row[0]['form_name']) == (
            'ИспользоватьСкидки', 'FormItem', 'Поле1', 'Номенклатура', 'ФормаЭлемента')

    def test_fo_content_ref_resolved(self, conn):
        row = conn.execute('''
            SELECT fo.name AS fo_name, target.name AS target, r.content_ref_type
            FROM fo_content_ref r
            JOIN metadata_objects fo ON fo.id = r.functional_option_id
            JOIN metadata_objects target ON target.id = r.metadata_object_id
        ''').fetchone()
        assert (row['fo_name'], row['target'], row['content_ref_type']) == (
            'ИспользоватьСкидки', 'Номенклатура', 'Object')

    def test_subsystem_and_event_subscription_relations(self, conn):
        rows = {
            (r['kind'], r['src'], r['dst'])
            for r in conn.execute('''
                SELECT rel.relation_kind AS kind, s.name AS src, d.name AS dst
                FROM metadata_relations rel
                JOIN metadata_objects s ON s.id = rel.src_object_id
                JOIN metadata_objects d ON d.id = rel.dst_object_id
            ''')
        }
        assert ('subsystem_member', 'Продажи', 'Номенклатура') in rows
        assert ('event_subscription', 'ПриЗаписиНоменклатуры', 'Номенклатура') in rows

    def test_handler_procedure_marked(self, conn):
        row = conn.execute('''
            SELECT p.name, p.used_in_event_subscription
            FROM module_procedures p WHERE p.name = 'ПриЗаписи'
        ''').fetchone()
        assert row['used_in_event_subscription'] == 1

    def test_index_metadata_written(self, conn):
        meta = {r['key']: r['value'] for r in conn.execute('SELECT key, value FROM index_metadata')}
        assert meta['config_name'] == 'ТестПоток'
        assert meta['source_db_name'] == 'ТестПоток'


if __name__ == '__main__':
    pytest.main([__file__])
