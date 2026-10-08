"""Disable must remove known mod code, preserve user edits, and keep failures accurately tracked."""
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


module = runpy.run_path(str(Path(__file__).with_name('modman.pyw')))
Game, stamp = module['Game'], module['stamp']


class DisableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'game'
        self.root.mkdir()
        self.game = Game(self.home, 'test', self.root, route={'BepInEx': ''})
        self.mod = 'example'
        self.rel = 'BepInEx/plugins/example/Example.dll'

    def file(self, base, rel, content):
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def source(self, rel, content):
        return self.file(self.game.mods_dir / self.mod, rel, content)

    def enable(self, content=b'known mod'):
        self.source(self.rel, content)
        self.game.enable(self.mod)
        return self.root / self.rel

    def saved_state(self):
        return json.loads(self.game.state.read_text())

    def test_preinstalled_identical_plugin_does_not_restore_itself(self):
        self.file(self.root, self.rel, b'known mod')
        destination = self.enable()
        backup = self.game.backup / self.rel
        self.assertEqual(backup.read_bytes(), destination.read_bytes())
        self.assertEqual(self.game.disable(self.mod), [])
        self.assertFalse(destination.exists())
        self.assertFalse(backup.exists())
        self.assertEqual(backup.with_name(backup.name + '.disabled-copy').read_bytes(), b'known mod')
        self.assertNotIn(self.mod, self.saved_state())

    def test_timestamp_only_change_does_not_keep_known_plugin(self):
        destination = self.enable()
        installed = stamp(destination)
        os.utime(destination, ns=(installed[1] + 1_000_000_000, installed[1] + 1_000_000_000))
        self.assertNotEqual(stamp(destination), installed)
        self.game.disable(self.mod)
        self.assertFalse(destination.exists())
        self.assertNotIn(self.mod, self.saved_state())

    def test_unknown_modified_plugin_remains_tracked_and_reports_partial_disable(self):
        data = 'tank.blueprint'
        self.source(data, b'starter')
        self.file(self.root, self.rel, b'known mod')
        destination = self.enable()
        destination.write_bytes(b'unknown replacement')
        with self.assertRaisesRegex(RuntimeError, 'not fully disabled'):
            self.game.disable(self.mod)
        self.assertEqual(destination.read_bytes(), b'unknown replacement')
        self.assertEqual(set(self.saved_state()[self.mod]), {self.rel})
        self.assertEqual((self.game.backup / self.rel).read_bytes(), b'known mod')
        self.assertFalse((self.root / data).exists())
        destination.unlink()
        self.game.disable(self.mod)
        self.assertNotIn(self.mod, self.saved_state())

    def test_archiving_duplicate_does_not_overwrite_previous_recovery_copy(self):
        self.file(self.root, self.rel, b'known mod')
        destination = self.enable()
        backup = self.game.backup / self.rel
        previous = backup.with_name(backup.name + '.disabled-copy')
        previous.write_bytes(b'previous recovery copy')
        self.game.disable(self.mod)
        self.assertFalse(destination.exists())
        self.assertEqual(previous.read_bytes(), b'previous recovery copy')
        self.assertEqual(backup.with_name(backup.name + '.disabled-copy.1').read_bytes(), b'known mod')

    def test_edited_blueprint_and_original_backup_remain_recoverable(self):
        data = 'tank.blueprint'
        self.file(self.root, data, b'original tank')
        self.source(data, b'starter')
        self.enable()
        destination = self.root / data
        destination.write_bytes(b'player edits')
        self.assertEqual(self.game.disable(self.mod), [data])
        self.assertEqual(destination.read_bytes(), b'player edits')
        backup = self.game.backup / data
        self.assertEqual(backup.with_name(backup.name + '.kept').read_bytes(), b'original tank')
        self.assertNotIn(self.mod, self.saved_state())

    def test_distinct_original_plugin_is_restored(self):
        self.file(self.root, self.rel, b'other original code')
        destination = self.enable()
        self.game.disable(self.mod)
        self.assertEqual(destination.read_bytes(), b'other original code')
        self.assertNotIn(self.mod, self.saved_state())

    def test_locked_plugin_retains_record_and_retry_removes_it(self):
        self.file(self.root, self.rel, b'known mod')
        destination = self.enable()
        real_unlink = Path.unlink

        def locked(path, *args, **kwargs):
            if path == destination:
                raise PermissionError('simulated Windows sharing violation')
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', locked):
            with self.assertRaisesRegex(RuntimeError, 'Close the game'):
                self.game.disable(self.mod)
        self.assertTrue(destination.exists())
        self.assertEqual(set(self.saved_state()[self.mod]), {self.rel})
        self.game.disable(self.mod)
        self.assertFalse(destination.exists())
        self.assertNotIn(self.mod, self.saved_state())

    def test_shared_plugin_remains_until_last_owner_disables_it(self):
        self.enable()
        other = self.game.mods_dir / 'other'
        self.file(other, self.rel, b'known mod')
        self.game.enable('other')
        self.game.disable(self.mod)
        self.assertTrue((self.root / self.rel).exists())
        self.game.disable('other')
        self.assertFalse((self.root / self.rel).exists())
        self.assertEqual(self.saved_state(), {})


if __name__ == '__main__':
    unittest.main()
