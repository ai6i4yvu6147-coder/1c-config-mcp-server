import os
import xml.etree.ElementTree as ET

from .role_qname import classify_target_qname
from .xml_helpers import _winlong

MD_NS = 'http://v8.1c.ru/8.3/MDClasses'


def _reshape_rights_from_library(neutral):
    """Turn ``onec_metadata_schema.read_rights``'s neutral dict (objects -> rights ->
    restrictions, structurally faithful to the XML) into C-MCP's flat indexing shape.

    The library owns the *format* (which tags, whitespace/bool rules, namespace tolerance);
    the ``classify_target_qname`` taxonomy (``target_kind``/``parent_object_qname``) stays
    here — it is C-MCP's storage model, not a fact about ``Rights.xml``. Output is
    byte-for-byte the same dict the legacy hand-rolled parser produced (A/B verified)."""
    grants = []
    restrictions = []
    for obj in neutral['objects']:
        target_qname = obj['name']
        target_kind, parent_object_qname = classify_target_qname(target_qname)
        for right in obj['rights']:
            right_name = right['name']
            grants.append({
                'target_qname': target_qname,
                'target_kind': target_kind,
                'parent_object_qname': parent_object_qname,
                'right_name': right_name,
                'granted': right['value'],
            })
            for restr in right['restrictions']:
                restrictions.append({
                    'target_qname': target_qname,
                    'right_name': right_name,
                    'field_scope': restr['field'],
                    'restriction_text': restr['condition'],
                })

    templates = [
        {'template_name': t['name'], 'condition_text': t['condition']}
        for t in neutral['templates']
    ]

    return {
        'role_settings': dict(neutral['settings']),
        'role_grants': grants,
        'role_access_restrictions': restrictions,
        'role_restriction_templates': templates,
    }


def parse_rights_xml(rights_path):
    """
    Parse Roles/<Name>/Ext/Rights.xml through the single format engine
    (``onec_metadata_schema.read_rights``), reshaped to C-MCP's flat indexing dict
    (role_settings, role_grants, role_access_restrictions, role_restriction_templates).

    Returns None if the file is missing or malformed (skip-on-error: one bad Rights.xml must
    not fail the whole build — same contract as forms/DCS). Library absence surfaces loudly
    via ImportError, but by the time roles are parsed the object pass has already required the
    library, so it is guaranteed present.
    """
    if not os.path.exists(_winlong(rights_path)):
        return None
    from onec_metadata_schema import read_rights
    try:
        with open(_winlong(rights_path), 'rb') as f:
            xml = f.read()
        return _reshape_rights_from_library(read_rights(xml))
    except (ET.ParseError, OSError):
        return None


class RolesMixin:
    """Parse Roles/*.xml and Roles/<Name>/Ext/Rights.xml."""

    def _parse_roles(self):
        """Parse all roles from Roles/ directory."""
        return list(self._iter_roles())

    def _iter_roles(self):
        """Роли по одной (`parser-streaming-pipeline`): у крупной конфигурации это ~3000 ролей
        и сотни тысяч грантов — держать их все в памяти незачем, потребитель вставляет и
        отпускает каждую. Время копится по одной роли, чтобы в `stage_seconds['roles']` не
        попало время потребителя (генератор исполняется между его итерациями)."""
        roles_root = self.root_dir / 'Roles'
        if not roles_root.is_dir():
            return

        for xml_file in sorted(roles_root.glob('*.xml')):
            if 'Ext' in xml_file.parts:
                continue
            with self._accumulate('roles'):
                entry = self._parse_role_file(xml_file, roles_root)
            if entry is not None:
                yield entry

    def _parse_role_file(self, xml_file, roles_root):
        """Одна роль: дескриптор `Roles/<Имя>.xml` + права `Roles/<Имя>/Ext/Rights.xml`.
        None — файл не читается или это не Role (skip-on-error, как формы/СКД)."""
        try:
            root = ET.parse(_winlong(xml_file)).getroot()
        except (ET.ParseError, OSError):
            return None

        obj_elem = self._get_object_element(root, 'Role', MD_NS)
        if obj_elem is None:
            return None

        role_name = xml_file.stem
        properties = self._parse_properties(root, 'Role')
        uuid = obj_elem.get('uuid', '')

        rights_path = roles_root / role_name / 'Ext' / 'Rights.xml'
        rights_data = parse_rights_xml(rights_path)

        entry = {
            'name': role_name,
            'type': 'Role',
            'uuid': uuid,
            'properties': properties,
            'modules': [],
            'forms': [],
            'tabular_sections': [],
            'dimensions': [],
            'resources': [],
            'enum_values': [],
            'commands': [],
            'role_settings': None,
            'role_grants': [],
            'role_access_restrictions': [],
            'role_restriction_templates': [],
        }

        if rights_data:
            entry['role_settings'] = rights_data['role_settings']
            entry['role_grants'] = rights_data['role_grants']
            entry['role_access_restrictions'] = rights_data['role_access_restrictions']
            entry['role_restriction_templates'] = rights_data['role_restriction_templates']

        return entry
