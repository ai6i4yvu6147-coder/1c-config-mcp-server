"""Pure merge helpers for effective role state across configuration layers."""

PURPOSE_ORDER = {
    'Customization': 0,
    'AddOn': 1,
    'Patch': 2,
}


def sort_layers_for_merge(layers):
    """
    Order layers: main first, then extensions by ConfigurationExtensionPurpose
    (Customization < AddOn < Patch), tie-break by source_db_name.
    """
    main_layers = [layer for layer in layers if layer.get('db_type') == 'base']
    ext_layers = [layer for layer in layers if layer.get('db_type') != 'base']
    ext_layers.sort(
        key=lambda layer: (
            PURPOSE_ORDER.get(layer.get('extension_purpose') or '', 99),
            layer.get('source_db_name') or '',
        )
    )
    return main_layers + ext_layers


def merge_role_settings(layers):
    """Last layer with role_settings wins."""
    effective = None
    for layer in layers:
        if layer.get('role_settings') is not None:
            effective = dict(layer['role_settings'])
            effective['source_db_name'] = layer.get('source_db_name')
    return effective


def merge_grants(layers):
    """Overlay grants by (target_qname, right_name)."""
    merged = {}
    for layer in layers:
        source = layer.get('source_db_name')
        for grant in layer.get('grants') or []:
            key = (grant['target_qname'], grant['right_name'])
            merged[key] = {**grant, 'source_db_name': source}
    return list(merged.values())


def merge_restrictions(layers):
    """Overlay restrictions by (target_qname, right_name, field_scope)."""
    merged = {}
    for layer in layers:
        source = layer.get('source_db_name')
        for restr in layer.get('access_restrictions') or []:
            key = (
                restr['target_qname'],
                restr['right_name'],
                restr.get('field_scope'),
            )
            merged[key] = {**restr, 'source_db_name': source}
    return list(merged.values())


def merge_templates(layers):
    """Overlay templates by template_name."""
    merged = {}
    for layer in layers:
        source = layer.get('source_db_name')
        for tmpl in layer.get('restriction_templates') or []:
            key = tmpl['template_name']
            merged[key] = {**tmpl, 'source_db_name': source}
    return list(merged.values())


def filter_grants(grants, *, object_name=None, rights=None, depth='object'):
    """Apply object_name, rights list, and depth filters."""
    result = grants
    if depth == 'object':
        result = [g for g in result if g.get('target_kind') == 'object']
    if object_name:
        needle = object_name.lower()
        result = [
            g for g in result
            if needle in g.get('parent_object_qname', '').lower()
            or needle in g.get('target_qname', '').lower()
        ]
    if rights:
        allowed = {r.lower() for r in rights}
        result = [g for g in result if g.get('right_name', '').lower() in allowed]
    return result


def filter_restrictions(restrictions, *, rls=None, object_name=None):
    result = restrictions
    if rls is False:
        return []
    if object_name:
        needle = object_name.lower()
        result = [
            r for r in result
            if needle in (r.get('target_qname') or '').lower()
        ]
    return result


def grant_stats(grants):
    object_level = sum(1 for g in grants if g.get('target_kind') == 'object')
    field_level = len(grants) - object_level
    total_rights = len(grants)
    return {
        'object_level': object_level,
        'field_level': field_level,
        'total_rights': total_rights,
    }


def should_use_summary_mode(role_name, grant_count, object_name, response_mode, max_results):
    if response_mode == 'full':
        return False
    if object_name:
        return False
    if role_name == 'ПолныеПрава':
        return True
    return grant_count > max_results


def restriction_preview(text, include_mode, max_chars=200):
    if include_mode is False or include_mode is None:
        return None
    if include_mode == 'full':
        return text
    if not text:
        return ''
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '…'
