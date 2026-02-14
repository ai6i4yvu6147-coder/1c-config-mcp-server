# -*- coding: utf-8 -*-
"""Тест парсера на XML выгрузки расширения (формат 2.20)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.xml_parser import ConfigurationParser

def main():
    path = Path(r"C:\Users\Alex\Documents\Работа\Общая\Выгрузка конф\Расш бюдж\Catalogs\ФТ_СтруктураБДР.xml")
    if not path.exists():
        print("File not found:", path)
        return 1
    parser = ConfigurationParser(path)
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()
    md_ns = "http://v8.1c.ru/8.3/MDClasses"
    obj_elem = parser._get_object_element(root, "Catalog", md_ns)
    print("obj_elem:", obj_elem.tag if obj_elem is not None else None)
    attrs = parser._parse_custom_attributes(root, "Catalog")
    print("custom_attributes:", len(attrs))
    for a in attrs[:5]:
        print("  ", a["name"], "-", a["type"])
    ts = parser._parse_tabular_sections(root, "Catalog")
    print("tabular_sections:", len(ts))
    for t in ts:
        print("  ", t["name"], "-", len(t["columns"]), "columns")
    return 0

if __name__ == "__main__":
    sys.exit(main())
