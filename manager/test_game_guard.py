"""Offline fixtures for Steam updates, mixed IL2CPP files and same-build native backups."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

import game_guard
import loader_setup

Game = runpy.run_path(str(Path(__file__).with_name('modman.pyw')))['Game']


class GameGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / 'steamapps/common/Sprocket'
        self.root.mkdir(parents=True)
        (self.root / 'Sprocket.exe').write_bytes(b'exe')
        self.native = self.root / game_guard.NATIVE
        self.native.write_bytes(b'old native')
        self.metadata = self.root / game_guard.METADATA
        self.metadata.parent.mkdir(parents=True)
        self.metadata.write_bytes(b'old metadata')
        self.hash = game_guard.digest(self.native)
        self.metadata_hash = game_guard.digest(self.metadata)
        constants = patch.multiple(game_guard, GAME_HASH=self.hash, METADATA_HASH=self.metadata_hash)
        constants.start()
        self.addCleanup(constants.stop)
        native_constant = patch.object(loader_setup, 'GAME_HASH', self.hash.lower())
        native_constant.start()
        self.addCleanup(native_constant.stop)
        self.build()
        self.game = Game(self.home / 'manager', 'Sprocket', self.root, 'Sprocket.exe',
                         protect=[game_guard.NATIVE], originals={game_guard.NATIVE: [self.hash]})

    def build(self, number='25392405', manifest='2900396840838466543'):
        (self.root.parent.parent / 'appmanifest_1674170.acf').write_text(
            f'"AppState" {{ "appid" "1674170" "installdir" "Sprocket" '
            f'"buildid" "{number}" "InstalledDepots" {{ "1674171" {{ "manifest" "{manifest}" }} }} }}')

    def guard(self):
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'original')])
        return self.game.backup / '_originals' / game_guard.NATIVE

    def test_supported_pair_accepts_before_download(self):
        with patch.object(game_guard, 'trace_failure', return_value=None):
            loader_setup.validate_game(self.game, lambda _: [])
        self.assertFalse((self.home / 'manager/loader-cache').exists())

    def test_untraceable_build_refused_with_the_reason(self):
        with patch.object(game_guard, 'trace_failure', return_value='Class::Init not found'):
            with self.assertRaisesRegex(RuntimeError, r'not supported by the loader.*Class::Init not found'):
                loader_setup.validate_game(self.game, lambda _: [])

    def test_real_game_builds_trace(self):
        # Real GameAssembly.dll files listed in MODMAN_TEST_GAME_ASSEMBLIES (';'-separated); never distributed.
        paths = [p for p in os.environ.get('MODMAN_TEST_GAME_ASSEMBLIES', '').split(';') if p]
        if not paths:
            self.skipTest('set MODMAN_TEST_GAME_ASSEMBLIES to GameAssembly.dll paths')
        for path in paths:
            self.assertIsNone(game_guard.trace_failure(path), path)
        self.assertEqual(game_guard.trace_failure(self.native), 'unreadable GameAssembly')

    def test_old_native_with_new_metadata_refused_without_backup_mutation(self):
        backup = self.guard()
        self.build('25808118', '3052560297148110237')
        self.metadata.write_bytes(b'new metadata')
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'update')])
        with self.assertRaisesRegex(RuntimeError, 'different builds'):
            self.game.restore_original(game_guard.NATIVE)
        with self.assertRaisesRegex(RuntimeError, 'different builds'):
            self.game.trust(game_guard.NATIVE)
        with self.assertRaisesRegex(RuntimeError, 'different builds'):
            loader_setup.validate_game(self.game, lambda _: [])
        self.assertEqual(backup.read_bytes(), b'old native')
        self.assertEqual(self.metadata.read_bytes(), b'new metadata')

    def test_changed_steam_build_refuses_old_backup_even_when_native_still_old(self):
        backup = self.guard()
        self.build('25808118', '3052560297148110237')
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'update')])
        with self.assertRaisesRegex(RuntimeError, 'Steam updated'):
            self.game.restore_original(game_guard.NATIVE)
        self.assertEqual(backup.read_bytes(), self.native.read_bytes())

    def test_updated_native_preserved_and_not_accepted_by_loader(self):
        backup = self.guard()
        self.build('25808118', '3052560297148110237')
        self.native.write_bytes(b'new native')
        self.metadata.write_bytes(b'new metadata')
        with self.assertRaisesRegex(RuntimeError, 'Steam updated'):
            self.game.restore_original(game_guard.NATIVE)
        with self.assertRaisesRegex(RuntimeError, 'not supported'):
            loader_setup.validate_game(self.game, lambda _: [])
        self.assertEqual(self.native.read_bytes(), b'new native')
        self.assertEqual(backup.read_bytes(), b'old native')

    def test_verified_update_can_be_recorded_preserving_previous_original(self):
        backup = self.guard()
        self.build('25808118', '3052560297148110237')
        self.native.write_bytes(b'new native')
        self.metadata.write_bytes(b'new metadata')
        self.game.trust(game_guard.NATIVE)
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'original')])
        self.assertEqual(backup.read_bytes(), b'new native')
        previous = backup.with_name(backup.name + '.' + self.hash + '.previous-original')
        self.assertEqual(previous.read_bytes(), b'old native')
        self.native.write_bytes(b'patched new native')
        self.game.restore_original(game_guard.NATIVE)
        self.assertEqual(self.native.read_bytes(), b'new native')

    def test_same_build_patch_restores_original(self):
        self.guard()
        self.native.write_bytes(b'patched native')
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'changed')])
        self.game.restore_original(game_guard.NATIVE)
        self.assertEqual(self.native.read_bytes(), b'old native')

    def test_metadata_change_without_steam_build_change_blocks_restore(self):
        self.guard()
        self.native.write_bytes(b'patched native')
        self.metadata.write_bytes(b'other metadata')
        with self.assertRaisesRegex(RuntimeError, 'metadata changed'):
            self.game.restore_original(game_guard.NATIVE)
        self.assertEqual(self.native.read_bytes(), b'patched native')

    def test_legacy_guard_does_not_bless_current_update(self):
        backup = self.game.backup / '_originals' / game_guard.NATIVE
        backup.parent.mkdir(parents=True)
        backup.write_bytes(b'old native')
        self.game.state.parent.mkdir(parents=True)
        self.game.state.with_name('Sprocket.guard.json').write_text(json.dumps({game_guard.NATIVE: self.hash}))
        self.build('25808118', '3052560297148110237')
        self.native.write_bytes(b'new native')
        self.metadata.write_bytes(b'new metadata')
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'update')])
        with self.assertRaisesRegex(RuntimeError, 'Steam updated'):
            self.game.restore_original(game_guard.NATIVE)
        self.assertFalse(self.game.state.with_name('Sprocket.guard-context.json').exists())

    def test_legacy_same_build_guard_migrates_and_restores(self):
        self.guard()
        context = self.game.state.with_name('Sprocket.guard-context.json')
        context.unlink()
        self.native.write_bytes(b'patched native')
        self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'changed')])
        self.assertTrue(context.exists())
        self.game.restore_original(game_guard.NATIVE)
        self.assertEqual(self.native.read_bytes(), b'old native')

    def native_mod(self):
        folder = self.game.mods_dir / 'native patch'
        folder.mkdir()
        (folder / game_guard.NATIVE).write_bytes(b'patched native')
        return folder.name

    def test_same_build_native_mod_enable_disable_keeps_existing_behavior(self):
        mod = self.native_mod()
        self.game.enable(mod)
        self.assertEqual(self.native.read_bytes(), b'patched native')
        self.game.disable(mod)
        self.assertEqual(self.native.read_bytes(), b'old native')
        self.assertNotIn(mod, self.game.enabled)

    def test_native_mod_backup_cannot_restore_across_update(self):
        mod = self.native_mod()
        self.game.enable(mod)
        self.build('25808118', '3052560297148110237')
        self.metadata.write_bytes(b'new metadata')
        with self.assertRaisesRegex(RuntimeError, 'different builds'):
            self.game.disable(mod)
        self.assertEqual(self.native.read_bytes(), b'patched native')
        self.assertIn(game_guard.NATIVE, self.game.enabled[mod])
        self.assertEqual((self.game.backup / game_guard.NATIVE).read_bytes(), b'old native')

    def test_test_copy_does_not_inherit_live_steam_manifest(self):
        self.assertIsNone(game_guard.steam_build(self.home / 'TestGame'))
        (self.root.parent.parent / 'appmanifest_1674170.acf').write_text(
            '"appid" "1674170" "installdir" "Another Game" "buildid" "25808118"')
        self.assertIsNone(game_guard.steam_build(self.root))

    def test_missing_metadata_rejected(self):
        self.metadata.unlink()
        with self.assertRaisesRegex(RuntimeError, 'metadata does not match'):
            loader_setup.validate_game(self.game, lambda _: [])

    def test_separately_traced_update_pair_accepted_but_crossed_pair_rejected(self):
        self.build('25808118', '3052560297148110237')
        self.native.write_bytes(b'new native')
        self.metadata.write_bytes(b'new metadata')
        with patch.multiple(game_guard, UPDATED_GAME_HASH=game_guard.digest(self.native),
                            UPDATED_METADATA_HASH=game_guard.digest(self.metadata)), \
                patch.object(game_guard, 'trace_failure', return_value=None):
            loader_setup.validate_game(self.game, lambda _: [])
            self.metadata.write_bytes(b'old metadata')
            with self.assertRaisesRegex(RuntimeError, 'different builds'):
                loader_setup.validate_game(self.game, lambda _: [])

    def test_new_native_with_old_metadata_cannot_be_trusted_in_test_copy(self):
        (self.root.parent.parent / 'appmanifest_1674170.acf').unlink()
        self.native.write_bytes(b'new native')
        expected_metadata = hashlib.sha256(b'new metadata').hexdigest().upper()
        with patch.multiple(game_guard, UPDATED_GAME_HASH=game_guard.digest(self.native),
                            UPDATED_METADATA_HASH=expected_metadata):
            self.assertEqual(self.game.check_files(), [(game_guard.NATIVE, 'update')])
            with self.assertRaisesRegex(RuntimeError, 'different builds'):
                self.game.trust(game_guard.NATIVE)
            self.assertFalse((self.game.backup / '_originals' / game_guard.NATIVE).exists())
            self.assertFalse(self.game.state.with_name('Sprocket.guard.json').exists())

    def test_unpublished_package_missing_locally_never_requests_network(self):
        cache = self.home / 'loader-cache'
        cache.mkdir()
        with patch.object(loader_setup, 'PATCH_PUBLISHED', False), \
                patch.object(loader_setup, 'browser_copy', return_value=None), \
                patch.object(loader_setup.urllib.request, 'urlopen') as request:
            with self.assertRaisesRegex(RuntimeError, 'has not been published yet'):
                loader_setup.download(cache, loader_setup.PATCH_NAME, loader_setup.PATCH_URL,
                                      loader_setup.PATCH_HASH, lambda _: None)
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
