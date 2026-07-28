"""Тесты _parse_modules: какие файлы Ext/*.bsl распознаются как модули объекта."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser


class TestParseModules(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'Configuration.xml').write_text('<x/>', encoding='utf-8')
        self.parser = ConfigurationParser(str(self.root / 'Configuration.xml'))
        self.addCleanup(self._tmp.cleanup)

    def _write_module(self, folder, obj_name, file_name, code):
        ext_dir = self.root / folder / obj_name / 'Ext'
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / file_name).write_text(code, encoding='utf-8')

    def test_record_set_module_of_register_is_parsed(self):
        """Регистр: код лежит в RecordSetModule, ObjectModule у регистров не бывает."""
        self._write_module(
            'InformationRegisters', 'ФТ_НазначениеОбъектовОперУчета',
            'RecordSetModule.bsl', 'Процедура ПередЗаписью(Отказ, Замещение)\nКонецПроцедуры\n',
        )
        modules = self.parser._parse_modules(
            'ФТ_НазначениеОбъектовОперУчета', 'InformationRegisters'
        )
        self.assertEqual([m['type'] for m in modules], ['RecordSetModule'])
        self.assertIn('ПередЗаписью', modules[0]['code'])

    def test_register_with_both_manager_and_record_set_modules(self):
        """Оба модуля регистра попадают в индекс, а не только ManagerModule."""
        self._write_module(
            'InformationRegisters', 'ФТ_СостоянияОбъектовОперУчета',
            'ManagerModule.bsl', '// менеджер\n',
        )
        self._write_module(
            'InformationRegisters', 'ФТ_СостоянияОбъектовОперУчета',
            'RecordSetModule.bsl', '// набор записей\n',
        )
        modules = self.parser._parse_modules(
            'ФТ_СостоянияОбъектовОперУчета', 'InformationRegisters'
        )
        self.assertEqual(
            sorted(m['type'] for m in modules), ['ManagerModule', 'RecordSetModule']
        )

    def test_bom_is_stripped(self):
        """Выгрузка Конфигуратора пишет BSL с BOM — он не должен попадать в код."""
        ext_dir = self.root / 'AccumulationRegisters' / 'ТД_Остатки' / 'Ext'
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / 'RecordSetModule.bsl').write_bytes(
            '﻿Процедура Тест()\nКонецПроцедуры\n'.encode('utf-8')
        )
        modules = self.parser._parse_modules('ТД_Остатки', 'AccumulationRegisters')
        self.assertTrue(modules[0]['code'].startswith('Процедура'))

    def test_value_manager_module_of_constant_is_parsed(self):
        """Константа: код живёт в ValueManagerModule, рядом может быть и ManagerModule."""
        self._write_module('Constants', 'НастройкиКолонтитулов', 'ValueManagerModule.bsl',
                           'Процедура ПередЗаписью(Отказ)\nКонецПроцедуры\n')
        self._write_module('Constants', 'НастройкиКолонтитулов', 'ManagerModule.bsl', '// менеджер\n')
        modules = self.parser._parse_modules('НастройкиКолонтитулов', 'Constants')
        self.assertEqual(
            sorted(m['type'] for m in modules), ['ManagerModule', 'ValueManagerModule']
        )

    def test_missing_ext_dir_returns_empty(self):
        self.assertEqual(self.parser._parse_modules('НетТакого', 'Catalogs'), [])

    def test_unknown_bsl_file_is_ignored(self):
        """Whitelist осознанный: посторонние .bsl рядом не индексируются."""
        self._write_module('Catalogs', 'Номенклатура', 'ObjectModule.bsl', '// объектный\n')
        self._write_module('Catalogs', 'Номенклатура', 'Черновик.bsl', '// мусор\n')
        modules = self.parser._parse_modules('Номенклатура', 'Catalogs')
        self.assertEqual([m['type'] for m in modules], ['ObjectModule'])


if __name__ == '__main__':
    unittest.main()
