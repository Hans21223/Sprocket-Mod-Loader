import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import loader_setup as setup

Game = runpy.run_path(str(Path(__file__).with_name('modman.pyw')))['Game']


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'game'
        self.root.mkdir()
        self.game = Game(self.home, 'test', self.root, 'Sprocket.exe')
        self.prepared = self.home / 'prepared'
        (self.prepared / 'BepInEx/core').mkdir(parents=True)
        (self.prepared / 'BepInEx/core/bridge.dll').write_bytes(b'patched')
        (self.prepared / 'winhttp.dll').write_bytes(b'loader')

    def install(self):
        return setup.install_prepared(self.game, self.home, self.prepared)

    def test_install_repeat_disable_restores_original(self):
        (self.root / 'winhttp.dll').write_bytes(b'original')
        self.install()
        self.assertEqual((self.root / 'winhttp.dll').read_bytes(), b'loader')
        self.assertIn('already installed', self.install())
        self.game.disable(setup.MOD)
        self.assertEqual((self.root / 'winhttp.dll').read_bytes(), b'original')
        self.assertFalse((self.root / 'BepInEx/core/bridge.dll').exists())

    def test_migrate_loader_keeps_gameplay_mod(self):
        old = self.game.mods_dir / 'old loader'
        old.mkdir()
        (old / 'winhttp.dll').write_bytes(b'old')
        self.game.enable(old.name)
        mod = self.game.mods_dir / 'gameplay'
        mod.mkdir()
        (mod / 'part.json').write_bytes(b'part')
        self.game.enable(mod.name)
        self.install()
        self.assertEqual(set(self.game.enabled), {setup.MOD, 'gameplay'})
        self.assertEqual((self.root / 'part.json').read_bytes(), b'part')

    def test_mid_install_failure_restores_bytes_state_and_timestamps(self):
        (self.root / 'winhttp.dll').write_bytes(b'original')
        before = (self.root / 'winhttp.dll').stat().st_mtime_ns
        real_enable = self.game.enable
        def broken(mod):
            real_enable(mod)
            raise OSError('simulated failure after copy')
        self.game.enable = broken
        with self.assertRaisesRegex(RuntimeError, 'previous files restored'):
            self.install()
        self.assertEqual((self.root / 'winhttp.dll').read_bytes(), b'original')
        self.assertEqual((self.root / 'winhttp.dll').stat().st_mtime_ns, before)
        self.assertEqual(self.game.enabled, {})
        self.assertFalse(self.game.state.exists())
        self.assertFalse((self.root / 'BepInEx/core/bridge.dll').exists())

    def test_failure_during_upgrade_restores_old_entry(self):
        self.install()
        before = self.game.state.read_bytes()
        (self.prepared / 'winhttp.dll').write_bytes(b'new version')
        real_enable = self.game.enable
        def broken(mod):
            real_enable(mod)
            raise OSError('upgrade failed')
        self.game.enable = broken
        with self.assertRaisesRegex(RuntimeError, 'previous files restored'):
            self.install()
        self.assertEqual(self.game.state.read_bytes(), before)
        self.assertEqual((self.root / 'winhttp.dll').read_bytes(), b'loader')
        self.assertEqual((self.game.mods_dir / setup.MOD / 'winhttp.dll').read_bytes(), b'loader')

    def test_mixed_mod_conflict_is_not_disabled(self):
        mod = self.game.mods_dir / 'mixed'
        mod.mkdir()
        (mod / 'winhttp.dll').write_bytes(b'other')
        (mod / 'tank.blueprint').write_bytes(b'user content')
        self.game.enable(mod.name)
        with self.assertRaisesRegex(RuntimeError, 'other content'):
            self.install()
        self.assertIn('mixed', self.game.enabled)
        self.assertEqual((self.root / 'tank.blueprint').read_bytes(), b'user content')

    def test_edited_file_is_recoverable_after_disable(self):
        self.install()
        (self.root / 'winhttp.dll').write_bytes(b'edited')
        self.install()
        self.game.disable(setup.MOD)
        self.assertEqual((self.root / 'winhttp.dll').read_bytes(), b'edited')

    def test_running_and_wrong_game_fail_before_download(self):
        (self.root / 'Sprocket.exe').touch()
        (self.root / 'GameAssembly.dll').write_bytes(b'unsupported')
        with self.assertRaisesRegex(RuntimeError, 'Close Sprocket'):
            setup.validate_game(self.game, lambda _: [123])
        with self.assertRaisesRegex(RuntimeError, 'not supported'):
            setup.validate_game(self.game, lambda _: [])
        self.assertFalse((self.home / 'loader-cache').exists())

    def test_checksum_and_archive_traversal(self):
        with self.assertRaisesRegex(RuntimeError, 'Checksum failed'):
            setup.verify(self.prepared / 'winhttp.dll', 'wrong')
        archive = self.home / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('../escaped', b'bad')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe path'):
            setup.extract(archive, self.prepared)
        self.assertFalse((self.home / 'escaped').exists())

    def test_failed_download_leaves_no_cached_package(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): raise OSError('network disconnected')
        with patch('urllib.request.urlopen', return_value=Response()):
            with self.assertRaises(OSError):
                setup.download(self.home, 'download.zip', 'https://example.com/test.zip', 'hash', lambda _: None)
        self.assertFalse((self.home / 'download.zip').exists())
        self.assertFalse((self.home / 'download.download').exists())


if __name__ == '__main__':
    unittest.main()
