import os

from .xml_helpers import _winlong


class ModulesMixin:
    """BSL module code loading: object modules and object commands (which also load a module)."""

    def _parse_object_commands(self, descriptor, obj_name, folder_name):
        """Команды объекта: Command-дети уже разобранного дескриптора (onec_metadata_schema)
        + модуль Commands/<Name>/Ext/CommandModule.bsl.

        P-7 (audit-2026-08): раньше требовался второй ET.parse того же файла только ради
        команд (+36% времени разбора дескриптора, не видно в профиле — см. аудит). Дескриптор
        уже несёт Command-детей ChildObjects как обычные `Node` (reader.py оборачивает их
        наравне с TabularSection/EnumValue), второй проход не нужен.
        """
        result = []
        for child in descriptor.children:
            if child.tag != 'Command':
                continue
            cmd_name = child.properties.get('Name') or child.name or ''
            if not cmd_name:
                continue
            synonym = self._node_synonym(child)
            ob = child.properties.get('ObjectBelonging')
            ob = ob.strip() if isinstance(ob, str) and ob.strip() else None
            eco = child.properties.get('ExtendedConfigurationObject')
            eco = eco.strip() if isinstance(eco, str) and eco.strip() else None
            module_path = self.root_dir / folder_name / obj_name / 'Commands' / cmd_name / 'Ext' / 'CommandModule.bsl'
            module_code = None
            if os.path.exists(_winlong(module_path)):
                with open(_winlong(module_path), 'r', encoding='utf-8-sig') as f:
                    module_code = f.read()
            result.append({
                'name': cmd_name,
                'synonym': synonym,
                'uuid': child.uuid or '',
                'object_belonging': ob,
                'extended_configuration_object': eco,
                'module_code': module_code,
            })
        return result

    def _parse_modules(self, obj_name, folder_name):
        """Извлекает код модулей объекта"""
        modules = []
        obj_dir = self.root_dir / folder_name / obj_name / 'Ext'

        if not os.path.exists(_winlong(obj_dir)):
            return modules

        # Типы модулей. RecordSetModule — у регистров (сведений/накопления/бухгалтерии/расчёта):
        # там нет ObjectModule, весь код набора записей лежит именно в нём, и без этой строки
        # модуль молча терялся при индексации. ValueManagerModule — модуль менеджера значения
        # константы (у константы бывает и обычный ManagerModule, он уже покрыт выше).
        module_files = {
            'Module.bsl': 'Module',
            'ManagerModule.bsl': 'ManagerModule',
            'ObjectModule.bsl': 'ObjectModule',
            'RecordSetModule.bsl': 'RecordSetModule',
            'ValueManagerModule.bsl': 'ValueManagerModule',
        }

        for file_name, module_type in module_files.items():
            module_path = obj_dir / file_name
            if os.path.exists(_winlong(module_path)):
                with open(_winlong(module_path), 'r', encoding='utf-8-sig') as f:
                    code = f.read()
                modules.append({
                    'type': module_type,
                    'code': code
                })

        return modules
