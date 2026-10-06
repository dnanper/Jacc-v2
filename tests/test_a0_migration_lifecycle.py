"""Regression for the preparation script, no benchmark, DB writes or model calls."""
import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src/modules'), str(ROOT / '.tmp')]
SCRIPT = ROOT / '.tmp/build_development12_v2.py'
spec = importlib.util.spec_from_file_location('development_builder', SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MigrationLifecycleTest(unittest.TestCase):
    def test_no_reset_while_backup_connection_is_held(self):
        tree = ast.parse(SCRIPT.read_text())
        one = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'one')
        for node in ast.walk(one):
            if isinstance(node, ast.With):
                calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                self.assertNotIn('prepare_ckg', calls)
        calls = [n for n in one.body if isinstance(n, ast.If) and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == 'close' for c in ast.walk(n))]
        self.assertTrue(calls)

    def test_recovery_preserves_working_sidecars_and_original_backup(self):
        with tempfile.TemporaryDirectory() as root:
            storage, backup = Path(root) / 'working', Path(root) / 'backup'
            storage.mkdir(); backup.mkdir()
            (storage / 'lbug').write_text('partial new db')
            (storage / 'lbug.wal').write_text('old database wal')
            (backup / 'lbug').write_text('original db')
            (backup / 'graph.json').write_text('{}')
            (backup / 'backup_complete.json').write_text(json.dumps({'source_path': str(storage), 'base_commit': 'base'}))
            destination = builder.quarantine_failed(storage, backup, {'id': 'synthetic', 'base_commit': 'base'})
            self.assertFalse(storage.exists())
            self.assertEqual((destination / 'lbug.wal').read_text(), 'old database wal')
            self.assertEqual((backup / 'lbug').read_text(), 'original db')

    def test_wrong_backup_never_moves_current_cache(self):
        with tempfile.TemporaryDirectory() as root:
            storage, backup = Path(root) / 'working', Path(root) / 'backup'
            storage.mkdir(); backup.mkdir()
            (storage / 'lbug.wal').write_text('preserve')
            (backup / 'backup_complete.json').write_text(json.dumps({'source_path': str(storage), 'base_commit': 'other'}))
            with self.assertRaises(RuntimeError):
                builder.quarantine_failed(storage, backup, {'id': 'synthetic', 'base_commit': 'base'})
            self.assertTrue(storage.exists())
            self.assertEqual((storage / 'lbug.wal').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
