"""Tests for BSL module procedure boundary parsing."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_tool.db_manager.bsl import _parse_module_procedures


class TestParseModuleProcedures(unittest.TestCase):
    def test_end_function_with_trailing_name_comment(self):
        code = """Функция ИнициализироватьТаблицуОперандов(ЧислоДопАналитик) Экспорт
	Возврат мЗначенияОперандов;

КонецФункции // ИнициализироватьТаблицуОперандов()

Функция ИнициализироватьТаблицуПротокола() Экспорт

	ТаблицаПротокола=Новый ТаблицаЗначений;
	ТаблицаПротокола.Колонки.Добавить("Колонка");
	Возврат ТаблицаПротокола;

КонецФункции // ИнициализироватьТаблицуПротокола()
"""
        procs = _parse_module_procedures(code)
        names = [p['name'] for p in procs]
        self.assertEqual(names, ['ИнициализироватьТаблицуОперандов', 'ИнициализироватьТаблицуПротокола'])

        first, second = procs
        self.assertEqual(first['end_line'], 4)
        self.assertEqual(second['start_line'], 6)
        self.assertEqual(second['end_line'], 12)

    def test_bare_end_function_still_works(self):
        code = """Процедура Foo() Экспорт
КонецПроцедуры

Функция Bar()
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['Foo', 'Bar'])
        self.assertEqual(procs[0]['end_line'], 2)
        self.assertEqual(procs[1]['end_line'], 5)


if __name__ == '__main__':
    unittest.main()
