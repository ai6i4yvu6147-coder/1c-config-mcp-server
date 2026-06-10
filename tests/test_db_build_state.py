from shared.db_build_state import (
    building_marker_path,
    clear_building,
    is_building,
    is_stale_building,
    mark_building,
    reconcile_building_markers,
    tmp_db_path,
)


def test_building_marker_lifecycle(tmp_path):
    db_path = tmp_path / 'proj_main.db'
    assert not is_building(db_path)
    mark_building(db_path)
    assert is_building(db_path)
    assert building_marker_path(db_path).exists()
    clear_building(db_path)
    assert not is_building(db_path)


def test_tmp_path_suffix(tmp_path):
    db_path = tmp_path / 'foo.db'
    assert tmp_db_path(db_path).name == 'foo.db.tmp'


def test_reconcile_removes_stale_marker(tmp_path):
    db_path = tmp_path / 'foo.db'
    mark_building(db_path)
    marker = building_marker_path(db_path)
    marker.write_text('{"pid": 999999999}', encoding='utf-8')
    reconcile_building_markers(tmp_path)
    assert not marker.exists()


def test_is_stale_when_pid_dead_and_no_tmp(tmp_path):
    db_path = tmp_path / 'foo.db'
    marker = building_marker_path(db_path)
    marker.write_text('{"pid": 999999999}', encoding='utf-8')
    assert is_stale_building(db_path)
