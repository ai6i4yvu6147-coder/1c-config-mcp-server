#!/usr/bin/env python3
"""
Standalone parse/build timing benchmark (dev tool, not shipped in the portable build).

Runs the same DatabaseManager.build_from_xml_atomic() pipeline the admin GUI/CLI use,
against a real 1C export's Configuration.xml, printing timestamped per-stage lines as
they arrive plus a final statistics summary. Writes its output .db to a scratch temp
file (never into databases/ or projects.json) so it does not touch any real project
state; this is a timing/benchmark tool, not a substitute for the MCP verification
protocol in docs/testing-protocol.md.

Usage:
  python scripts/parse-benchmark.py --config-xml <path to Configuration.xml>
  python scripts/parse-benchmark.py --config-xml <path> --out-db <path> --keep
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin_tool.db_manager import DatabaseManager, format_build_error


def _print_progress(current: int, total: int, message: str, replace_last: bool = False) -> None:
    # replace_last is a GUI-only hint (collapse "Объекты N/M" counters into one line); the
    # benchmark log keeps every line since that's useful detail for a saved run.
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ({current:3d}/{total}) {message}")


def run_benchmark(config_xml: Path, out_db: Path) -> int:
    if not config_xml.is_file():
        print(f"Not a file: {config_xml}", file=sys.stderr)
        return 2

    print(f"Config:  {config_xml}")
    print(f"Out DB:  {out_db}")
    print()

    t_start = time.perf_counter()
    try:
        ok = DatabaseManager.build_from_xml_atomic(out_db, config_xml, progress_callback=_print_progress)
    except Exception as exc:
        print(f"\nBuild failed: {format_build_error(exc)}", file=sys.stderr)
        return 1
    total_seconds = time.perf_counter() - t_start

    if not ok:
        print("\nBuild returned false", file=sys.stderr)
        return 1

    print(f"\nTotal wall-clock time: {total_seconds:.1f} c")

    db_manager = DatabaseManager(out_db)
    db_manager.connect(journal_mode=None)
    try:
        stats = db_manager.get_statistics()
    finally:
        db_manager.close()

    print("\nStatistics:")
    print(f"  Объектов: {stats['total_objects']}")
    print(f"  Модулей: {stats['total_modules']}")
    print(f"  Атрибутов: {stats['total_attributes']} (стд: {stats['total_standard_attributes']}, "
          f"кастом: {stats['total_custom_attributes']})")
    print(f"  Колонок ТЧ: {stats['total_tabular_section_columns']}")
    print(f"  Значений перечислений: {stats['total_enum_values']}")
    print(f"  Регл. заданий: {stats['total_scheduled_jobs']}")
    print("  По типам:")
    for obj_type, count in stats["by_type"].items():
        print(f"    {obj_type}: {count}")

    return 0


def main() -> int:
    # Console codepage (e.g. cp1251) may not cover every character progress messages could
    # contain; replace instead of crashing the whole benchmark on a single unencodable char.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--config-xml", type=Path, required=True, help="Путь к Configuration.xml выгрузки")
    parser.add_argument("--out-db", type=Path, default=None, help="Путь к выходному .db (по умолчанию — временный файл)")
    parser.add_argument("--keep", action="store_true", help="Не удалять выходной .db после завершения")
    args = parser.parse_args()

    config_xml = args.config_xml.resolve()

    if args.out_db is not None:
        out_db = args.out_db.resolve()
        keep = True
    else:
        tmp_fd, tmp_name = tempfile.mkstemp(prefix="parse-benchmark-", suffix=".db")
        import os
        os.close(tmp_fd)
        out_db = Path(tmp_name)
        out_db.unlink()  # build_from_xml_atomic expects to create it itself
        keep = args.keep

    try:
        return run_benchmark(config_xml, out_db)
    finally:
        if not keep and out_db.exists():
            out_db.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm"):
                sidecar = out_db.parent / (out_db.name + suffix)
                sidecar.unlink(missing_ok=True)
        elif keep:
            print(f"\nBenchmark DB kept at: {out_db}")


if __name__ == "__main__":
    sys.exit(main())
