import hashlib
import io
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

    def test_remove_mod_restores_game_and_deletes_copy(self):
        (self.root / 'part.json').write_bytes(b'original')
        mod = self.game.mods_dir / 'gameplay'
        mod.mkdir()
        (mod / 'part.json').write_bytes(b'modded')
        self.game.enable(mod.name)
        self.game.remove(mod.name)
        self.assertEqual((self.root / 'part.json').read_bytes(), b'original')
        self.assertFalse(mod.exists())
        self.assertNotIn('gameplay', self.game.enabled)
        self.assertNotIn('gameplay', self.game.mods())
        with self.assertRaisesRegex(RuntimeError, 'Refusing'):
            self.game.remove('..')

    def test_remove_all_leaves_an_unmodded_game(self):
        game = Game(self.home, 'sprocket', self.root, 'Sprocket.exe')
        (self.root / 'GameAssembly.dll').write_bytes(b'game')
        (self.root / 'winhttp.dll').write_bytes(b'original')
        self.game = game
        self.install()  # the loader entry
        mod = game.mods_dir / 'gameplay'
        (mod / 'BepInEx/plugins').mkdir(parents=True)
        (mod / 'BepInEx/plugins/Plugin.dll').write_bytes(b'mod')
        game.enable(mod.name)
        (self.root / 'BepInEx/interop').mkdir()  # generated on first launch; no mod owns it
        (self.root / 'BepInEx/interop/Assembly-CSharp.dll').write_bytes(b'generated')
        (self.root / 'changelog.txt').write_text('BepInEx 6.0.0-be.788 changes')
        kept, gone = game.remove_all(setup.MOD)
        self.assertEqual((kept, game.enabled, game.mods()), ([], {}, []))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['GameAssembly.dll'])
        self.assertIn(self.root / 'changelog.txt', gone)

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
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): raise OSError('network disconnected')
        with patch('urllib.request.urlopen', return_value=Response()):
            with self.assertRaisesRegex(RuntimeError, 'network disconnected(.|\n)*https://example.com/test.zip'):
                setup.download(self.home, 'download.zip', 'https://example.com/test.zip', 'hash', lambda _: None, [])
        self.assertFalse((self.home / 'download.zip').exists())
        self.assertFalse((self.home / 'download.download').exists())


class DownloadTests(unittest.TestCase):
    """A download that goes wrong is tried again and explained; a copy saved by a browser is used instead."""
    GOOD = b'PK\x03\x04 the real package'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'loader-cache'
        self.cache.mkdir()
        self.hash = hashlib.sha256(self.GOOD).hexdigest()

    def responses(self, *bodies):
        """urlopen answering with these bodies in turn: (data, Content-Length) each."""
        answers = iter(bodies)
        def urlopen(*args, **kwargs):
            data, length = next(answers)
            response = io.BytesIO(data)
            response.headers = {'Content-Length': str(length)}
            return response
        return patch('urllib.request.urlopen', urlopen)

    def get(self, folders=()):
        return setup.download(self.cache, 'Package-1.0+abc.zip', 'https://example.com/p.zip', self.hash,
                              lambda _: None, list(folders))

    def test_cut_off_download_is_tried_again(self):
        with self.responses((self.GOOD[:5], len(self.GOOD)), (self.GOOD, len(self.GOOD))):
            self.assertEqual(self.get().read_bytes(), self.GOOD)

    def test_explains_cut_off_and_blocked_downloads(self):
        with self.responses(*[(self.GOOD[:5], len(self.GOOD))] * 3):
            with self.assertRaisesRegex(RuntimeError, f'cut off \\(5 of {len(self.GOOD)} bytes\\)(.|\n)*https://example.com/p.zip'):
                self.get()
        with self.responses(*[(b'<html>Blocked</html>', 20)] * 3):
            with self.assertRaisesRegex(RuntimeError, 'web page arrived'):
                self.get()
        with self.responses(*[(b'PK\x03\x04 another file', 17)] * 3):
            with self.assertRaisesRegex(RuntimeError, 'different from the official one'):
                self.get()
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_uses_a_copy_saved_by_the_browser(self):
        downloads = Path(self.temp.name) / 'Downloads'
        downloads.mkdir()
        (downloads / 'Package-1.0+abc.zip').write_bytes(b'PK wrong one')
        (downloads / 'Package-1.0%2Babc (1).zip').write_bytes(self.GOOD)
        with patch('urllib.request.urlopen', side_effect=AssertionError('no download needed')):
            self.assertEqual(self.get([downloads]).read_bytes(), self.GOOD)
            self.assertEqual(self.get().read_bytes(), self.GOOD)  # cached from now on

    def test_damaged_cached_copy_is_downloaded_again(self):
        (self.cache / 'Package-1.0+abc.zip').write_bytes(b'damaged')
        with self.responses((self.GOOD, len(self.GOOD))):
            self.assertEqual(self.get().read_bytes(), self.GOOD)


class OneClickTests(unittest.TestCase):
    """Install mod loader finds the game and MLLoader by itself, and works without MLLoader for BepInEx mods."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'game'
        self.root.mkdir()
        self.game = Game(self.home, 'test', self.root, 'Sprocket.exe')
        self.base = self.zip('base.zip', {'winhttp.dll': b'doorstop', 'doorstop_config.ini': b'config',
                                          'BepInEx/core/Il2CppInterop.HarmonySupport.dll': b'upstream'})
        self.patch = self.zip('patch.zip', {'Sprocket-Mod-Loader-1.2.1/Patch/BepInEx/core/Il2CppInterop.HarmonySupport.dll':
                                            b'patched',
                                         'Sprocket-Mod-Loader-1.2.1/Patch/BepInEx/core/Il2CppInterop.Generator.dll':
                                            b'ui-generator'})
        self.melon = self.zip('downloads/MLLoader IL2CPP BepInEx6 V0.7.3-26-2-3-9.zip', {
            'BepInEx/patchers/BepInEx.MelonLoader.Loader.Patcher.dll': b'patcher',
            'BepInEx/core/Il2CppInterop.Generator.dll': b'older-generator',
            'MLLoader/MelonLoader/MelonLoader.dll': b'melon'})
        # Stand-in packages: no network, and any game folder counts as the supported build.
        for name, value in (('MELON_HASH', setup.digest(self.melon)), ('validate_game', lambda game, running: None),
                            ('download', lambda cache, name, *args: self.base if name == setup.BASE_NAME else self.patch)):
            patcher = patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def zip(self, name, files):
        path = self.home / 'sources' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, 'w') as z:
            for member, data in files.items():
                z.writestr(member, data)
        return path

    def test_finds_sprocket_in_another_steam_library(self):
        steam, library = self.home / 'Steam', self.home / 'D Drive' / 'SteamLibrary'
        (steam / 'steamapps').mkdir(parents=True)
        (steam / 'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n'
            % (str(steam).replace('\\', '\\\\'), str(library).replace('\\', '\\\\')))
        self.assertIsNone(setup.find_sprocket(setup.steam_libraries([steam])))
        game = library / 'steamapps/common/Sprocket'
        game.mkdir(parents=True)
        (game / 'Sprocket.exe').write_bytes(b'')
        self.assertEqual(setup.find_sprocket(setup.steam_libraries([steam])), game)

    def test_finds_downloaded_mlloader_and_caches_it(self):
        other = self.zip('downloads/MelonLoader.x64.zip', {'version.dll': b'not MLLoader'})
        self.assertIsNone(setup.find_melon(self.home, [other.parent.parent]))  # not in the searched folder itself
        found = setup.find_melon(self.home, [self.melon.parent])
        self.assertEqual(found, self.home / 'loader-cache' / setup.MELON_CACHE)
        self.assertEqual(found.read_bytes(), self.melon.read_bytes())
        self.assertEqual(setup.find_melon(self.home, []), found)  # cached from now on

    def test_installs_without_mlloader_then_adds_it(self):
        result = setup.install(self.game, self.home, None, lambda _: [])
        self.assertIn('MLLoader was left out', result)
        self.assertEqual((self.root / 'BepInEx/core/Il2CppInterop.HarmonySupport.dll').read_bytes(), b'patched')
        self.assertEqual((self.root / 'BepInEx/core/Il2CppInterop.Generator.dll').read_bytes(), b'ui-generator')
        self.assertFalse((self.root / 'MLLoader').exists())
        self.assertFalse(setup.needs_melon(self.game))
        (self.home / 'loader-cache' / setup.MELON_CACHE).write_bytes(b'damaged copy')  # ignored, not an error
        self.assertIn('MLLoader was left out', setup.install(self.game, self.home, None, lambda _: []))
        result = setup.install(self.game, self.home, self.melon, lambda _: [])
        self.assertNotIn('left out', result)
        self.assertEqual((self.root / 'MLLoader/MelonLoader/MelonLoader.dll').read_bytes(), b'melon')
        self.assertEqual((self.root / 'BepInEx/core/Il2CppInterop.HarmonySupport.dll').read_bytes(), b'patched')
        self.assertEqual(list(self.game.enabled), [setup.MOD])

    def test_never_drops_mlloader_that_melon_mods_use(self):
        setup.install(self.game, self.home, self.melon, lambda _: [])
        (self.home / 'loader-cache' / setup.MELON_CACHE).unlink()
        self.assertTrue(setup.needs_melon(self.game))
        with self.assertRaisesRegex(RuntimeError, 'need MLLoader'):
            setup.install(self.game, self.home, None, lambda _: [])
        self.assertEqual((self.root / 'MLLoader/MelonLoader/MelonLoader.dll').read_bytes(), b'melon')

    def test_ui_generator_is_authoritative_after_mlloader_overlay(self):
        setup.install(self.game, self.home, self.melon, lambda _: [])
        self.assertEqual((self.root / 'BepInEx/core/Il2CppInterop.Generator.dll').read_bytes(), b'ui-generator')

    def test_missing_ui_generator_fails_before_installing(self):
        self.patch = self.zip('patch-missing-generator.zip', {
            'Sprocket-Mod-Loader-1.2.1/Patch/BepInEx/core/Il2CppInterop.HarmonySupport.dll': b'patched'})
        with self.assertRaisesRegex(RuntimeError, 'missing BepInEx/core/Il2CppInterop.Generator.dll'):
            setup.install(self.game, self.home, None, lambda _: [])
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.game.enabled, {})


if __name__ == '__main__':
    unittest.main()
