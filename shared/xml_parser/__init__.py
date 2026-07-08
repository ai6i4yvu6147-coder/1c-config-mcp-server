from .core import ConfigurationParserCore
from .types import TypeSlotsMixin
from .sections import SectionsMixin
from .flowchart import FlowchartMixin
from .modules import ModulesMixin
from .forms import FormsMixin
from .roles import RolesMixin
from .xml_helpers import XmlHelpersMixin, get_configuration_name, get_configuration_type


class ConfigurationParser(
    FormsMixin,
    ModulesMixin,
    FlowchartMixin,
    SectionsMixin,
    TypeSlotsMixin,
    RolesMixin,
    XmlHelpersMixin,
    ConfigurationParserCore,
):
    """Парсер XML-выгрузки конфигурации 1С"""


def test_parser(config_path):
    """Тестовая функция"""
    parser = ConfigurationParser(config_path)
    data = parser.parse()

    print(f"\nКонфигурация: {data['name']}")
    print(f"Объектов найдено: {len(data['objects'])}")

    for obj in data['objects'][:5]:
        print(f"  {obj['type']}: {obj['name']}")
        if obj['modules']:
            print(f"    Модулей: {len(obj['modules'])}")


__all__ = ['ConfigurationParser', 'get_configuration_name', 'get_configuration_type', 'test_parser']
