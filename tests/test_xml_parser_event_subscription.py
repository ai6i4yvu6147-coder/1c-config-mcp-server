"""Тесты подписок на события: разбор дескриптора и нормализация Source."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.metadata_type_resolver import parse_event_source_string
from shared.xml_parser import ConfigurationParser

SUBSCRIPTION_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"
    xmlns:v8="http://v8.1c.ru/8.1/data/core"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" version="2.20">
\t<EventSubscription uuid="7f4268f7-17ca-4e5d-8b1e-70260957baf2">
\t\t<Properties>
\t\t\t<Name>{name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item><v8:lang>ru</v8:lang><v8:content>{synonym}</v8:content></v8:item>
\t\t\t</Synonym>
\t\t\t<Comment/>
\t\t\t<Source>
{source}
\t\t\t</Source>
\t\t\t<Event>{event}</Event>
\t\t\t<Handler>{handler}</Handler>
\t\t</Properties>
\t</EventSubscription>
</MetaDataObject>
'''


class TestParseEventSourceString(unittest.TestCase):
    """Разбор строки Source — суффикс «лица» объекта срезается, важен сам объект."""

    def test_concrete_object(self):
        self.assertEqual(
            parse_event_source_string('cfg:DocumentObject.РеализацияТоваров'),
            {'kind': 'object_ref', 'raw': 'cfg:DocumentObject.РеализацияТоваров',
             'object_type': 'Document', 'ref_name': 'РеализацияТоваров'},
        )

    def test_kind_wide(self):
        parsed = parse_event_source_string('cfg:DocumentObject')
        self.assertEqual(parsed['kind'], 'kind_wide')
        self.assertEqual(parsed['object_type'], 'Document')
        self.assertIsNone(parsed['ref_name'])

    def test_all_faces_of_same_object_collapse_to_one_type(self):
        for raw, expected in (
            ('cfg:CatalogObject.Валюты', 'Catalog'),
            ('cfg:CatalogManager.Валюты', 'Catalog'),
            ('cfg:InformationRegisterRecordSet.КурсыВалют', 'InformationRegister'),
            ('cfg:ConstantValueManager.ОсновнаяВалюта', 'Constant'),
            ('cfg:ChartOfCalculationTypesObject.Начисления', 'ChartOfCalculationTypes'),
            ('cfg:AccumulationRegisterRecordSet.Остатки', 'AccumulationRegister'),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse_event_source_string(raw)['object_type'], expected)

    def test_constant_value_manager_not_split_as_manager(self):
        """ValueManager срезается раньше Manager — иначе получился бы вид 'ConstantValue'."""
        self.assertEqual(
            parse_event_source_string('cfg:ConstantValueManager.X')['object_type'], 'Constant'
        )

    def test_defined_type_source(self):
        parsed = parse_event_source_string('cfg:DefinedType.ВладелецФайла')
        self.assertEqual(parsed['object_type'], 'DefinedType')
        self.assertEqual(parsed['ref_name'], 'ВладелецФайла')

    def test_unknown_kind_keeps_raw(self):
        """Нераспознанный вид не роняет разбор — строка остаётся доступной в raw."""
        parsed = parse_event_source_string('cfg:ЧтоТоНовоеObject.Имя')
        self.assertIsNone(parsed['object_type'])
        self.assertEqual(parsed['raw'], 'cfg:ЧтоТоНовоеObject.Имя')

    def test_empty(self):
        self.assertEqual(parse_event_source_string('')['kind'], 'unknown')


class TestParseEventSubscription(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'Configuration.xml').write_text('<x/>', encoding='utf-8')
        self.parser = ConfigurationParser(str(self.root / 'Configuration.xml'))
        self.addCleanup(self._tmp.cleanup)

    def _write(self, name, source, event='BeforeWrite',
               handler='CommonModule.МойМодуль.МояПроцедура', synonym=''):
        (self.root / 'EventSubscriptions').mkdir(exist_ok=True)
        (self.root / 'EventSubscriptions' / f'{name}.xml').write_text(
            SUBSCRIPTION_XML.format(name=name, source=source, event=event,
                                    handler=handler, synonym=synonym),
            encoding='utf-8',
        )

    def test_single_concrete_source(self):
        self._write('ПередЗаписьюРеализации',
                    '\t\t\t\t<v8:Type>cfg:DocumentObject.РеализацияТоваров</v8:Type>')
        obj = self.parser._parse_object(
            'ПередЗаписьюРеализации', 'EventSubscription', 'EventSubscriptions'
        )
        p = obj['properties']
        self.assertEqual(p['event'], 'BeforeWrite')
        self.assertEqual(p['handler'], 'CommonModule.МойМодуль.МояПроцедура')
        self.assertEqual(
            p['sources'],
            [{'raw': 'cfg:DocumentObject.РеализацияТоваров', 'is_type_set': False}],
        )

    def test_no_own_code(self):
        """У подписки нет ни модулей, ни форм, ни команд — обработчик в общем модуле."""
        self._write('Пустая', '\t\t\t\t<v8:Type>cfg:CatalogObject.Валюты</v8:Type>')
        obj = self.parser._parse_object('Пустая', 'EventSubscription', 'EventSubscriptions')
        self.assertEqual(obj['modules'], [])
        self.assertEqual(obj['forms'], [])
        self.assertEqual(obj['commands'], [])

    def test_type_set_marked(self):
        self._write('НаВсеДокументы', '\t\t\t\t<v8:TypeSet>cfg:DocumentObject</v8:TypeSet>')
        obj = self.parser._parse_object('НаВсеДокументы', 'EventSubscription', 'EventSubscriptions')
        self.assertEqual(
            obj['properties']['sources'],
            [{'raw': 'cfg:DocumentObject', 'is_type_set': True}],
        )

    def test_multiple_sources_and_both_containers(self):
        """Type и TypeSet могут стоять рядом, значение каждого — список."""
        self._write('Смешанная',
                    '\t\t\t\t<v8:Type>cfg:CatalogObject.Валюты</v8:Type>\n'
                    '\t\t\t\t<v8:Type>cfg:CatalogObject.Организации</v8:Type>\n'
                    '\t\t\t\t<v8:TypeSet>cfg:DocumentObject</v8:TypeSet>')
        sources = self.parser._parse_object(
            'Смешанная', 'EventSubscription', 'EventSubscriptions'
        )['properties']['sources']
        self.assertEqual(
            sources,
            [
                {'raw': 'cfg:CatalogObject.Валюты', 'is_type_set': False},
                {'raw': 'cfg:CatalogObject.Организации', 'is_type_set': False},
                {'raw': 'cfg:DocumentObject', 'is_type_set': True},
            ],
        )

    def test_empty_source_container(self):
        """Подписка без источников не роняет разбор — sources пустой список."""
        self._write('БезИсточника', '')
        obj = self.parser._parse_object('БезИсточника', 'EventSubscription', 'EventSubscriptions')
        self.assertEqual(obj['properties']['sources'], [])

    def test_reaches_parse_via_child_objects(self):
        self._write('ТД_Подписка', '\t\t\t\t<v8:Type>cfg:CatalogObject.Валюты</v8:Type>')
        (self.root / 'Configuration.xml').write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">\n'
            '  <Configuration uuid="c0000000-0000-0000-0000-000000000001">\n'
            '    <Properties><Name>ТестКонфигурация</Name></Properties>\n'
            '    <ChildObjects><EventSubscription>ТД_Подписка</EventSubscription></ChildObjects>\n'
            '  </Configuration>\n'
            '</MetaDataObject>\n',
            encoding='utf-8',
        )
        parser = ConfigurationParser(str(self.root / 'Configuration.xml'))
        objects = parser.parse()['objects']
        self.assertEqual(
            [(o['type'], o['name']) for o in objects], [('EventSubscription', 'ТД_Подписка')]
        )


if __name__ == '__main__':
    unittest.main()
