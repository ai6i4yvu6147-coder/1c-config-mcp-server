from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .core import DatabaseManagerCore
from .schema import SchemaMixin
from .insert_objects import ObjectInsertionMixin
from .insert_forms import FormInsertionMixin
from .relations import RelationsMixin
from .roles import RoleInsertionMixin
from .file_ops import format_build_error, _replace_file_with_retry


class DatabaseManager(
    ObjectInsertionMixin,
    FormInsertionMixin,
    RelationsMixin,
    RoleInsertionMixin,
    SchemaMixin,
    DatabaseManagerCore,
):
    """Управление SQLite базой данных конфигурации"""


def test_database_creation(config_xml_path, db_path):
    """Тестовая функция создания БД"""

    def progress(current, total, message):
        print(f"[{current}/{total}] {message}")

    db = DatabaseManager(db_path)
    db.connect()

    print("Создание базы данных...")
    db.create_database(config_xml_path, progress)

    print("\nСтатистика:")
    stats = db.get_statistics()
    print(f"  Всего объектов: {stats['total_objects']}")
    print(f"  Всего модулей: {stats['total_modules']}")
    print(f"  Всего атрибутов: {stats['total_attributes']}")
    print(f"    - Стандартных: {stats['total_standard_attributes']}")
    print(f"    - Кастомных: {stats['total_custom_attributes']}")
    print("\nПо типам:")
    for obj_type, count in stats['by_type'].items():
        print(f"  {obj_type}: {count}")
    if stats.get('total_functional_options', 0) or stats.get('total_fo_content_ref', 0) or stats.get('total_fo_form_usage', 0):
        print(f"\n  ФО: {stats.get('total_functional_options', 0)}, content_ref: {stats.get('total_fo_content_ref', 0)}, form_usage: {stats.get('total_fo_form_usage', 0)}")
    if stats.get('total_scheduled_jobs', 0):
        print(f"\n  Регл. задания: {stats.get('total_scheduled_jobs', 0)}")

    db.close()
    print(f"\nБаза создана: {db_path}")


__all__ = ['DatabaseManager', 'format_build_error', '_replace_file_with_retry', 'test_database_creation']
