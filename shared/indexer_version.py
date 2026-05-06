"""
Версия формата индекса (SQLite), не путать с версией приложения.

Увеличивать INDEXER_VERSION вручную в том же коммите, что и изменение, если:
- меняется схема в admin_tool/db_manager.py (CREATE TABLE, индексы, FTS);
- меняется shared/xml_parser.py или _insert_configuration так, что существующие
  databases/*.db становятся неполными или некорректными для текущего MCP.

Не увеличивать при правках только в server/, в admin_tool/gui_v2.py или при
рефакторинге без изменения того, что записывается в БД.

Значение записывается в каждую .db как PRAGMA user_version при создании/обновлении
через admin_tool (см. DatabaseManager.create_database).
"""

INDEXER_VERSION = 1
