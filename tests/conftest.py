"""Shared fixtures and helpers for ConfigurationTools integration tests."""

import sqlite3
from pathlib import Path

import pytest

from shared.indexer_version import INDEXER_VERSION
from server.tools import ConfigurationTools


METADATA_OBJECTS_DDL = '''
    CREATE TABLE metadata_objects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT,
        object_type TEXT NOT NULL,
        name TEXT NOT NULL,
        synonym TEXT,
        comment TEXT,
        object_belonging TEXT,
        extended_configuration_object TEXT,
        object_kind TEXT NOT NULL DEFAULT 'ConfigObject',
        is_primitive INTEGER NOT NULL DEFAULT 0,
        base_type TEXT,
        qualifier_1 TEXT,
        qualifier_2 TEXT,
        qualifier_3 TEXT
    );
'''


def create_test_db(path: Path, ddl_and_data: str) -> None:
    """Create a mini SQLite DB with INDEXER_VERSION and the given schema/data SQL."""
    conn = sqlite3.connect(path)
    conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
    conn.executescript(ddl_and_data)
    conn.commit()
    conn.close()


def build_configuration_tools(tmp_path: Path, db_path: Path) -> ConfigurationTools:
    """ConfigurationTools with a single mocked active database."""
    tools = ConfigurationTools(
        projects_file=str(tmp_path / 'projects.json'),
        databases_dir=str(tmp_path),
    )
    db_info = {
        'project_name': 'TestProject',
        'db_name': 'Main',
        'db_type': 'base',
        'db_path': str(db_path),
    }
    tools._get_active_databases = lambda project_filter=None, include_outdated=False: [db_info]
    return tools


@pytest.fixture
def tools_with_db_factory(tmp_path):
    """Factory fixture: tools_with_db_factory(setup_fn) -> ConfigurationTools."""

    def _factory(setup_fn):
        db_path = tmp_path / 'test.db'
        conn = sqlite3.connect(db_path)
        conn.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
        setup_fn(conn)
        conn.commit()
        conn.close()
        return build_configuration_tools(tmp_path, db_path)

    yield _factory
