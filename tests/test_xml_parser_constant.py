"""Тесты индексации констант: дескриптор, тип значения, модуль менеджера значения."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser

CONSTANT_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"
    xmlns:v8="http://v8.1c.ru/8.1/data/core"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" version="2.20">
\t<Constant uuid="24c7acaa-a5dd-410f-a4e7-ac4b8b06dad7">
\t\t<Properties>
\t\t\t<ObjectBelonging>Adopted</ObjectBelonging>
\t\t\t<Name>{name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item><v8:lang>ru</v8:lang><v8:content>{synonym}</v8:content></v8:item>
\t\t\t</Synonym>
\t\t\t<Comment>{comment}</Comment>
\t\t\t<Type>
{types}
\t\t\t</Type>
\t\t</Properties>
\t</Constant>
</MetaDataObject>
'''


class TestParseConstant(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'Configuration.xml').write_text('<x/>', encoding='utf-8')
        self.parser = ConfigurationParser(str(self.root / 'Configuration.xml'))
        self.addCleanup(self._tmp.cleanup)

    def _write_constant(self, name, types, synonym='', comment=''):
        body = '\n'.join(f'\t\t\t\t<v8:Type>{t}</v8:Type>' for t in types)
        (self.root / 'Constants').mkdir(exist_ok=True)
        (self.root / 'Constants' / f'{name}.xml').write_text(
            CONSTANT_XML.format(name=name, types=body, synonym=synonym, comment=comment),
            encoding='utf-8',
        )

    def _write_module(self, name, file_name, code):
        ext = self.root / 'Constants' / name / 'Ext'
        ext.mkdir(parents=True, exist_ok=True)
        (ext / file_name).write_text(code, encoding='utf-8')

    def test_primitive_constant(self):
        self._write_constant('ТД_ОтрицательныеОстаткиРазрешены', ['xs:boolean'],
                             synonym='Отрицательные остатки разрешены')
        obj = self.parser._parse_object(
            'ТД_ОтрицательныеОстаткиРазрешены', 'Constant', 'Constants'
        )
        self.assertIsNotNone(obj)
        self.assertEqual(obj['type'], 'Constant')
        self.assertEqual(obj['uuid'], '24c7acaa-a5dd-410f-a4e7-ac4b8b06dad7')
        self.assertEqual(obj['properties']['synonym'], 'Отрицательные остатки разрешены')
        self.assertEqual(obj['properties']['object_belonging'], 'Adopted')
        self.assertEqual(
            obj['type_slots'], [{'kind': 'primitive', 'raw': 'xs:boolean',
                                 'xs_type': 'xs:boolean', 'base_type': 'Boolean'}]
        )

    def test_value_manager_module_is_parsed(self):
        """Модуль менеджера значения — основной (и часто единственный) код константы."""
        self._write_constant('ФТ_ДатаНачалаВзвешиваний', ['xs:dateTime'])
        self._write_module('ФТ_ДатаНачалаВзвешиваний', 'ValueManagerModule.bsl',
                           'Процедура ПередЗаписью(Отказ)\nКонецПроцедуры\n')
        obj = self.parser._parse_object('ФТ_ДатаНачалаВзвешиваний', 'Constant', 'Constants')
        self.assertEqual([m['type'] for m in obj['modules']], ['ValueManagerModule'])
        self.assertIn('ПередЗаписью', obj['modules'][0]['code'])

    def test_both_manager_and_value_manager_modules(self):
        """У константы бывают оба модуля — менеджера и менеджера значения."""
        self._write_constant('НастройкиКолонтитулов', ['v8:ValueStorage'])
        self._write_module('НастройкиКолонтитулов', 'ManagerModule.bsl', '// менеджер\n')
        self._write_module('НастройкиКолонтитулов', 'ValueManagerModule.bsl', '// значение\n')
        obj = self.parser._parse_object('НастройкиКолонтитулов', 'Constant', 'Constants')
        self.assertEqual(
            sorted(m['type'] for m in obj['modules']),
            ['ManagerModule', 'ValueManagerModule'],
        )

    def test_reference_type_slot(self):
        """Ссылочный тип значения — источник связи константа → объект (metadata_type_slots)."""
        self._write_constant('ОсновнаяВалюта', ['cfg:CatalogRef.Валюты'])
        obj = self.parser._parse_object('ОсновнаяВалюта', 'Constant', 'Constants')
        self.assertEqual(obj['type_slots'], [{
            'kind': 'object_ref', 'raw': 'cfg:CatalogRef.Валюты',
            'ref_suffix': 'CatalogRef', 'ref_name': 'Валюты',
        }])

    def test_no_forms_and_no_commands(self):
        """У константы нет ни собственных форм, ни команд — секции пустые, а не отсутствуют."""
        self._write_constant('ТД_ДатаЗапрета', ['xs:dateTime'])
        obj = self.parser._parse_object('ТД_ДатаЗапрета', 'Constant', 'Constants')
        self.assertEqual(obj['forms'], [])
        self.assertEqual(obj['commands'], [])
        self.assertEqual(obj['tabular_sections'], [])

    def test_constant_listed_in_child_objects(self):
        """Константа доезжает до parse() через ChildObjects, а не только точечным вызовом."""
        self._write_constant('ТД_Флаг', ['xs:boolean'])
        (self.root / 'Configuration.xml').write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">\n'
            '  <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
            '    <Properties><Name>ТестКонфигурация</Name></Properties>\n'
            '    <ChildObjects><Constant>ТД_Флаг</Constant></ChildObjects>\n'
            '  </Configuration>\n'
            '</MetaDataObject>\n',
            encoding='utf-8',
        )
        parser = ConfigurationParser(str(self.root / 'Configuration.xml'))
        objects = parser.parse()['objects']
        self.assertEqual([(o['type'], o['name']) for o in objects], [('Constant', 'ТД_Флаг')])


if __name__ == '__main__':
    unittest.main()
