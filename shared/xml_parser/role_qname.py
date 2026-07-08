"""Classify Rights.xml object target qualified names."""


def classify_target_qname(target_qname):
    """
    Return (target_kind, parent_object_qname) for a Rights.xml <object><name>.

    parent_object_qname is Type.Name for metadata object-level grants;
  field-level rows point at the owning metadata object.
    """
    if not target_qname or '.' not in target_qname:
        return 'object', target_qname or ''

    parts = target_qname.split('.')
    if parts[0] == 'Configuration':
        return 'configuration', target_qname

    if len(parts) < 2:
        return 'object', target_qname

    parent = f'{parts[0]}.{parts[1]}'
    if len(parts) == 2:
        return 'object', parent

    if '.StandardAttribute.' in target_qname:
        return 'standard_attribute', parent
    if '.Attribute.' in target_qname:
        return 'attribute', parent
    if '.TabularSection.' in target_qname:
        after_ts = target_qname.split('.TabularSection.', 1)[1]
        if '.Attribute.' in after_ts:
            return 'tabular_section_attribute', parent
        return 'tabular_section', parent
    if '.Resource.' in target_qname:
        return 'resource', parent
    if '.Dimension.' in target_qname:
        return 'dimension', parent
    if '.Command.' in target_qname:
        return 'command', parent

    return 'field', parent
