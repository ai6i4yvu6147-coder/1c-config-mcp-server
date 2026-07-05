from ..metadata_type_resolver import parse_cfg_type_string


class TypeSlotsMixin:
    """Type-slot extraction: resolves BSL/metadata type strings into structured slots.

    Used both by metadata parsing (attributes, tabular section columns, register
    dimensions/resources) and by form parsing (form attributes, table columns).
    """

    def _dedupe_type_strings_preserve_order(self, items):
        seen = set()
        out = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _find_metadata_type_container(self, elem, md_ns):
        """Контейнер типа в метаданных: обычно Properties/Type (MDClasses)."""
        props = elem.find(f'{{{md_ns}}}Properties')
        if props is not None:
            t = props.find(f'{{{md_ns}}}Type')
            if t is not None:
                return t
        return elem.find(f'.//{{{md_ns}}}Type')

    def _v8_child_text(self, parent, v8_ns, local_name):
        elem = parent.find(f'{{{v8_ns}}}{local_name}')
        if elem is not None and elem.text is not None:
            return elem.text.strip()
        return None

    def _extract_qualifiers_from_type_container(self, type_elem, v8_ns):
        """Извлекает квалификаторы примитива из контейнера Type."""
        num_q = type_elem.find(f'{{{v8_ns}}}NumberQualifiers')
        if num_q is not None:
            digits = self._v8_child_text(num_q, v8_ns, 'Digits')
            fraction = self._v8_child_text(num_q, v8_ns, 'FractionDigits')
            return {
                'digits': int(digits) if digits is not None else None,
                'fraction': int(fraction) if fraction is not None else None,
                'allowed_sign': self._v8_child_text(num_q, v8_ns, 'AllowedSign'),
            }
        str_q = type_elem.find(f'{{{v8_ns}}}StringQualifiers')
        if str_q is not None:
            length = self._v8_child_text(str_q, v8_ns, 'Length')
            return {
                'length': int(length) if length is not None else None,
                'allowed_length': self._v8_child_text(str_q, v8_ns, 'AllowedLength'),
            }
        date_q = type_elem.find(f'{{{v8_ns}}}DateQualifiers')
        if date_q is not None:
            return {
                'date_fractions': self._v8_child_text(date_q, v8_ns, 'DateFractions'),
            }
        return None

    def _slot_from_type_string(self, type_str, qualifiers=None):
        slot = parse_cfg_type_string(type_str)
        if slot.get('kind') == 'primitive' and qualifiers:
            slot = dict(slot)
            slot['qualifiers'] = qualifiers
        return slot

    def _extract_type_slots(self, elem):
        """Извлекает структурированные слоты типа атрибута/колонки."""
        md_ns = 'http://v8.1c.ru/8.3/MDClasses'
        v8_ns = 'http://v8.1c.ru/8.1/data/core'

        type_elem = self._find_metadata_type_container(elem, md_ns)
        if type_elem is not None:
            direct = []
            for child in list(type_elem):
                if child.tag == f'{{{v8_ns}}}Type' and child.text and child.text.strip():
                    direct.append(child.text.strip())
            if direct:
                qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
                slots = []
                for type_str in self._dedupe_type_strings_preserve_order(direct):
                    slot = self._slot_from_type_string(
                        type_str,
                        qualifiers if len(direct) == 1 else None,
                    )
                    slots.append(slot)
                return slots

            from_set = []
            for ts in type_elem.findall(f'.//{{{v8_ns}}}TypeSet'):
                if ts.text and ts.text.strip():
                    from_set.append(ts.text.strip())
                for t in ts.findall(f'.//{{{v8_ns}}}Type'):
                    if t.text and t.text.strip():
                        from_set.append(t.text.strip())
            if from_set:
                qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
                slots = []
                for type_str in self._dedupe_type_strings_preserve_order(from_set):
                    slot = parse_cfg_type_string(type_str)
                    if qualifiers and slot.get('kind') == 'primitive':
                        slot = dict(slot)
                        slot['qualifiers'] = qualifiers
                    slots.append(slot)
                return slots

        value_type = elem.find(f'.//{{{md_ns}}}ValueType')
        if value_type is not None:
            refs = []
            for ref in value_type.findall(f'.//{{{v8_ns}}}Ref'):
                if ref.text and ref.text.strip():
                    refs.append(ref.text.strip())
            if refs:
                return [
                    self._slot_from_type_string(type_str)
                    for type_str in self._dedupe_type_strings_preserve_order(refs)
                ]

        v8_type = elem.find(f'.//{{{v8_ns}}}Type')
        if v8_type is not None and v8_type.text and v8_type.text.strip():
            return [self._slot_from_type_string(v8_type.text.strip())]

        return []

    def _extract_attribute_type(self, elem):
        """Извлекает тип атрибута как строку (legacy helper для тестов)."""
        slots = self._extract_type_slots(elem)
        raws = [s.get('raw') for s in slots if s.get('raw')]
        if raws:
            return ', '.join(self._dedupe_type_strings_preserve_order(raws))
        return ''

    def _find_logform_type_container(self, elem, logform_ns):
        """Контейнер Type в logform (прямой потомок или вложенный)."""
        t = elem.find(f'{{{logform_ns}}}Type')
        if t is not None:
            return t
        return elem.find(f'.//{{{logform_ns}}}Type')

    def _extract_slots_from_v8_type_container(self, type_elem, v8_ns):
        """Слоты из контейнера с v8:Type / v8:TypeSet (logform или Settings)."""
        direct = []
        for child in list(type_elem):
            local_tag = child.tag.split('}')[-1] if child.tag else ''
            if local_tag == 'Type' and child.text and child.text.strip():
                direct.append(child.text.strip())
        if direct:
            qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
            slots = []
            for type_str in self._dedupe_type_strings_preserve_order(direct):
                slot = self._slot_from_type_string(
                    type_str,
                    qualifiers if len(direct) == 1 else None,
                )
                slots.append(slot)
            return slots

        from_set = []
        for ts in type_elem.findall(f'.//{{{v8_ns}}}TypeSet'):
            if ts.text and ts.text.strip():
                from_set.append(ts.text.strip())
            for t in ts.findall(f'.//{{{v8_ns}}}Type'):
                if t.text and t.text.strip():
                    from_set.append(t.text.strip())
        if from_set:
            qualifiers = self._extract_qualifiers_from_type_container(type_elem, v8_ns)
            slots = []
            for type_str in self._dedupe_type_strings_preserve_order(from_set):
                slot = parse_cfg_type_string(type_str)
                if qualifiers and slot.get('kind') == 'primitive':
                    slot = dict(slot)
                    slot['qualifiers'] = qualifiers
                slots.append(slot)
            return slots
        return []

    def _extract_logform_type_slots(self, elem):
        """Структурированные слоты типа реквизита/колонки формы (logform NS)."""
        logform_ns = 'http://v8.1c.ru/8.3/xcf/logform'
        v8_ns = 'http://v8.1c.ru/8.1/data/core'

        slots = []
        type_elem = self._find_logform_type_container(elem, logform_ns)
        if type_elem is not None:
            slots.extend(self._extract_slots_from_v8_type_container(type_elem, v8_ns))

        settings_elem = elem.find(f'{{{logform_ns}}}Settings')
        if settings_elem is not None:
            slots.extend(self._extract_slots_from_v8_type_container(settings_elem, v8_ns))

        return slots
