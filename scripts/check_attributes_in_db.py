"""
Проверка наличия реквизитов объектов в БД конфигурации.
Запуск: python scripts/check_attributes_in_db.py [путь_к_базе] [имя_объекта]
Если путь к базе не указан — используются активные проекты из config (server).
"""
import sqlite3
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def get_config_path():
    """Путь к config.json сервера для получения списка баз."""
    root = Path(__file__).resolve().parent.parent
    for candidate in [root / "server" / "config.json", root / "config.json"]:
        if candidate.exists():
            return candidate
    return None

def get_db_paths_from_config():
    """Список путей к БД из config (упрощённо — только db_path)."""
    import json
    config_path = get_config_path()
    if not config_path:
        return []
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    projects = data.get("projects", [])
    paths = []
    for p in projects:
        for db in p.get("databases", []):
            path = db.get("db_path") or db.get("path")
            if path:
                paths.append((p.get("name", ""), db.get("db_name", ""), path))
    return paths

def check_db(db_path, object_name_filter=None):
    """Проверяет реквизиты в одной БД. Возвращает список (object_name, attributes_count, sample_attrs)."""
    if not Path(db_path).exists():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, object_type FROM metadata_objects WHERE 1=1"
        + (" AND name LIKE ?" if object_name_filter else "")
        + " ORDER BY object_type, name",
        (f"%{object_name_filter}%",) if object_name_filter else ()
    )
    rows = cur.fetchall()
    result = []
    for row in rows:
        cur.execute(
            "SELECT name, attribute_type, section FROM attributes WHERE object_id = ? ORDER BY section, name",
            (row["id"],)
        )
        attrs = cur.fetchall()
        result.append({
            "name": row["name"],
            "type": row["object_type"],
            "attributes_count": len(attrs),
            "attributes": [dict(a) for a in attrs],
        })
    conn.close()
    return result

def main():
    object_name = (sys.argv[2] if len(sys.argv) > 2 else "").strip() or None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        db_path = sys.argv[1].strip()
        print(f"Проверка БД: {db_path}")
        print("Объект-фильтр:", object_name or "(все)")
        data = check_db(db_path, object_name)
        if data is None:
            print("Файл БД не найден.")
            return 1
        for obj in data:
            print(f"\n  {obj['type']}.{obj['name']}: реквизитов = {obj['attributes_count']}")
            for a in obj["attributes"][:15]:
                print(f"    - {a['name']}: {a['attribute_type']} [{a['section']}]")
            if len(obj["attributes"]) > 15:
                print(f"    ... и ещё {len(obj['attributes']) - 15}")
        return 0
    # Из config
    paths = get_db_paths_from_config()
    if not paths:
        print("Укажите путь к БД: python scripts/check_attributes_in_db.py <path_to_db> [object_name]")
        return 1
    for project_name, db_name, db_path in paths:
        if not Path(db_path).exists():
            print(f"Пропуск (нет файла): {project_name} / {db_name} — {db_path}")
            continue
        print(f"\n=== {project_name} / {db_name} ===\n")
        data = check_db(db_path, object_name)
        if not data:
            print("  Объектов не найдено.")
            continue
        for obj in data:
            print(f"  {obj['type']}.{obj['name']}: реквизитов = {obj['attributes_count']}")
            if object_name and obj["attributes_count"] <= 20:
                for a in obj["attributes"]:
                    print(f"    - {a['name']}: {a['attribute_type']} [{a['section']}]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
