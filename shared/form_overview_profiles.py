"""Overview property profiles for form MCP tools (mirrors docs/form-entity-model.md §4)."""

from __future__ import annotations

from shared.form_eav import count_field_siblings, query_text_length

ITEM_TYPE_TO_FAMILY = {
    'InputField': 'field_like',
    'LabelField': 'field_like',
    'CheckBoxField': 'field_like',
    'RadioButtonField': 'field_like',
    'Table': 'list_like',
    'Button': 'command_like',
    'UsualGroup': 'container',
    'Pages': 'container',
    'Page': 'container',
    'ButtonGroup': 'container',
    'Popup': 'container',
    'CommandBar': 'container',
    'LabelDecoration': 'decoration',
    'PictureDecoration': 'decoration',
    'ExtendedTooltip': 'decoration',
    'SpreadSheetDocumentField': 'document_field',
    'HTMLDocumentField': 'document_field',
    'FormattedDocumentField': 'document_field',
    'FlowchartField': 'chart_like',
    'PlannerField': 'chart_like',
    'GanttChartField': 'chart_like',
    'SearchControl': 'search_control',
}

OVERVIEW_PATHS_BY_FAMILY = {
    'field_like': ['DataPath', 'Title', 'Visible', 'Enabled', 'ReadOnly'],
    'list_like': ['DataPath', 'Title', 'Visible', 'Enabled', 'RowPictureDataPath', 'AutoRefresh'],
    'command_like': ['CommandName', 'Title', 'Visible', 'Enabled', 'Representation'],
    'container': ['Title', 'Visible', 'Enabled', 'Group', 'Representation'],
    'decoration': ['Title', 'Visible', 'Enabled'],
    'document_field': ['DataPath', 'Title', 'Visible', 'Enabled'],
    'chart_like': ['DataPath', 'Title', 'Visible', 'Enabled'],
    'search_control': ['DataPath', 'Title', 'Visible', 'Enabled'],
}

COLUMN_CONTAINER_TYPES = frozenset({'Table'})

PARSER_ITEM_TYPES = frozenset(ITEM_TYPE_TO_FAMILY.keys())


def item_family(item_type: str) -> str | None:
    return ITEM_TYPE_TO_FAMILY.get(item_type)


def overview_paths_for_item(item_type: str) -> list[str]:
    family = item_family(item_type)
    if not family:
        return []
    return list(OVERVIEW_PATHS_BY_FAMILY.get(family, []))


def is_column_container(item_type: str) -> bool:
    return item_type in COLUMN_CONTAINER_TYPES


def is_dynamic_list(types: list) -> bool:
    return any(t.get('kind') == 'primitive' and t.get('base_type') == 'DynamicList' for t in (types or []))


def is_value_table(types: list) -> bool:
    return any(t.get('kind') == 'primitive' and t.get('base_type') == 'ValueTable' for t in (types or []))


def attribute_overview_hints(types: list, eav_rows: list, column_count: int) -> list[str]:
    """Hint lines for get_form_structure attribute overview."""
    hints = []
    if is_value_table(types):
        hints.append(f'columns: {column_count} — get_form_attribute(attribute_name="…")')
    if is_dynamic_list(types):
        qlen = query_text_length(eav_rows)
        if qlen:
            hints.append(f'QueryText: present ({qlen} chars)')
        field_count = count_field_siblings(eav_rows)
        if field_count:
            hints.append(f'columns: {field_count}')
        hints.append('— get_form_attribute(attribute_name="…")')
    elif column_count and not is_value_table(types):
        pass
    return hints
