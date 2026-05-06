## Правило: бамп INDEXER_VERSION при несовместимых изменениях БД

Если правка меняет **схему** в `admin_tool/db_manager.py` (таблицы, индексы, FTS) или **то, что записывается в БД** из `shared/xml_parser.py` / `_insert_configuration` так, что существующие `databases/*.db` становятся неполными или некорректными для текущего MCP — в **том же коммите** увеличьте `INDEXER_VERSION` в `shared/indexer_version.py`.

Если неочевидно, нужен ли бамп — **спросите пользователя**.

Не бампать при правках только в `server/`, в `admin_tool/gui_v2.py` или при рефакторинге без изменения содержимого БД.

См. также: `docs/database.md` (раздел про `INDEXER_VERSION`), `NO_DB_MIGRATIONS` в `.cursor/rules/no-db-migrations.md`.
