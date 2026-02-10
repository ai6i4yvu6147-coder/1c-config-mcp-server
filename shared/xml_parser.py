import xml.etree.ElementTree as ET
import os
from pathlib import Path

class ConfigurationParser:
    """Парсер XML-выгрузки конфигурации 1С"""
    
    def __init__(self, config_path):
        """
        Args:
            config_path: Путь к файлу Configuration.xml
        """
        self.config_path = Path(config_path)
        self.root_dir = self.config_path.parent
        
    def parse(self):
        """Парсит конфигурацию и возвращает структуру данных"""
        tree = ET.parse(self.config_path)
        root = tree.getroot()
        
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
        config = root.find('md:Configuration', ns)
        
        if config is None:
            return {'name': '', 'objects': []}
        
        properties = config.find('md:Properties', ns)
        config_name = ''
        if properties is not None:
            name_elem = properties.find('md:n', ns)
            if name_elem is not None:
                config_name = name_elem.text
        
        objects = self._parse_child_objects(config, ns)
        
        return {
            'name': config_name,
            'objects': objects
        }

    def _parse_child_objects(self, config, ns):
        """Извлекает список дочерних объектов"""
        objects = []
        child_objects = config.find('md:ChildObjects', ns)
        
        if child_objects is None:
            return objects
        
        object_types = {
            'Catalog': 'Catalogs',
            'Document': 'Documents',
            'CommonModule': 'CommonModules',
            'InformationRegister': 'InformationRegisters',
            'AccumulationRegister': 'AccumulationRegisters',
            'Report': 'Reports',
            'DataProcessor': 'DataProcessors',
            'Enum': 'Enums',
            'BusinessProcess': 'BusinessProcesses',
            'Task': 'Tasks',
        }
        
        for obj_type, folder_name in object_types.items():
            for element in child_objects.findall(f'md:{obj_type}', ns):
                obj_name = element.text
                if obj_name:
                    obj_data = self._parse_object(obj_name, obj_type, folder_name)
                    if obj_data:
                        objects.append(obj_data)
        
        return objects
    
    def _parse_object(self, name, obj_type, folder_name):
        """Парсит отдельный объект метаданных"""
        xml_file = self.root_dir / folder_name / f"{name}.xml"
        
        if not xml_file.exists():
            return None
        
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Получаем UUID
        obj_elem = root.find(f'.//{obj_type}')
        uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''
        
        # Получаем свойства
        properties = self._parse_properties(root)
        
        # Получаем модули
        modules = self._parse_modules(name, folder_name)
        
        return {
            'name': name,
            'type': obj_type,
            'uuid': uuid,
            'properties': properties,
            'modules': modules
        }
    
    def _parse_properties(self, root):
        """Извлекает свойства объекта"""
        props = {}
        properties = root.find('.//Properties')
        
        if properties is not None:
            # Синоним
            ns = {'v8': 'http://v8.1c.ru/8.1/data/core'}
            synonym_elem = properties.find('.//v8:content', ns)
            if synonym_elem is not None and synonym_elem.text:
                props['synonym'] = synonym_elem.text
                
            # Комментарий
            comment_elem = properties.find('.//Comment')
            if comment_elem is not None and comment_elem.text:
                props['comment'] = comment_elem.text
        
        return props
    
    def _parse_modules(self, obj_name, folder_name):
        """Извлекает код модулей объекта"""
        modules = []
        obj_dir = self.root_dir / folder_name / obj_name / 'Ext'
        
        if not obj_dir.exists():
            return modules
        
        # Типы модулей
        module_files = {
            'Module.bsl': 'Module',
            'ManagerModule.bsl': 'ManagerModule',
            'ObjectModule.bsl': 'ObjectModule',
        }
        
        for file_name, module_type in module_files.items():
            module_path = obj_dir / file_name
            if module_path.exists():
                with open(module_path, 'r', encoding='utf-8-sig') as f:
                    code = f.read()
                modules.append({
                    'type': module_type,
                    'code': code
                })
        
        return modules


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