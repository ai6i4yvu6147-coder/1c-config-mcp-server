"""Benchmark form insert; report slow forms.

Dev-инструмент: гоняет сборку по реальной выгрузке и печатает формы, вставка которых
заняла дольше порога. Путь к выгрузке — аргументом (`--config-xml`), в портейбл не входит.
"""
import argparse
import multiprocessing
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.xml_parser import ConfigurationParser
from admin_tool.db_manager import DatabaseManager

SLOW_SECONDS = 0.5


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--config-xml', type=Path, required=True, help='Путь к Configuration.xml выгрузки')
    parser.add_argument('--slow-seconds', type=float, default=SLOW_SECONDS)
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp()) / 'test.db'
    dm = DatabaseManager(str(tmp))
    dm.connect(journal_mode='OFF')
    dm._create_schema()

    orig_insert = dm._insert_form

    def timed_insert(cursor, object_id, form, **kwargs):
        t = time.perf_counter()
        orig_insert(cursor, object_id, form, **kwargs)
        dt = time.perf_counter() - t
        if dt > args.slow_seconds:
            print(f'SLOW insert_form {form["name"]} {dt:.1f}s')

    dm._insert_form = timed_insert

    # Разбор идёт потоком вместе со вставкой (parser-streaming-pipeline), поэтому «время
    # парсинга» отдельной строкой больше не существует — оно в stage_seconds парсера.
    print('parse + insert...')
    t0 = time.perf_counter()
    config_parser = ConfigurationParser(str(args.config_xml))
    header, objects = config_parser.parse_streaming()
    data = dict(header)
    data['objects'] = objects
    dm._insert_configuration(data)
    print(f'done {time.perf_counter() - t0:.1f}s')
    for stage, seconds in sorted(config_parser.stage_seconds.items(), key=lambda kv: -kv[1]):
        print(f'  {stage}: {seconds:.1f}s')
    dm.close()
    print(f'db: {tmp}')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
