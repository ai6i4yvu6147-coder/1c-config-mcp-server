"""External data processor / external report as project-root kinds (Variant B).

An external data processor or external report lives in its own file (`<Name>.xml`, root
`MetaDataObject/ExternalDataProcessor` or `MetaDataObject/ExternalReport`) — not inside any
`Configuration.xml`, so neither is an `object_types` whitelist entry (see
docs/metadata-whitelist.md). They are additional root kinds alongside configuration and
extension.

Read side (this module): the object **descriptor** (`<Name>.xml`) is parsed through the
shared `1c-metadata-schema` library's generic `Node` reader, then adapted into the exact
dict shape `_parse_object(..., obj_type='DataProcessor'|'Report')` already produces, so the
existing `admin_tool/db_manager` insert pipeline consumes it unchanged (no duplicate
insert path). Type slots pass through verbatim — the library's decoded `.Type` property is
byte-identical to `_extract_type_slots()` (parity confirmed on real exports; both share the
ported `parse_cfg_type_string` logic).

An external report descriptor is structurally the same as a processor (uuid, object
requisites, tabular sections, form name-refs) plus `Template` name-refs and DCS-related
descriptor props (`MainDataCompositionSchema`, settings/variant forms). The `Template`
name-refs in the descriptor are ignored, but the caller (`_parse_external_root`) reads the
actual `Templates/` dir off disk for **both** DCS schemas and MXL macets: unlike an embedded
`Report` (which indexes DCS but not MXL — macets there are layout-only noise at corpus
scale), an external report/processor is a single object whose macet/schema is usually its
whole payload, so both are indexed. See docs/mxl-macet-indexing.md.

Modules (`.bsl`), form structure (`Form.xml`) and object commands are **separate files on
disk**, not present in the descriptor Node — the library's `parse()` is single-file. They
are read by the existing config-mcp file-walk methods with `folder_name=''`, because an
external object's siblings sit directly next to `<Name>.xml`
(`<root>/<Name>/Ext/…`, `<root>/<Name>/Forms/…`), i.e. the same relative layout an embedded
`DataProcessor`/`Report` has under `DataProcessors/<Name>/…` / `Reports/<Name>/…`.

Canon: docs/group/shared/metadata-library-cluster.md (Variant B); track
`external-processor-root` in docs/todo.md.
"""

EXTERNAL_DATA_PROCESSOR_TAG = 'ExternalDataProcessor'
EXTERNAL_REPORT_TAG = 'ExternalReport'


class ExternalProcessorMixin:
    """Root dispatch + Node->dict adapter for external data processor / report descriptors."""

    def _parse_external_data_processor(self, root):
        return self._parse_external_root(root, EXTERNAL_DATA_PROCESSOR_TAG, 'DataProcessor')

    def _parse_external_report(self, root):
        return self._parse_external_root(root, EXTERNAL_REPORT_TAG, 'Report')

    def _parse_external_root(self, root, descriptor_tag, obj_type):
        """Build the same {name, extension_purpose, objects:[…]} structure `parse()`
        returns for a configuration, but for a single external object (`obj_type` is the
        internal type it maps onto: an external data processor -> 'DataProcessor', an
        external report -> 'Report').

        `root` is the already-parsed ElementTree root of `<Name>.xml`; it is reused for the
        file-walk methods that read from the raw XML (commands) rather than the library Node.
        """
        try:
            import onec_metadata_schema
        except ImportError as exc:  # pragma: no cover - packaging guard
            raise RuntimeError(
                "External data processor/report support requires the '1c-metadata-schema' "
                "library (onec_metadata_schema). Install it "
                "(`pip install -e ../1c-metadata-schema`) and rebuild the portable."
            ) from exc

        node = onec_metadata_schema.parse(self.config_path)
        descriptor = self._find_descriptor_node(node, descriptor_tag)
        if descriptor is None:
            return {'name': '', 'extension_purpose': '', 'objects': []}

        name = descriptor.properties.get('Name') or descriptor.name or self.config_path.stem
        obj = self._adapt_object_descriptor(descriptor, name, obj_type)

        # File-walk siblings: folder_name='' — the object sits at <root_dir>/<Name>.xml, its
        # Ext/Forms/Commands directly under <root_dir>/<Name>/… (same relative shape the
        # embedded path uses under DataProcessors/<Name>/… or Reports/<Name>/…).
        with self._accumulate('modules'):
            obj['modules'] = self._parse_modules(name, '')
        # DataProcessor/Report Properties carry no DefaultObjectForm/List/ChoiceForm, so
        # form_kind detection is None-based here too — parity with the embedded path.
        default_forms = {'Element': None, 'List': None, 'Choice': None}
        with self._accumulate('forms'):
            obj['forms'] = self._parse_forms(name, '', default_forms)
        with self._accumulate('commands'):
            obj['commands'] = self._parse_object_commands(root, name, '', descriptor_tag)
        # Templates/ live at <root_dir>/<Name>/Templates/ (folder_name='') — same relative
        # shape as the embedded path. Unlike embedded objects, external reports/processors DO
        # index MXL macets (self.index_spreadsheet_templates set True in parse()): the macet is
        # typically the object's payload. DCS too — a pure external DCS report carries all its
        # meaning in the schema. See docs/mxl-macet-indexing.md, docs/dcs-schema-indexing.md.
        with self._accumulate('dcs'):
            obj['dcs_schemas'] = self._parse_dcs_schemas(name, '')
            obj['spreadsheet_templates'] = self._parse_spreadsheet_templates(name, '')

        return {'name': name, 'extension_purpose': '', 'objects': [obj]}

    @staticmethod
    def _find_descriptor_node(node, tag):
        """The library root is `MetaDataObject`; its descriptor child bears `tag`."""
        if node.tag == tag:
            return node
        for child in node.children:
            if child.tag == tag:
                return child
        return None

    def _adapt_object_descriptor(self, descriptor, name, obj_type):
        """Node -> the descriptor-derived subset of the `_parse_object` dict.

        `modules`/`forms`/`commands`/`dcs_schemas`/`spreadsheet_templates` are placeholders
        here — the caller (`_parse_external_root`) fills them via the existing file-walk
        methods. `Template` name-ref children in the descriptor are ignored; the caller reads
        the `Templates/` dir off disk instead (see module docstring).
        """
        properties = {'standard_attributes': [], 'custom_attributes': []}

        synonym = self._node_synonym(descriptor)
        if synonym:
            properties['synonym'] = synonym
        comment = descriptor.properties.get('Comment')
        if comment:
            properties['comment'] = comment
        # Extension adoption markers (Own/Adopted) — present only in extension exports.
        belonging = descriptor.properties.get('ObjectBelonging')
        if isinstance(belonging, str) and belonging.strip():
            properties['object_belonging'] = belonging.strip()
        extended = descriptor.properties.get('ExtendedConfigurationObject')
        if isinstance(extended, str) and extended.strip():
            properties['extended_configuration_object'] = extended.strip()

        for child in descriptor.children:
            if child.tag == 'Attribute':
                properties['custom_attributes'].append(self._adapt_attribute_node(child))

        tabular_sections = [
            self._adapt_tabular_section_node(child)
            for child in descriptor.children
            if child.tag == 'TabularSection'
        ]

        return {
            'name': name,
            'type': obj_type,
            'uuid': descriptor.uuid or '',
            'properties': properties,
            'modules': [],
            'forms': [],
            'tabular_sections': tabular_sections,
            'dimensions': [],
            'resources': [],
            'enum_values': [],
            'commands': [],
        }

    def _adapt_attribute_node(self, node):
        return {
            'name': node.properties.get('Name') or node.name or '',
            'type_slots': node.properties.get('Type') or [],
            'title': self._node_synonym(node),
            'comment': node.properties.get('Comment') or '',
            'is_standard': False,
            'standard_type': None,
        }

    def _adapt_tabular_section_node(self, node):
        columns = [
            {
                'name': col.properties.get('Name') or col.name or '',
                'type_slots': col.properties.get('Type') or [],
                'title': self._node_synonym(col),
                'comment': col.properties.get('Comment') or '',
            }
            for col in node.children
            if col.tag == 'Attribute'
        ]
        return {
            'name': node.properties.get('Name') or node.name or '',
            'title': self._node_synonym(node),
            'comment': node.properties.get('Comment') or '',
            'columns': columns,
        }

    @staticmethod
    def _node_synonym(node):
        """Library decodes `Synonym` to `[{'lang','content'}, …]`; config-mcp's
        `_extract_synonym` returns the first `content` in document order — same as `[0]`.
        """
        synonym = node.properties.get('Synonym')
        if isinstance(synonym, list) and synonym:
            first = synonym[0]
            if isinstance(first, dict):
                return first.get('content') or ''
        return ''
