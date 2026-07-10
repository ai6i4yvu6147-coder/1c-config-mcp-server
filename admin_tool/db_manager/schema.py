class SchemaMixin:
    """DB schema creation (migration-free: always CREATE TABLE/INDEX IF NOT EXISTS)."""

    def _create_schema(self):
        """Создает структуру таблиц"""
        cursor = self.conn.cursor()

        # Таблица объектов метаданных
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                object_type TEXT NOT NULL,
                name TEXT NOT NULL,
                synonym TEXT,
                comment TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                object_kind TEXT NOT NULL DEFAULT 'ConfigObject',
                is_primitive INTEGER NOT NULL DEFAULT 0,
                base_type TEXT,
                qualifier_1 TEXT,
                qualifier_2 TEXT,
                qualifier_3 TEXT
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS uq_metadata_objects_type_descriptor
            ON metadata_objects(object_kind, base_type, qualifier_1, qualifier_2, qualifier_3)
            WHERE object_kind = 'TypeDescriptor'
        ''')

        # Таблица форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_name TEXT NOT NULL,
                form_kind TEXT,
                uuid TEXT,
                properties_json TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица реквизитов форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                is_main INTEGER DEFAULT 0,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Колонки реквизитов форм (ValueTable / AdditionalColumns)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_attribute_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_attribute_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                table_context TEXT,
                FOREIGN KEY (form_attribute_id) REFERENCES form_attributes(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_fac_form_attribute
            ON form_attribute_columns(form_attribute_id)
        ''')

        # Таблица команд форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                action TEXT,
                shortcut TEXT,
                representation TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Таблица событий формы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                handler TEXT NOT NULL,
                call_type TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Таблица элементов UI
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                parent_id INTEGER,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                FOREIGN KEY (form_id) REFERENCES forms(id),
                FOREIGN KEY (parent_id) REFERENCES form_items(id)
            )
        ''')

        # EAV свойства сущностей форм (attribute | attribute_column | item)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_entity_properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_kind TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                property_path TEXT NOT NULL,
                property_name TEXT NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0,
                value_text TEXT,
                value_type TEXT,
                UNIQUE(entity_kind, entity_id, property_path, ordinal)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_fep_entity
            ON form_entity_properties(entity_kind, entity_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_fep_path
            ON form_entity_properties(property_path)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_fep_name
            ON form_entity_properties(property_name)
        ''')

        # Таблица событий элементов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_item_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                handler TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES form_items(id)
            )
        ''')

        # Таблица условного оформления
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_conditional_appearance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                xml_data TEXT NOT NULL,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Команды объекта метаданных (ChildObjects/Command в XML объекта)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS object_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                synonym TEXT,
                uuid TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_object_commands_object_name
            ON object_commands(object_id, name)
        ''')

        # Таблица модулей (form_id для FormModule; command_id для CommandModule команды объекта)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_id INTEGER,
                command_id INTEGER,
                module_type TEXT NOT NULL,
                code TEXT NOT NULL,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (form_id) REFERENCES forms(id),
                FOREIGN KEY (command_id) REFERENCES object_commands(id)
            )
        ''')

        # Таблица процедур/функций модулей (индекс, код хранится в modules.code по start_line/end_line)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                proc_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER,
                params TEXT,
                is_export INTEGER DEFAULT 0,
                execution_context TEXT,
                extension_call_type TEXT,
                comment TEXT,
                used_in_scheduled_job INTEGER DEFAULT 0,
                FOREIGN KEY (module_id) REFERENCES modules(id)
            )
        ''')

        # Таблица атрибутов объектов (стандартные + кастомные + измерения/ресурсы регистров)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                is_standard INTEGER DEFAULT 0,
                standard_type TEXT,
                section TEXT NOT NULL DEFAULT 'Attribute',
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица табличных частей (нормализованная)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabular_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица колонок табличных частей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabular_section_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tabular_section_id INTEGER NOT NULL,
                column_name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                FOREIGN KEY (tabular_section_id) REFERENCES tabular_sections(id)
            )
        ''')

        # Нормализованные типы реквизитов и колонок ТЧ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_type_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL,
                source_row_id INTEGER NOT NULL,
                src_object_id INTEGER NOT NULL,
                object_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (src_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_object ON metadata_type_slots(object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_src_object ON metadata_type_slots(src_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_source ON metadata_type_slots(source_table, source_row_id)
        ''')

        # Таблица значений перечислений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enum_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                enum_order INTEGER,
                title TEXT,
                comment TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Точки маршрута бизнес-процессов (Flowchart.xml)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bp_route_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                point_type TEXT NOT NULL,
                title TEXT,
                uuid TEXT,
                tab_order INTEGER,
                true_port INTEGER,
                false_port INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bp_route_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                from_point TEXT NOT NULL,
                to_point TEXT NOT NULL,
                from_port INTEGER,
                title TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица функциональных опций (свойства ФО; Content хранится в fo_content_ref)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS functional_options (
                object_id INTEGER NOT NULL PRIMARY KEY,
                location_constant TEXT,
                privileged_get_mode INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Регламентные задания (свойства из ScheduledJob.xml)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                object_id INTEGER NOT NULL PRIMARY KEY,
                method_name TEXT,
                description TEXT,
                key TEXT,
                use INTEGER,
                predefined INTEGER,
                restart_count_on_failure INTEGER,
                restart_interval_on_failure INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Структурные связи метаданных (подсистемы, роли, подписки — не типы полей)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_object_id INTEGER NOT NULL,
                dst_object_id INTEGER NOT NULL,
                relation_kind TEXT NOT NULL,
                source_name TEXT,
                source_detail TEXT,
                FOREIGN KEY (src_object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (dst_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_src ON metadata_relations(src_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_dst ON metadata_relations(dst_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_kind ON metadata_relations(relation_kind)
        ''')

        # Привязка ФО к объектам метаданных (Content ФО: документ/реквизит/колонка ТЧ/ресурс)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fo_content_ref (
                functional_option_id INTEGER NOT NULL,
                metadata_object_id INTEGER NOT NULL,
                content_ref_type TEXT NOT NULL,
                tabular_section_name TEXT,
                element_name TEXT,
                FOREIGN KEY (functional_option_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (metadata_object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Привязка ФО к элементам форм (реквизит/команда/элемент формы зависит от ФО)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fo_form_usage (
                functional_option_id INTEGER NOT NULL,
                owner_object_id INTEGER NOT NULL,
                form_id INTEGER,
                element_type TEXT NOT NULL,
                element_name TEXT,
                parent_element_name TEXT,
                FOREIGN KEY (functional_option_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (owner_object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Индексы для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_objects_name
            ON metadata_objects(name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_objects_type
            ON metadata_objects(object_type)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_forms_name
            ON forms(form_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_form_items_name
            ON form_items(name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_form_items_type
            ON form_items(item_type)
        ''')

        # Индексы для атрибутов
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attributes_object
            ON attributes(object_id)
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_sections_object ON tabular_sections(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_section_columns_ts ON tabular_section_columns(tabular_section_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_section_columns_name ON tabular_section_columns(column_name)')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_enum_values_object
            ON enum_values(object_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bp_route_points_object
            ON bp_route_points(object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bp_route_transitions_object
            ON bp_route_transitions(object_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_content_ref_fo
            ON fo_content_ref(functional_option_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_content_ref_object
            ON fo_content_ref(metadata_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_form_usage_fo
            ON fo_form_usage(functional_option_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_form_usage_owner_form
            ON fo_form_usage(owner_object_id, form_id, element_type, element_name)
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_modules_object ON modules(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_forms_object ON forms(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_events_form ON form_events(form_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_item_events_item ON form_item_events(item_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_procedures_module ON module_procedures(module_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_procedures_name ON module_procedures(name)')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_method_name
            ON scheduled_jobs(method_name)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_settings (
                role_object_id INTEGER NOT NULL PRIMARY KEY,
                set_for_new_objects INTEGER,
                set_for_attributes_by_default INTEGER,
                independent_rights_of_child_objects INTEGER,
                source_db_name TEXT,
                FOREIGN KEY (role_object_id) REFERENCES metadata_objects(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_object_id INTEGER NOT NULL,
                target_qname TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                parent_object_qname TEXT NOT NULL,
                right_name TEXT NOT NULL,
                granted INTEGER,
                source_db_name TEXT,
                FOREIGN KEY (role_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_role_grants_role
            ON role_grants(role_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_role_grants_parent
            ON role_grants(parent_object_qname)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_role_grants_target_right
            ON role_grants(target_qname, right_name)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_access_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grant_id INTEGER NOT NULL,
                field_scope TEXT,
                restriction_text TEXT NOT NULL,
                source_db_name TEXT,
                FOREIGN KEY (grant_id) REFERENCES role_grants(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_role_access_restrictions_grant
            ON role_access_restrictions(grant_id)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_restriction_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_object_id INTEGER NOT NULL,
                template_name TEXT NOT NULL,
                condition_text TEXT NOT NULL,
                source_db_name TEXT,
                FOREIGN KEY (role_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_role_restriction_templates_role
            ON role_restriction_templates(role_object_id)
        ''')

        # Таблица для полнотекстового поиска по коду (FTS5)
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS code_search
            USING fts5(
                object_name,
                module_type,
                code,
                content='modules',
                content_rowid='id'
            )
        ''')

        self.conn.commit()
