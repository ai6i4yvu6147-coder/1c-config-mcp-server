from pathlib import Path
import xml.etree.ElementTree as ET


def _local_tag(tag):
    """Локальное имя тега без namespace (для сравнения)."""
    if not tag:
        return ''
    return tag.split('}')[-1] if '}' in tag else tag


class XmlHelpersMixin:
    """Generic namespace-aware extraction helpers shared across parsing domains."""

    def _extract_synonym(self, elem):
        """Извлекает синоним атрибута"""
        v8_ns = 'http://v8.1c.ru/8.1/data/core'
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        # Ищем в v8:content с учетом namespace
        synonym_elem = elem.find(f'.//{{{v8_ns}}}content')
        if synonym_elem is not None and synonym_elem.text:
            return synonym_elem.text

        # Ищем в Synonym с учетом namespace
        syn_elem = elem.find(f'.//{{{md_ns}}}Synonym')
        if syn_elem is not None:
            syn_content = syn_elem.find(f'.//{{{v8_ns}}}content')
            if syn_content is not None and syn_content.text:
                return syn_content.text

        return ''

    def _extract_comment(self, elem):
        """Извлекает комментарий атрибута/табличной части/значения перечисления из Properties/Comment."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        props = elem.find(f'{{{md_ns}}}Properties')
        if props is None:
            return ''
        comment_elem = props.find(f'{{{md_ns}}}Comment')
        if comment_elem is None:
            comment_elem = props.find('Comment')
        if comment_elem is not None and comment_elem.text:
            return comment_elem.text
        return ''


def get_configuration_name(config_path):
    """
    Возвращает имя конфигурации из Configuration.xml (без полного парсинга).
    Используется для подстановки имени базы в GUI при выборе выгрузки.
    """
    path = Path(config_path)
    if not path.exists() or path.suffix.lower() != '.xml':
        return ''
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        config = root.find(f'{{{md_ns}}}Configuration')
        if config is None:
            config = root.find('.//{http://v8.1c.ru/8.3/MDClasses}Configuration')
        if config is None:
            return ''
        properties = config.find(f'{{{md_ns}}}Properties')
        if properties is None:
            properties = config.find(f'.//{{{md_ns}}}Properties')
        if properties is None:
            return ''
        for child in properties:
            if _local_tag(child.tag) in ('Name', 'n') and child.text:
                return child.text.strip()
    except (ET.ParseError, OSError):
        pass
    return ''


def get_configuration_type(config_path):
    """
    Возвращает тип конфигурации: 'extension' или 'base'.
    Расширение определяется по наличию ConfigurationExtensionPurpose в Configuration.xml.
    """
    path = Path(config_path)
    if not path.exists() or path.suffix.lower() != '.xml':
        return 'base'
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)
        if config is None:
            return 'base'
        properties = config.find('md:Properties', ns)
        if properties is None:
            return 'base'
        purpose_elem = properties.find('md:ConfigurationExtensionPurpose', ns)
        if purpose_elem is not None and purpose_elem.text and purpose_elem.text.strip():
            return 'extension'
    except (ET.ParseError, OSError):
        pass
    return 'base'
