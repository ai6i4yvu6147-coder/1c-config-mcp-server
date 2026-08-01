"""gui-bulk-update: отбор целей и оркестрация массового обновления (без Tk)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_tool import bulk_update
from admin_tool.bulk_update import (
    SCOPE_ALL,
    SCOPE_OUTDATED,
    collect_bulk_targets,
    run_bulk_update,
)
from shared.indexer_version import INDEXER_VERSION


class FakeProjectManager:
    def __init__(self, projects):
        self._projects = projects

    def get_all_projects(self):
        return self._projects


def _db(db_id, name, db_file, source_xml=None):
    record = {'id': db_id, 'name': name, 'type': 'base', 'db_file': db_file}
    if source_xml is not None:
        record['source_xml'] = str(source_xml)
    return record


class BulkTargetSelectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_dir = self.tmp / 'databases'
        self.db_dir.mkdir()
        self.source_dir = self.tmp / 'export'
        self.source_dir.mkdir()
        self.config_xml = self.source_dir / 'Configuration.xml'
        self.config_xml.write_text('<MetaDataObject/>', encoding='utf-8')

        self._versions = {}
        self._orig_read_version = bulk_update.DatabaseManager.read_db_version
        bulk_update.DatabaseManager.read_db_version = staticmethod(
            lambda db_path: self._versions.get(Path(db_path).name)
        )

    def tearDown(self):
        bulk_update.DatabaseManager.read_db_version = self._orig_read_version
        self._tmp.cleanup()

    def _pm(self, databases):
        return FakeProjectManager([{'id': 'p1', 'name': 'Проект', 'databases': databases}])

    def test_outdated_scope_skips_current_version(self):
        self._versions['fresh.db'] = INDEXER_VERSION
        self._versions['old.db'] = INDEXER_VERSION - 1
        pm = self._pm([
            _db('d1', 'Свежая', 'fresh.db', self.config_xml),
            _db('d2', 'Старая', 'old.db', self.config_xml),
        ])

        targets = collect_bulk_targets(pm, self.db_dir, scope=SCOPE_OUTDATED)

        self.assertEqual([t.db_name for t in targets], ['Свежая', 'Старая'])
        fresh, old = targets
        self.assertFalse(fresh.is_actionable)
        self.assertIn(f'v{INDEXER_VERSION}', fresh.skip_reason)
        self.assertTrue(old.is_actionable)

    def test_all_scope_includes_current_version(self):
        self._versions['fresh.db'] = INDEXER_VERSION
        pm = self._pm([_db('d1', 'Свежая', 'fresh.db', self.config_xml)])

        targets = collect_bulk_targets(pm, self.db_dir, scope=SCOPE_ALL)

        self.assertTrue(targets[0].is_actionable)
        self.assertEqual(targets[0].config_xml, str(self.config_xml))

    def test_missing_db_file_is_actionable(self):
        """Базы без файла (version is None) — тоже цель: их надо собрать."""
        pm = self._pm([_db('d1', 'Нет файла', 'absent.db', self.config_xml)])

        targets = collect_bulk_targets(pm, self.db_dir, scope=SCOPE_OUTDATED)

        self.assertIsNone(targets[0].db_version)
        self.assertTrue(targets[0].is_actionable)

    def test_missing_source_is_skipped_with_reason(self):
        self._versions['old.db'] = INDEXER_VERSION - 1
        pm = self._pm([_db('d1', 'Без источника', 'old.db', self.tmp / 'gone' / 'Configuration.xml')])

        targets = collect_bulk_targets(pm, self.db_dir, scope=SCOPE_OUTDATED)

        self.assertFalse(targets[0].is_actionable)
        self.assertIn('источник не найден', targets[0].skip_reason)

    def test_db_newer_than_app_is_never_rebuilt(self):
        """Пересборка старым ПО понизила бы формат индекса — не побочный эффект массовой операции."""
        self._versions['new.db'] = INDEXER_VERSION + 1
        pm = self._pm([_db('d1', 'Новее ПО', 'new.db', self.config_xml)])

        for scope in (SCOPE_OUTDATED, SCOPE_ALL):
            targets = collect_bulk_targets(pm, self.db_dir, scope=scope)
            self.assertFalse(targets[0].is_actionable, scope)
            self.assertIn('новее ПО', targets[0].skip_reason)

    def test_project_filter_limits_scope(self):
        self._versions['a.db'] = INDEXER_VERSION - 1
        self._versions['b.db'] = INDEXER_VERSION - 1
        pm = FakeProjectManager([
            {'id': 'p1', 'name': 'Первый', 'databases': [_db('d1', 'A', 'a.db', self.config_xml)]},
            {'id': 'p2', 'name': 'Второй', 'databases': [_db('d2', 'B', 'b.db', self.config_xml)]},
        ])

        all_targets = collect_bulk_targets(pm, self.db_dir, scope=SCOPE_OUTDATED)
        one_project = collect_bulk_targets(pm, self.db_dir, project_id='p2', scope=SCOPE_OUTDATED)

        self.assertEqual(len(all_targets), 2)
        self.assertEqual([t.label for t in one_project], ['Второй / B'])


class BulkRunTest(unittest.TestCase):
    def setUp(self):
        self._orig_build = bulk_update.DatabaseManager.build_from_xml_atomic
        self.built = []

    def tearDown(self):
        bulk_update.DatabaseManager.build_from_xml_atomic = self._orig_build

    def _target(self, name, skip_reason=None):
        return bulk_update.BulkTarget(
            project_id='p1', project_name='Проект', db_id=f'id-{name}', db_name=name,
            db_file=f'{name}.db', db_path=Path(f'{name}.db'), config_xml='Configuration.xml',
            db_version=1, skip_reason=skip_reason,
        )

    def _stub_build(self, failing=()):
        def build(db_path, config_xml, progress_callback=None):
            name = Path(db_path).stem
            self.built.append(name)
            if progress_callback:
                progress_callback(0, 100, f'{name}: стадия', False)
            if name in failing:
                raise RuntimeError(f'сбой {name}')
            return True

        bulk_update.DatabaseManager.build_from_xml_atomic = staticmethod(build)

    def test_skipped_targets_are_not_built(self):
        self._stub_build()
        targets = [self._target('A'), self._target('B', skip_reason='актуальна')]

        result = run_bulk_update(targets)

        self.assertEqual(self.built, ['A'])
        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.failed, 0)

    def test_failure_does_not_stop_the_run(self):
        self._stub_build(failing={'B'})
        targets = [self._target('A'), self._target('B'), self._target('C')]

        result = run_bulk_update(targets)

        self.assertEqual(self.built, ['A', 'B', 'C'])
        self.assertEqual((result.succeeded, result.failed), (2, 1))
        self.assertEqual(len(result.failures), 1)
        self.assertIn('Проект / B', result.failures[0][0])
        self.assertIn('сбой B', result.failures[0][1])
        self.assertFalse(result.stopped_early)

    def test_stop_request_ends_run_between_databases(self):
        self._stub_build()
        targets = [self._target('A'), self._target('B'), self._target('C')]
        stop = {'value': False}

        def on_db_finish(target, ok, error_text):
            if target.db_name == 'A':
                stop['value'] = True

        result = run_bulk_update(
            targets, on_db_finish=on_db_finish, should_stop=lambda: stop['value']
        )

        self.assertEqual(self.built, ['A'])
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.succeeded, 1)

    def test_callbacks_report_position_and_progress(self):
        self._stub_build()
        starts, progress = [], []
        targets = [self._target('A'), self._target('B', skip_reason='пропуск'), self._target('C')]

        run_bulk_update(
            targets,
            on_db_start=lambda i, total, t: starts.append((i, total, t.db_name)),
            on_progress=lambda t, cur, total, msg, repl: progress.append((t.db_name, msg)),
        )

        self.assertEqual(starts, [(1, 2, 'A'), (2, 2, 'C')])
        self.assertEqual(progress, [('A', 'A: стадия'), ('C', 'C: стадия')])


if __name__ == '__main__':
    unittest.main()
