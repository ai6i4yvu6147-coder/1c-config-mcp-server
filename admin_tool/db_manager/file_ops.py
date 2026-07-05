import os
import time
from pathlib import Path

_SQLITE_SIDECAR_SUFFIXES = ('-wal', '-shm')


def _sqlite_sidecar_paths(db_path):
    p = Path(db_path)
    return [p.parent / (p.name + suffix) for suffix in _SQLITE_SIDECAR_SUFFIXES]


def _remove_sqlite_sidecars(db_path):
    for sidecar in _sqlite_sidecar_paths(db_path):
        sidecar.unlink(missing_ok=True)


def _unlink_with_retry(path, retries=10, delay=0.05):
    """Удаление файла с повторами (Windows может держать handle после close SQLite)."""
    p = Path(path)
    if not p.exists():
        return
    last_err = None
    for attempt in range(retries):
        try:
            p.unlink()
            return
        except OSError as exc:
            last_err = exc
            retryable = (
                getattr(exc, 'winerror', None) in (32, 5)
                or exc.errno in (16, 26)
            )
            if not retryable:
                raise
            if attempt + 1 < retries:
                time.sleep(delay)
    raise last_err


def _remove_db_file(db_path):
    """Удалить .db и sidecar-файлы SQLite (-wal, -shm)."""
    _remove_sqlite_sidecars(db_path)
    _unlink_with_retry(db_path)


def _replace_file_with_retry(src, dst, retries=10, delay=0.05):
    """os.replace с повторами: на Windows файл может освобождаться с задержкой."""
    last_err = None
    for attempt in range(retries):
        try:
            os.replace(src, dst)
            return
        except OSError as exc:
            last_err = exc
            retryable = (
                getattr(exc, 'winerror', None) in (32, 5)
                or exc.errno in (16, 26)
            )
            if not retryable:
                raise
            if attempt + 1 < retries:
                time.sleep(delay)
    raise last_err


def format_build_error(exc):
    """Вернуть исходную ошибку сборки, если WinError 32 при очистке .tmp маскирует её."""
    root = exc.__cause__
    if root is None and exc.__context__ is not None and exc.__context__ is not exc:
        root = exc.__context__
    if root is not None and root is not exc:
        cleanup_hint = str(exc)
        if 'WinError 32' in cleanup_hint or 'WinError 5' in cleanup_hint:
            return (
                f'{root}\n\n'
                f'Дополнительно при освобождении временного файла: {cleanup_hint}'
            )
        return f'{root}\n\nПри очистке: {cleanup_hint}'
    return str(exc)
