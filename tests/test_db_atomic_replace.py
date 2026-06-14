import os

from admin_tool.db_manager import DatabaseManager, _replace_file_with_retry
from shared.db_build_state import tmp_db_path


def test_close_allows_atomic_replace_with_wal(tmp_path):
    db_path = tmp_path / 'test.db'
    tmp = tmp_db_path(db_path)

    mgr = DatabaseManager(tmp)
    mgr.connect()
    mgr.conn.execute('CREATE TABLE t(x INTEGER)')
    mgr.conn.execute('INSERT INTO t VALUES (1)')
    mgr.conn.commit()
    mgr.close()

    _replace_file_with_retry(tmp, db_path)
    assert db_path.exists()
    assert not tmp.exists()
