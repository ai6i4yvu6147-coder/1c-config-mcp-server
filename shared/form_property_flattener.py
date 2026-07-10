"""Flatten Form.xml entity subtrees into EAV property rows for form_entity_properties."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any

V8_CORE = 'http://v8.1c.ru/8.1/data/core'
LOGFORM_NS = 'http://v8.1c.ru/8.3/xcf/logform'

LONGTEXT_PROPERTY_NAMES = frozenset({'QueryText'})

SKIP_TAGS = {
    'attribute': frozenset({'Type', 'Columns', 'MainAttribute', 'FunctionalOptions'}),
    'attribute_column': frozenset({'Type', 'FunctionalOptions'}),
    'item': frozenset({'ChildItems', 'Items', 'Events', 'FunctionalOptions'}),
}


def _local_tag(tag: str) -> str:
    if tag and '}' in tag:
        return tag.split('}', 1)[1]
    return tag or ''


def _extract_leaf_value(elem: ET.Element, local_name: str) -> str | None:
    """Extract scalar value from a leaf element."""
    if local_name == 'Title':
        content = elem.find(f'.//{{{V8_CORE}}}content')
        if content is not None and content.text:
            return content.text.strip()
        return None

    children = list(elem)
    if children:
        return None

    text = (elem.text or '').strip()
    return text if text else None


def _value_type_for(local_name: str, value: str) -> str:
    if local_name in LONGTEXT_PROPERTY_NAMES:
        return 'longtext'
    lower = value.lower()
    if lower in ('true', 'false'):
        return 'boolean'
    try:
        float(value)
        if '.' not in value:
            int(value)
        return 'number'
    except ValueError:
        pass
    if len(value) > 500:
        return 'longtext'
    return 'string'


def flatten_entity(elem: ET.Element, entity_kind: str) -> list[dict[str, Any]]:
    """Walk entity XML subtree and return EAV row dicts for insert."""
    skip = SKIP_TAGS.get(entity_kind, frozenset())
    rows: list[dict[str, Any]] = []
    path_ordinals: dict[str, int] = defaultdict(int)

    def emit(path_parts: list[str], local_name: str, value: str) -> None:
        path = '.'.join(path_parts) if path_parts else local_name
        ordinal = path_ordinals[path]
        path_ordinals[path] += 1
        rows.append({
            'property_path': path,
            'property_name': local_name,
            'ordinal': ordinal,
            'value_text': value,
            'value_type': _value_type_for(local_name, value),
        })

    def walk(parent: ET.Element, path_parts: list[str]) -> None:
        child_tags: dict[str, list[ET.Element]] = defaultdict(list)
        for child in parent:
            local = _local_tag(child.tag)
            if local in skip:
                continue
            child_tags[local].append(child)

        for local, siblings in child_tags.items():
            for child in siblings:
                child_path = path_parts + [local]
                value = _extract_leaf_value(child, local)
                if value is not None:
                    emit(child_path, local, value)
                else:
                    walk(child, child_path)

    walk(elem, [])
    return rows


def flatten_attribute(attr_elem: ET.Element) -> list[dict[str, Any]]:
    return flatten_entity(attr_elem, 'attribute')


def flatten_attribute_column(col_elem: ET.Element) -> list[dict[str, Any]]:
    return flatten_entity(col_elem, 'attribute_column')


def flatten_item(item_elem: ET.Element) -> list[dict[str, Any]]:
    return flatten_entity(item_elem, 'item')
