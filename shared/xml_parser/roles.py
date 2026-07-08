import os
import xml.etree.ElementTree as ET

from .role_qname import classify_target_qname
from .xml_helpers import _local_tag, _winlong

ROLES_NS = 'http://v8.1c.ru/8.2/roles'
MD_NS = 'http://v8.1c.ru/8.3/MDClasses'


def _roles_child(parent, local_name):
    """Find direct child in Roles namespace or without namespace."""
    if parent is None:
        return None
    elem = parent.find(f'{{{ROLES_NS}}}{local_name}')
    if elem is None:
        elem = parent.find(local_name)
    return elem


def _roles_children(parent, local_name):
    if parent is None:
        return []
    elems = parent.findall(f'{{{ROLES_NS}}}{local_name}')
    if not elems:
        elems = parent.findall(local_name)
    return elems


def _text(elem):
    if elem is None or elem.text is None:
        return ''
    return elem.text.strip()


def _bool_text(elem):
    text = _text(elem).lower()
    if text == 'true':
        return True
    if text == 'false':
        return False
    return None


def parse_rights_xml(rights_path):
    """
    Parse Roles/<Name>/Ext/Rights.xml.

    Returns dict with role_settings, role_grants, role_access_restrictions,
    role_restriction_templates — or None if file missing/unreadable.
    """
    if not os.path.exists(_winlong(rights_path)):
        return None

    try:
        root = ET.parse(_winlong(rights_path)).getroot()
    except (ET.ParseError, OSError):
        return None

    settings = {
        'set_for_new_objects': _bool_text(_roles_child(root, 'setForNewObjects')),
        'set_for_attributes_by_default': _bool_text(_roles_child(root, 'setForAttributesByDefault')),
        'independent_rights_of_child_objects': _bool_text(_roles_child(root, 'independentRightsOfChildObjects')),
    }

    grants = []
    restrictions = []

    for obj_elem in _roles_children(root, 'object'):
        target_qname = _text(_roles_child(obj_elem, 'name'))
        if not target_qname:
            continue
        target_kind, parent_object_qname = classify_target_qname(target_qname)

        for right_elem in _roles_children(obj_elem, 'right'):
            right_name = _text(_roles_child(right_elem, 'name'))
            if not right_name:
                continue
            granted = _bool_text(_roles_child(right_elem, 'value'))
            grants.append({
                'target_qname': target_qname,
                'target_kind': target_kind,
                'parent_object_qname': parent_object_qname,
                'right_name': right_name,
                'granted': granted,
            })

            for restr_elem in _roles_children(right_elem, 'restrictionByCondition'):
                field_elem = _roles_child(restr_elem, 'field')
                field_scope = _text(field_elem) or None
                condition_elem = _roles_child(restr_elem, 'condition')
                restriction_text = condition_elem.text if condition_elem is not None and condition_elem.text else ''
                restrictions.append({
                    'target_qname': target_qname,
                    'right_name': right_name,
                    'field_scope': field_scope,
                    'restriction_text': restriction_text,
                })

    templates = []
    for tmpl_elem in _roles_children(root, 'restrictionTemplate'):
        template_name = _text(_roles_child(tmpl_elem, 'name'))
        condition_elem = _roles_child(tmpl_elem, 'condition')
        condition_text = condition_elem.text if condition_elem is not None and condition_elem.text else ''
        if template_name:
            templates.append({
                'template_name': template_name,
                'condition_text': condition_text,
            })

    return {
        'role_settings': settings,
        'role_grants': grants,
        'role_access_restrictions': restrictions,
        'role_restriction_templates': templates,
    }


class RolesMixin:
    """Parse Roles/*.xml and Roles/<Name>/Ext/Rights.xml."""

    def _parse_roles(self):
        """Parse all roles from Roles/ directory."""
        roles_root = self.root_dir / 'Roles'
        if not roles_root.is_dir():
            return []

        results = []
        for xml_file in sorted(roles_root.glob('*.xml')):
            if 'Ext' in xml_file.parts:
                continue
            try:
                root = ET.parse(_winlong(xml_file)).getroot()
            except (ET.ParseError, OSError):
                continue

            if self._get_object_element(root, 'Role', MD_NS) is None:
                continue

            role_name = xml_file.stem
            properties = self._parse_properties(root, 'Role')
            obj_elem = self._get_object_element(root, 'Role', MD_NS)
            uuid = obj_elem.get('uuid', '') if obj_elem is not None else ''

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

            results.append(entry)

        return results
