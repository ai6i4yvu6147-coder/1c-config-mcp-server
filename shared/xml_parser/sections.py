class SectionsMixin:
    """Tabular sections, register sections (Dimensions/Resources/Attributes), and enum values."""

    def _parse_tabular_sections(self, root, obj_type):
        """Извлекает табличные части: из TabularSections или из ChildObjects (формат выгрузки 2.20)."""
        result = []
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return result

        # Вариант 1: контейнер TabularSections
        ts_container = obj_elem.find(f'{{{md_ns}}}TabularSections')
        if ts_container is not None:
            for ts_elem in ts_container.findall(f'{{{md_ns}}}TabularSection'):
                ts_name = ts_elem.get('name', '') or self._get_attribute_name(ts_elem, md_ns)
                if not ts_name:
                    continue
                ts_title = self._extract_synonym(ts_elem)
                columns = []
                attrs_elem = ts_elem.find(f'{{{md_ns}}}Attributes')
                if attrs_elem is not None:
                    for attr in attrs_elem.findall(f'{{{md_ns}}}Attribute'):
                        col_name = attr.get('name', '') or self._get_attribute_name(attr, md_ns)
                        if col_name:
                            columns.append({
                                'name': col_name,
                                'type_slots': self._extract_type_slots(attr),
                                'title': self._extract_synonym(attr),
                                'comment': self._extract_comment(attr),
                            })
                result.append({'name': ts_name, 'title': ts_title, 'comment': self._extract_comment(ts_elem), 'columns': columns})
            return result

        # Вариант 2: выгрузка 2.20 — табличные части в ChildObjects как TabularSection
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return result
        for child in child_objects:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag != 'TabularSection':
                continue
            ts_name = child.get('name', '') or self._get_attribute_name(child, md_ns)
            if not ts_name:
                continue
            ts_title = self._extract_synonym(child)
            columns = []
            ts_child_objects = child.find(f'{{{md_ns}}}ChildObjects')
            if ts_child_objects is not None:
                for col_elem in ts_child_objects:
                    col_local = col_elem.tag.split('}')[-1] if '}' in col_elem.tag else col_elem.tag
                    if col_local != 'Attribute':
                        continue
                    col_name = self._get_attribute_name(col_elem, md_ns)
                    if col_name:
                        columns.append({
                            'name': col_name,
                            'type_slots': self._extract_type_slots(col_elem),
                            'title': self._extract_synonym(col_elem),
                            'comment': self._extract_comment(col_elem),
                        })
            result.append({'name': ts_name, 'title': ts_title, 'comment': self._extract_comment(child), 'columns': columns})
        return result

    def _parse_register_section(self, root, section_tag, obj_type):
        """Извлекает секцию регистра: Dimensions, Resources или Attributes.
        Поддерживает классический формат (контейнеры Dimensions/Resources) и формат 2.20 (Dimension/Resource в ChildObjects).
        """
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        singular_map = {
            'Dimensions': 'Dimension',
            'Resources': 'Resource',
            'Attributes': 'Attribute',
        }
        child_tag = singular_map.get(section_tag, section_tag[:-1])

        obj_elem = self._get_object_element(root, obj_type, md_ns)
        if obj_elem is None:
            return []

        container = obj_elem.find(f'{{{md_ns}}}{section_tag}')
        if container is not None:
            result = []
            for elem in container.findall(f'{{{md_ns}}}{child_tag}'):
                elem_name = elem.get('name', '') or self._get_attribute_name(elem, md_ns)
                if elem_name:
                    result.append({
                        'name': elem_name,
                        'type_slots': self._extract_type_slots(elem),
                        'title': self._extract_synonym(elem),
                        'comment': self._extract_comment(elem),
                    })
            return result

        # Формат 2.20: Dimension/Resource лежат в ChildObjects без обёрток Dimensions/Resources
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for elem in child_objects.findall(f'{{{md_ns}}}{child_tag}'):
            elem_name = elem.get('name', '') or self._get_attribute_name(elem, md_ns)
            if elem_name:
                result.append({
                    'name': elem_name,
                    'type_slots': self._extract_type_slots(elem),
                    'title': self._extract_synonym(elem),
                    'comment': self._extract_comment(elem),
                })
        return result

    def _parse_enum_value_elem(self, ev_elem, md_ns):
        """Из одного элемента EnumValue собирает словарь для БД."""
        ev_name = ev_elem.get('name', '') or self._get_attribute_name(ev_elem, md_ns)
        if not ev_name:
            return None
        ev_title = self._extract_synonym(ev_elem)
        ev_order = None
        ev_belonging = None
        ev_extended = None
        props_elem = ev_elem.find(f'{{{md_ns}}}Properties')
        if props_elem is not None:
            order_elem = props_elem.find(f'{{{md_ns}}}Order')
            if order_elem is not None and order_elem.text:
                try:
                    ev_order = int(order_elem.text)
                except ValueError:
                    pass
            ob_elem = props_elem.find(f'{{{md_ns}}}ObjectBelonging')
            if ob_elem is not None and ob_elem.text:
                ev_belonging = ob_elem.text.strip()
            eco_elem = props_elem.find(f'{{{md_ns}}}ExtendedConfigurationObject')
            if eco_elem is not None and eco_elem.text:
                ev_extended = eco_elem.text.strip()
        return {
            'name': ev_name,
            'title': ev_title,
            'comment': self._extract_comment(ev_elem),
            'order': ev_order,
            'object_belonging': ev_belonging,
            'extended_configuration_object': ev_extended,
        }

    def _parse_enum_values(self, root):
        """Извлекает значения перечисления. Поддерживает контейнер EnumValues и формат 2.20 (EnumValue в ChildObjects)."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'

        obj_elem = self._get_object_element(root, 'Enum', md_ns)
        if obj_elem is None:
            return []

        ev_container = obj_elem.find(f'{{{md_ns}}}EnumValues')
        if ev_container is not None:
            result = []
            for ev_elem in ev_container.findall(f'{{{md_ns}}}EnumValue'):
                ev = self._parse_enum_value_elem(ev_elem, md_ns)
                if ev:
                    result.append(ev)
            return result

        # Формат 2.20: значения перечисления в ChildObjects без обёртки EnumValues
        child_objects = obj_elem.find(f'{{{md_ns}}}ChildObjects')
        if child_objects is None:
            return []
        result = []
        for ev_elem in child_objects.findall(f'{{{md_ns}}}EnumValue'):
            ev = self._parse_enum_value_elem(ev_elem, md_ns)
            if ev:
                result.append(ev)
        return result
