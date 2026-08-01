import json

from .bsl import _parse_module_procedures


def _insert_entity_properties(cursor, entity_kind, entity_id, properties):
    """Bulk-insert EAV rows for one entity."""
    if not properties:
        return
    cursor.executemany('''
        INSERT INTO form_entity_properties (
            entity_kind, entity_id, property_path, property_name, ordinal, value_text, value_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [
        (
            entity_kind,
            entity_id,
            p['property_path'],
            p['property_name'],
            p.get('ordinal', 0),
            p.get('value_text'),
            p.get('value_type'),
        )
        for p in properties
    ])


class FormInsertionMixin:
    """Form insertion (forms + attributes + commands + events + items + fo_form_usage) and Content-ref parsing."""

    def _parse_content_ref(self, ref_str):
        """Парсит строку Content ФО (например Document.Имя, Document.Имя.Attribute.Рекв,
        Document.Имя.TabularSection.ТЧ.Attribute.Кол, InformationRegister.Имя.Resource.Ресурс).
        Возвращает (object_type, object_name, content_ref_type, tabular_section_name, element_name)
        или None при неверном формате."""
        if not ref_str or not isinstance(ref_str, str):
            return None
        s = ref_str.strip()
        parts = s.split('.')
        if len(parts) < 2:
            return None
        object_type = parts[0]
        object_name = parts[1]
        if len(parts) == 2:
            return (object_type, object_name, 'Object', None, None)
        if len(parts) == 4:
            # Type.Name.Attribute|Resource|Dimension.ElementName
            ref_type = parts[2]
            if ref_type in ('Attribute', 'Resource', 'Dimension'):
                return (object_type, object_name, ref_type, None, parts[3])
            return None
        if len(parts) == 6 and parts[2] == 'TabularSection' and parts[4] == 'Attribute':
            return (object_type, object_name, 'TabularSectionColumn', parts[3], parts[5])
        return None

    def _resolve_fo_id(self, fo_ref, fo_resolver):
        """Разрешает ссылку на ФО (UUID или FunctionalOption.Имя) в id. Возвращает id или None."""
        if not fo_ref or not fo_resolver:
            return None
        s = fo_ref.strip()
        return fo_resolver.get(s)

    def _insert_fo_form_usage(self, cursor, fo_id, owner_object_id, form_id, element_type, element_name,
                              parent_element_name=None):
        cursor.execute('''
            INSERT INTO fo_form_usage (
                functional_option_id, owner_object_id, form_id,
                element_type, element_name, parent_element_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (fo_id, owner_object_id, form_id, element_type, element_name, parent_element_name))

    def _record_fo_form_usage(self, cursor, fo_ref, fo_resolver, pending_fo_usage,
                              owner_object_id, form_id, element_type, element_name,
                              parent_element_name=None):
        """Использование ФО на элементе формы: сразу строкой в fo_form_usage или, при потоковой
        вставке (`pending_fo_usage is not None`), в отложенный список — id функциональной опции
        известен только когда вставлены все объекты. См. `_insert_configuration`."""
        if pending_fo_usage is not None:
            pending_fo_usage.append(
                (fo_ref, owner_object_id, form_id, element_type, element_name, parent_element_name)
            )
            return
        fo_id = self._resolve_fo_id(fo_ref, fo_resolver)
        if fo_id is not None:
            self._insert_fo_form_usage(
                cursor, fo_id, owner_object_id, form_id,
                element_type, element_name, parent_element_name,
            )

    def _insert_form(self, cursor, object_id, form, fo_resolver=None, pending_type_slots=None,
                     pending_fo_usage=None):
        """Вставляет данные формы в БД. fo_resolver: dict (uuid/имя/FunctionalOption.Имя -> id)
        для fo_form_usage; pending_fo_usage — отложенное разрешение вместо fo_resolver."""
        fo_resolver = fo_resolver or {}
        cursor.execute('''
            INSERT INTO forms (object_id, form_name, form_kind, uuid, properties_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            object_id,
            form['name'],
            form.get('form_kind'),
            form['uuid'],
            json.dumps(form['properties'], ensure_ascii=False) if form['properties'] else None
        ))
        form_id = cursor.lastrowid

        for attr in form.get('attributes', []):
            cursor.execute('''
                INSERT INTO form_attributes (form_id, name, title, is_main)
                VALUES (?, ?, ?, ?)
            ''', (
                form_id,
                attr['name'],
                attr['title'],
                1 if attr['is_main'] else 0,
            ))
            attr_id = cursor.lastrowid
            _insert_entity_properties(cursor, 'attribute', attr_id, attr.get('entity_properties'))
            if pending_type_slots is not None:
                type_slots = attr.get('type_slots')
                if type_slots:
                    pending_type_slots.append({
                        'source_table': 'form_attributes',
                        'source_row_id': attr_id,
                        'src_object_id': object_id,
                        'type_slots': type_slots,
                    })
            for col in attr.get('columns') or []:
                cursor.execute('''
                    INSERT INTO form_attribute_columns (
                        form_attribute_id, name, title, table_context
                    )
                    VALUES (?, ?, ?, ?)
                ''', (
                    attr_id,
                    col['name'],
                    col.get('title', ''),
                    col.get('table'),
                ))
                col_id = cursor.lastrowid
                _insert_entity_properties(cursor, 'attribute_column', col_id, col.get('entity_properties'))
                if pending_type_slots is not None:
                    col_slots = col.get('type_slots')
                    if col_slots:
                        pending_type_slots.append({
                            'source_table': 'form_attribute_columns',
                            'source_row_id': col_id,
                            'src_object_id': object_id,
                            'type_slots': col_slots,
                        })
                for fo_ref in col.get('functional_options', []):
                    self._record_fo_form_usage(
                        cursor, fo_ref, fo_resolver, pending_fo_usage, object_id, form_id,
                        'FormAttributeColumn', col['name'], parent_element_name=attr['name'],
                    )
            for fo_ref in attr.get('functional_options', []):
                self._record_fo_form_usage(
                    cursor, fo_ref, fo_resolver, pending_fo_usage, object_id, form_id,
                    'FormAttribute', attr['name'],
                )

        for cmd in form.get('commands', []):
            cursor.execute('''
                INSERT INTO form_commands (
                    form_id, name, title, action, shortcut, representation
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                cmd['name'],
                cmd['title'],
                cmd['action'],
                cmd.get('shortcut'),
                cmd.get('representation')
            ))
            for fo_ref in cmd.get('functional_options', []):
                self._record_fo_form_usage(
                    cursor, fo_ref, fo_resolver, pending_fo_usage, object_id, form_id,
                    'FormCommand', cmd['name'],
                )

        # Вставляем события формы
        for event in form.get('events', []):
            cursor.execute('''
                INSERT INTO form_events (form_id, event_name, handler, call_type)
                VALUES (?, ?, ?, ?)
            ''', (
                form_id,
                event['name'],
                event['handler'],
                event['call_type']
            ))

        # Вставляем элементы UI
        item_id_map = {}  # Маппинг item['id'] -> db_id

        for item in form.get('items', []):
            parent_db_id = None
            if item['parent_id']:
                parent_db_id = item_id_map.get(item['parent_id'])

            cursor.execute('''
                INSERT INTO form_items (form_id, parent_id, name, item_type)
                VALUES (?, ?, ?, ?)
            ''', (
                form_id,
                parent_db_id,
                item['name'],
                item['type'],
            ))

            item_db_id = cursor.lastrowid
            item_id_map[item['id']] = item_db_id
            _insert_entity_properties(cursor, 'item', item_db_id, item.get('entity_properties'))
            for fo_ref in item.get('functional_options', []):
                self._record_fo_form_usage(
                    cursor, fo_ref, fo_resolver, pending_fo_usage, object_id, form_id,
                    'FormItem', item['name'],
                )

            for event in item.get('events', []):
                cursor.execute('''
                    INSERT INTO form_item_events (item_id, event_name, handler)
                    VALUES (?, ?, ?)
                ''', (
                    item_db_id,
                    event['name'],
                    event['handler']
                ))

        if form.get('conditional_appearance'):
            cursor.execute('''
                INSERT INTO form_conditional_appearance (form_id, xml_data)
                VALUES (?, ?)
            ''', (
                form_id,
                form['conditional_appearance']
            ))

        if form.get('module'):
            cursor.execute('''
                INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                VALUES (?, ?, NULL, ?, ?)
            ''', (
                object_id,
                form_id,
                'FormModule',
                form['module']
            ))

            module_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO code_search (rowid, code)
                VALUES (?, ?)
            ''', (module_id, form['module']))
            procs = _parse_module_procedures(form['module'])
            if procs:
                cursor.executemany('''
                    INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                       p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])
