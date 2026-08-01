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


class TestDeclarationLineTail(unittest.TestCase):
    """Хвост строки объявления: 1С допускает и //-комментарий, и `;` после сигнатуры.

    Раньше шаблон требовал `$` сразу после `)`/`Экспорт`, и такая процедура выпадала
    из индекса целиком — её не брал ни основной шаблон, ни фолбэк многострочной
    сигнатуры (он отсеивал строку по наличию `)`). Примеры — из общих модулей ЕРП.
    """

    def test_trailing_comment_after_export(self):
        code = """Функция ПолучитьТаймаут(Знач Секунды = 3600) Экспорт // 1 час по умолчанию
	Возврат Секунды;
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ПолучитьТаймаут'])
        self.assertEqual(procs[0]['params'], 'Знач Секунды = 3600')
        self.assertEqual(procs[0]['is_export'], 1)
        self.assertEqual(procs[0]['end_line'], 3)

    def test_trailing_comment_without_export(self):
        code = """Функция ЭтоРабочийДень() // берётся из производственного календаря
	Возврат Истина;
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ЭтоРабочийДень'])
        self.assertEqual(procs[0]['params'], '(без параметров)')
        self.assertEqual(procs[0]['is_export'], 0)

    def test_trailing_comment_containing_parenthesis(self):
        """Непарная `)` в комментарии не должна путать разбор параметров."""
        code = """Функция ПолучитьНазначение(Сертификат) // "2.5.29.37"
	Возврат Неопределено;
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ПолучитьНазначение'])
        self.assertEqual(procs[0]['params'], 'Сертификат')

    def test_trailing_semicolon(self):
        code = """Процедура ЗаполнитьРеквизитыСвойств(ПараметрыСообщения, Предмет);
	Предмет = Неопределено;
КонецПроцедуры
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ЗаполнитьРеквизитыСвойств'])
        self.assertEqual(procs[0]['params'], 'ПараметрыСообщения, Предмет')
        self.assertEqual(procs[0]['end_line'], 3)

    def test_trailing_semicolon_and_comment_together(self):
        code = """Функция ФорматДействует(СведенияОФормате, ТекущаяДата); // УТ:581
	Возврат Истина;
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ФорматДействует'])
        self.assertEqual(procs[0]['params'], 'СведенияОФормате, ТекущаяДата')

    def test_doc_comment_above_declaration_with_trailing_tail_still_collected(self):
        code = """// Возвращает таймаут ожидания.
&НаСервере
Функция ПолучитьТаймаут(Секунды) Экспорт // 1 час
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual(procs[0]['start_line'], 1)
        self.assertEqual(procs[0]['comment'], 'Возвращает таймаут ожидания.')
        self.assertEqual(procs[0]['execution_context'], 'НаСервере')


class TestGluedEndKeyword(unittest.TestCase):
    """`КонецПроцедуры`, приклеенный к предыдущему оператору (34 места в ЕРП).

    Цена пропущенной границы двойная: предыдущая процедура получала end_line
    следующей (get_procedure_code склеивал две), а следующая терялась целиком.
    """

    def test_end_glued_after_semicolon(self):
        code = """&НаКлиенте
Процедура ГодНазад(Команда)
	Пока Выборка.Следующий() Цикл
		Период = Выборка.Ссылка;
	КонецЦикла;	КонецПроцедуры

&НаСервереБезКонтекста
Функция СписокНоменклатуры(Категория)
	Возврат Неопределено;КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['ГодНазад', 'СписокНоменклатуры'])
        self.assertEqual(procs[0]['end_line'], 5)
        self.assertEqual(procs[1]['start_line'], 7)
        self.assertEqual(procs[1]['end_line'], 9)

    def test_end_keyword_inside_string_literal_is_not_a_boundary(self):
        code = """Процедура Foo()
	Текст = "КонецПроцедуры";
	Ещё = "А; КонецПроцедуры";
КонецПроцедуры
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['Foo'])
        self.assertEqual(procs[0]['end_line'], 4)


class TestMultilineSignature(unittest.TestCase):
    def test_plain_multiline_signature(self):
        code = """Процедура Обработать(Первый,
		Второй) Экспорт
КонецПроцедуры
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['Обработать'])
        self.assertEqual(procs[0]['params'], '(многострочные)')
        self.assertEqual(procs[0]['is_export'], 1)
        self.assertEqual(procs[0]['end_line'], 3)

    def test_first_line_closes_parens_of_a_default_value(self):
        """Фолбэк идёт по балансу скобок, а не по «есть ли в строке )».

        При проверке `')' not in line` объявление с `Новый Массив()` в значении по
        умолчанию не подхватывал ни один из шаблонов.
        """
        code = """Процедура Собрать(Список = Новый Массив(),
		Прочее) Экспорт
КонецПроцедуры
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['Собрать'])
        self.assertEqual(procs[0]['is_export'], 1)
        self.assertEqual(procs[0]['end_line'], 3)

    def test_unbalanced_parenthesis_in_continuation_comment(self):
        """Скобки в //-комментарии не участвуют в балансе."""
        code = """Функция Посчитать(Первый,
		Второй, // откуда (см. описание выше
		Третий)
	Возврат 0;
КонецФункции
"""
        procs = _parse_module_procedures(code)
        self.assertEqual([p['name'] for p in procs], ['Посчитать'])
        self.assertEqual(procs[0]['end_line'], 5)


if __name__ == '__main__':
    unittest.main()
