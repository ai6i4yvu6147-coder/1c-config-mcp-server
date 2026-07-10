"""Benchmark form insert; report slow forms."""
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser
from admin_tool.db_manager import DatabaseManager

CFG = Path(
    r'C:\Users\Alex\Documents\Работа\Общая\Выгрузки конфигураций\main'
    r'\Фитэра\АСБ тест\Основная конфигурация\Configuration.xml'
)


def main():
    print('parsing...')
    t0 = time.perf_counter()
    data = ConfigurationParser(str(CFG)).parse()
    print(f'parse {time.perf_counter() - t0:.1f}s, objects {len(data["objects"])}')

    tmp = Path(tempfile.mkdtemp()) / 'test.db'
    dm = DatabaseManager(str(tmp))
    dm.connect(journal_mode='OFF')
    dm._create_schema()

    orig_insert = dm._insert_form

    def timed_insert(cursor, object_id, object_name, form, fo_resolver=None, pending_type_slots=None):
        t = time.perf_counter()
        orig_insert(cursor, object_id, object_name, form, fo_resolver, pending_type_slots)
        dt = time.perf_counter() - t
        if dt > 0.5:
            print(f'SLOW insert_form {object_name}.{form["name"]} {dt:.1f}s')

    dm._insert_form = timed_insert

    print('insert_configuration...')
    t1 = time.perf_counter()
    dm._insert_configuration(data)
    print(f'done {time.perf_counter() - t1:.1f}s')
    dm.close()


if __name__ == '__main__':
    main()
