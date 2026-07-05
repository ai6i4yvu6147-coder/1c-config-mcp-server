class ModulesMixin:
    """BSL module code loading: object modules and object commands (which also load a module)."""

    def _parse_object_commands(self, root, obj_name, folder_name, obj_type):
        """Команды объекта: ChildObjects/Command в XML + модуль Commands/<Name>/Ext/CommandModule.bsl."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return []
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for child in child_objects:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag != 'Command':
                continue
            cmd_uuid = child.get('uuid', '') or ''
            props = child.find(f'{{{md_ns}}}Properties')
            cmd_name = ''
            synonym = ''
            ob = None
            eco = None
            if props is not None:
                name_elem = props.find(f'{{{md_ns}}}Name')
                if name_elem is not None and name_elem.text:
                    cmd_name = name_elem.text.strip()
            if not cmd_name:
                cmd_name = child.get('name', '') or self._get_attribute_name(child, md_ns)
            if not cmd_name:
                continue
            synonym = self._extract_synonym(child)
            if props is not None:
                ob_elem = props.find(f'{{{md_ns}}}ObjectBelonging')
                if ob_elem is not None and ob_elem.text:
                    ob = ob_elem.text.strip()
                eco_elem = props.find(f'{{{md_ns}}}ExtendedConfigurationObject')
                if eco_elem is not None and eco_elem.text:
                    eco = eco_elem.text.strip()
            module_path = self.root_dir / folder_name / obj_name / 'Commands' / cmd_name / 'Ext' / 'CommandModule.bsl'
            module_code = None
            if module_path.exists():
                with open(module_path, 'r', encoding='utf-8-sig') as f:
                    module_code = f.read()
            result.append({
                'name': cmd_name,
                'synonym': synonym,
                'uuid': cmd_uuid,
                'object_belonging': ob,
                'extended_configuration_object': eco,
                'module_code': module_code,
            })
        return result

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
