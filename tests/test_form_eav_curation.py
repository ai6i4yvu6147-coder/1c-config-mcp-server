"""Unit tests for curate_eav_properties (form drill-down curation, T-2)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.form_eav import curate_eav_properties


def _row(path, name, value, ordinal=0, value_type='string'):
    return {
        'property_path': path,
        'property_name': name,
        'ordinal': ordinal,
        'value_text': value,
        'value_type': value_type,
    }


def test_verbose_returns_all_rows_unchanged():
    rows = [
        _row('ToolTip.item.lang', 'lang', 'ru'),
        _row('DataPath', 'DataPath', 'Список'),
    ]
    props, hidden = curate_eav_properties(rows, verbose=True)
    assert hidden == 0
    assert [p['path'] for p in props] == ['ToolTip.item.lang', 'DataPath']


def test_curated_drops_lang_empty_and_unset_date():
    rows = [
        _row('ToolTip.item.lang', 'lang', 'ru'),
        _row('Period.startDate', 'startDate', '0001-01-01T00:00:00'),
        _row('Title', 'Title', ''),
        _row('DataPath', 'DataPath', 'Список'),
    ]
    props, hidden = curate_eav_properties(rows)
    paths = [p['path'] for p in props]
    assert paths == ['DataPath']
    assert hidden == 3


def test_curated_collapses_localized_content():
    rows = [
        _row('ToolTip.item.content', 'content', 'Всплывающая подсказка'),
        _row('ToolTip.item.lang', 'lang', 'ru'),
    ]
    props, hidden = curate_eav_properties(rows)
    assert len(props) == 1
    assert props[0]['path'] == 'ToolTip'
    assert props[0]['value'] == 'Всплывающая подсказка'
    assert hidden == 1  # only the lang row


def test_priority_paths_ordered_first():
    rows = [
        _row('Behavior', 'Behavior', 'Usual'),
        _row('DataPath', 'DataPath', 'Поле'),
        _row('Title', 'Title', 'Заголовок'),
        _row('AutoMaxWidth', 'AutoMaxWidth', 'true'),
    ]
    props, _ = curate_eav_properties(rows, priority_paths=['DataPath', 'Title'])
    paths = [p['path'] for p in props]
    assert paths[:2] == ['DataPath', 'Title']
    # remaining alphabetical
    assert paths[2:] == ['AutoMaxWidth', 'Behavior']


def test_drop_prefixes_suppresses_family():
    rows = [
        _row('Settings.QueryText', 'QueryText', 'ВЫБРАТЬ 1', value_type='longtext'),
        _row('Settings.Field.dataPath', 'dataPath', 'Ссылка', ordinal=0),
        _row('Settings.Field.field', 'field', 'Ссылка', ordinal=0),
    ]
    props, hidden = curate_eav_properties(rows, drop_prefixes=('Settings.Field.',))
    paths = [p['path'] for p in props]
    assert paths == ['Settings.QueryText']
    assert hidden == 2
