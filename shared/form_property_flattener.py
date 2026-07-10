"""Flatten Form.xml entity subtrees into EAV property rows for form_entity_properties."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any

LONGTEXT_PROPERTY_NAMES = frozenset({'QueryText'})

# Platform sentinel for an unset date/period bound (Period.startDate/endDate and similar).
# Never real user data — dropped wherever it occurs so it never reaches the EAV table.
UNSET_DATE_VALUE = '0001-01-01T00:00:00'

SKIP_TAGS = {
    'attribute': frozenset({'Type', 'Columns', 'MainAttribute', 'FunctionalOptions'}),
    'attribute_column': frozenset({'Type', 'FunctionalOptions'}),
    'item': frozenset({'ChildItems', 'Items', 'Events', 'FunctionalOptions'}),
}

# Tags skipped in every entity kind: pure structural wiring, never meaningful to an agent.
# AdditionSource (SearchStringAddition/ViewStatusAddition/…) just echoes back the owning
# item's own name + a fixed enum discriminator — no independent data.
GLOBAL_SKIP_TAGS = frozenset({'AdditionSource'})


def _local_tag(tag: str) -> str:
    if tag and '}' in tag:
        return tag.split('}', 1)[1]
    return tag or ''


def _is_localized_string_container(elem: ET.Element) -> bool:
    """True if every child is a v8 `item` — the localized-string wrapper
    (`<Tag><item><lang/><content/></item>…</Tag>`, one item per language)."""
    children = list(elem)
    if not children:
        return False
    return all(_local_tag(child.tag) == 'item' for child in children)


def _localized_string_value(elem: ET.Element) -> str | None:
    """Collapse a localized-string container to one value: prefer `lang=ru`,
    else the first non-empty content found."""
    best = None
    for item in elem:
        lang = None
        content = None
        for sub in item:
            local = _local_tag(sub.tag)
            if local == 'lang':
                lang = (sub.text or '').strip()
            elif local == 'content':
                content = (sub.text or '').strip()
        if content:
            if lang == 'ru':
                return content
            if best is None:
                best = content
    return best


def _extract_leaf_value(elem: ET.Element, local_name: str) -> str | None:
    """Extract scalar value from a leaf element."""
    if _is_localized_string_container(elem):
        return _localized_string_value(elem)

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
    skip = SKIP_TAGS.get(entity_kind, frozenset()) | GLOBAL_SKIP_TAGS
    rows: list[dict[str, Any]] = []
    path_ordinals: dict[str, int] = defaultdict(int)

    def emit(path_parts: list[str], local_name: str, value: str) -> None:
        if value == UNSET_DATE_VALUE:
            return
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
