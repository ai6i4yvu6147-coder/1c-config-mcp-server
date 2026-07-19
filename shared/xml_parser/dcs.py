"""DataCompositionSchema templates -- the new read path via the library.

The legacy parser never read `Templates/` at all, so DCS indexing is purely additive and
isolated behind the library (`onec_metadata_schema.dcs`): a broken or non-DCS template is
skipped and recorded in `self.skipped_dcs`, never fatal -- mirroring `skipped_forms` (P-2).
Срез 1 uses `query_texts` (-> FTS `code_search`); Срез 2 uses `schema`/`shape`
(-> `dcs_schema` table + `get_dcs_schema`). See docs/dcs-schema-indexing.md.
"""

import os
import xml.etree.ElementTree as ET

from .xml_helpers import _winlong

_MD_NS = 'http://v8.1c.ru/8.3/MDClasses'


class TemplatesDcsMixin:
    """Discovery + library-backed reading of an object's DCS templates."""

    def _dcs_reader(self):
        """Cached tuple of the library DCS read functions, or ``None`` when the library is
        unavailable -- DCS indexing then degrades to a no-op so ordinary config parsing
        never depends on it (external reports/processors still hard-require it elsewhere)."""
        cached = getattr(self, '_dcs_reader_cache', False)
        if cached is not False:
            return cached
        try:
            from onec_metadata_schema.dcs import (
                dcs_shape_hints,
                read_dcs_query_texts,
                read_dcs_schema,
            )
            cached = (read_dcs_schema, read_dcs_query_texts, dcs_shape_hints)
        except ImportError:
            cached = None
        self._dcs_reader_cache = cached
        return cached

    def _is_dcs_descriptor(self, descriptor_path):
        """True only for a `TemplateType=DataCompositionSchema` descriptor (MXL and other
        template kinds are indexed separately/deferred)."""
        try:
            root = ET.parse(_winlong(descriptor_path)).getroot()
        except (ET.ParseError, OSError):
            return False
        ttype = root.find(f'.//{{{_MD_NS}}}TemplateType')
        return ttype is not None and (ttype.text or '').strip() == 'DataCompositionSchema'

    def _parse_dcs_schemas(self, name, folder_name):
        """DCS schemas owned by ``<folder_name>/<name>/Templates/``.

        Returns a list of ``{template_name, query_texts, schema, shape}``; empty when the
        object owns no ``Templates/`` dir, no DCS template (MXL-only), or the library is
        absent. Descriptor lives at ``Templates/<Name>.xml`` (declares ``TemplateType``);
        the schema body at ``Templates/<Name>/Ext/Template.xml``."""
        templates_dir = self.root_dir / folder_name / name / 'Templates'
        if not templates_dir.is_dir():
            return []
        reader = self._dcs_reader()
        if reader is None:
            return []
        read_dcs_schema, read_dcs_query_texts, dcs_shape_hints = reader

        schemas = []
        for descriptor in sorted(templates_dir.glob('*.xml')):
            template_name = descriptor.stem
            body = templates_dir / template_name / 'Ext' / 'Template.xml'
            if not os.path.exists(_winlong(body)):
                continue
            if not self._is_dcs_descriptor(descriptor):
                continue
            try:
                with open(_winlong(body), 'rb') as f:
                    xml = f.read()
                schema = read_dcs_schema(xml)
            except Exception as exc:  # skip-on-error: one bad schema must not fail the build
                self.skipped_dcs.append({
                    'object': f'{folder_name}/{name}',
                    'template': template_name,
                    'error': str(exc),
                })
                continue
            schemas.append({
                'template_name': template_name,
                'query_texts': read_dcs_query_texts(schema),
                'schema': schema,
                'shape': dcs_shape_hints(schema),
            })
        return schemas

    def _spreadsheet_reader(self):
        """Cached library ``read_spreadsheet_text`` (MXL macet text), or ``None`` when the
        library is unavailable -- macet indexing then degrades to a no-op, mirroring
        ``_dcs_reader`` (ordinary config parsing never depends on it)."""
        cached = getattr(self, '_spreadsheet_reader_cache', False)
        if cached is not False:
            return cached
        try:
            from onec_metadata_schema import read_spreadsheet_text
            cached = read_spreadsheet_text
        except ImportError:
            cached = None
        self._spreadsheet_reader_cache = cached
        return cached

    def _is_spreadsheet_descriptor(self, descriptor_path):
        """True only for a ``TemplateType=SpreadsheetDocument`` descriptor (the MXL macet
        path; DCS and other template kinds are handled/skipped separately)."""
        try:
            root = ET.parse(_winlong(descriptor_path)).getroot()
        except (ET.ParseError, OSError):
            return False
        ttype = root.find(f'.//{{{_MD_NS}}}TemplateType')
        return ttype is not None and (ttype.text or '').strip() == 'SpreadsheetDocument'

    def _parse_spreadsheet_templates(self, name, folder_name):
        """MXL macets owned by ``<folder_name>/<name>/Templates/`` (mxl-macet-indexing).

        Returns a list of ``{template_name, text}`` — the macet's visible text (cell text +
        whole-cell parameters + named-area names) for FTS ``code_search`` (Срез 1). Empty when
        macet indexing is off (``self.index_spreadsheet_templates`` — off for configurations/
        extensions, on for external reports/processors), or the object owns no ``Templates/``
        dir, no MXL template, or the library is absent. The legacy parser never read
        ``Templates/`` at all → purely additive, skip-on-error like ``_parse_dcs_schemas``.
        See docs/mxl-macet-indexing.md."""
        if not self.index_spreadsheet_templates:
            return []
        templates_dir = self.root_dir / folder_name / name / 'Templates'
        if not templates_dir.is_dir():
            return []
        read_spreadsheet_text = self._spreadsheet_reader()
        if read_spreadsheet_text is None:
            return []

        macets = []
        for descriptor in sorted(templates_dir.glob('*.xml')):
            template_name = descriptor.stem
            body = templates_dir / template_name / 'Ext' / 'Template.xml'
            if not os.path.exists(_winlong(body)):
                continue
            if not self._is_spreadsheet_descriptor(descriptor):
                continue
            try:
                with open(_winlong(body), 'rb') as f:
                    text = read_spreadsheet_text(f.read())
            except Exception as exc:  # skip-on-error: one bad macet must not fail the build
                self.skipped_dcs.append({
                    'object': f'{folder_name}/{name}',
                    'template': template_name,
                    'error': str(exc),
                })
                continue
            macets.append({'template_name': template_name, 'text': text})
        return macets
