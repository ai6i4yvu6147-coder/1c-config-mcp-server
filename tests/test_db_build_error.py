import sqlite3
import tempfile
import unittest
from pathlib import Path

from admin_tool.db_manager import DatabaseManager, format_build_error
from shared.db_build_state import tmp_db_path


class TestFormatBuildError(unittest.TestCase):
    def test_shows_root_cause_masked_by_winerror_32(self):
        try:
            try:
                raise ValueError('duplicate TypeDescriptor')
            except ValueError as root:
                try:
                    raise PermissionError('[WinError 32] file locked: foo.db.tmp') from root
                except PermissionError as cleanup:
                    raise cleanup
        except PermissionError as exc:
            text = format_build_error(exc)
            self.assertIn('duplicate TypeDescriptor', text)
            self.assertIn('WinError 32', text)

    def test_build_from_missing_xml_surfaces_file_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / 'test.db'
            bad_xml = Path(d) / 'missing.xml'
            with self.assertRaises(FileNotFoundError) as ctx:
                DatabaseManager.build_from_xml_atomic(db_path, str(bad_xml))
            self.assertIn('missing.xml', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
