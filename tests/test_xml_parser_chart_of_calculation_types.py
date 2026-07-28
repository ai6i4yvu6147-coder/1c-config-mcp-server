"""Планы видов расчёта: индексируются как обычный объект, ссылки на них перестают висеть."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_tool.db_manager import DatabaseManager
from shared.metadata_type_resolver import REF_SUFFIX_TO_OBJECT_TYPE
from shared.xml_parser.core import CHILD_OBJECT_TYPES

NS = ('xmlns="http://v8.1c.ru/8.3/MDClasses" '
      'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
      'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')


def _md(body):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject {NS} version="2.20">\n{body}\n</MetaDataObject>\n'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


class TestChartOfCalculationTypesIndexing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _write(self.root / 'Configuration.xml', _md(
            ' <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
            '  <Properties><Name>Тест</Name></Properties>\n'
            '  <ChildObjects>\n'
            '   <ChartOfCalculationTypes>Начисления</ChartOfCalculationTypes>\n'
            '   <Document>Начисление</Document>\n'
            '  </ChildObjects>\n'
            ' </Configuration>'
        ))
        _write(self.root / 'ChartsOfCalculationTypes' / 'Начисления.xml', _md(
            ' <ChartOfCalculationTypes uuid="p0000000-0000-0000-0000-000000000001">\n'
            '  <Properties><Name>Начисления</Name></Properties>\n'
            '  <ChildObjects>\n'
            '   <Attribute uuid="a0000000-0000-0000-0000-000000000001">\n'
            '    <Properties><Name>Показатель</Name>\n'
            '     <Type><v8:Type>xs:string</v8:Type></Type>\n'
            '    </Properties>\n'
            '   </Attribute>\n'
            '  </ChildObjects>\n'
            ' </ChartOfCalculationTypes>'
        ))
        _write(self.root / 'ChartsOfCalculationTypes' / 'Начисления' / 'Ext' / 'ObjectModule.bsl',
               'Процедура ПередЗаписью(Отказ)\nКонецПроцедуры\n')
        # Документ с реквизитом, ссылающимся на план видов расчёта.
        _write(self.root / 'Documents' / 'Начисление.xml', _md(
            ' <Document uuid="d0000000-0000-0000-0000-000000000001">\n'
            '  <Properties><Name>Начисление</Name></Properties>\n'
            '  <ChildObjects>\n'
            '   <Attribute uuid="a0000000-0000-0000-0000-000000000002">\n'
            '    <Properties><Name>ВидРасчета</Name>\n'
            '     <Type><v8:Type>cfg:ChartOfCalculationTypesRef.Начисления</v8:Type></Type>\n'
            '    </Properties>\n'
            '   </Attribute>\n'
            '  </ChildObjects>\n'
            ' </Document>'
        ))

    def _build(self):
        db_path = self.root / 'test.db'
        manager = DatabaseManager(str(db_path))
        manager.connect()
        manager.create_database(str(self.root / 'Configuration.xml'))
        manager.close()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn

    def test_ref_suffix_map_and_object_types_agree(self):
        """Все виды из REF_SUFFIX_TO_OBJECT_TYPE должны индексироваться — иначе слоты типов,
        указывающие на них, молча теряются при резолве (так было с планами видов расчёта)."""
        missing = sorted(set(REF_SUFFIX_TO_OBJECT_TYPE.values()) - set(CHILD_OBJECT_TYPES))
        self.assertEqual(missing, [])

    def test_parsed_as_regular_object(self):
        parser_conn = self._build()
        row = parser_conn.execute(
            "SELECT id, name FROM metadata_objects WHERE object_type = 'ChartOfCalculationTypes'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['name'], 'Начисления')
        modules = parser_conn.execute(
            'SELECT module_type FROM modules WHERE object_id = ?', (row['id'],)
        ).fetchall()
        self.assertEqual([m['module_type'] for m in modules], ['ObjectModule'])
        attrs = parser_conn.execute(
            'SELECT name FROM attributes WHERE object_id = ?', (row['id'],)
        ).fetchall()
        self.assertEqual([a['name'] for a in attrs], ['Показатель'])

    def test_reference_to_chart_resolves(self):
        """Раньше `cfg:ChartOfCalculationTypesRef.X` резолвился в None и слот выбрасывался."""
        conn = self._build()
        rows = conn.execute('''
            SELECT src.name AS src_name, a.name AS attr_name
            FROM metadata_type_slots s
            JOIN metadata_objects tgt ON tgt.id = s.object_id
            JOIN metadata_objects src ON src.id = s.src_object_id
            JOIN attributes a ON a.id = s.source_row_id AND s.source_table = 'attributes'
            WHERE tgt.object_type = 'ChartOfCalculationTypes' AND tgt.name = 'Начисления'
        ''').fetchall()
        self.assertEqual([(r['src_name'], r['attr_name']) for r in rows],
                         [('Начисление', 'ВидРасчета')])


if __name__ == '__main__':
    unittest.main()
