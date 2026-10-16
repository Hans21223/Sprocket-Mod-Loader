"""Updates: which release fits the game, which version is installed, and that an update keeps what the user added."""
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import updates

Game = runpy.run_path(str(Path(__file__).with_name('modman.pyw')))['Game']


def release(assets, compat=None, draft=False):
    body = 'Notes.' + (f'\n\n<!-- sp-compat {json.dumps({"hamish.sprocket": compat})} -->' if compat is not None else '')
    names = [n for a in assets for n in (a, a + '.sha256')]
    return {'draft': draft, 'body': body, 'assets': [{'name': n, 'browser_download_url': 'https://example/' + n} for n in names]}


class Versions(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(updates.version('1.8.8'), updates.version('1.8.8.0'))
        self.assertGreater(updates.version('1.8.10'), updates.version('1.8.9'))

    def test_fits(self):
        fits = updates.fits
        self.assertTrue(fits('>=0.2.55.5', '0.2.56.2'))
        self.assertFalse(fits('>=0.2.57', '0.2.56.2'))
        self.assertFalse(fits('0.2.56.0', '0.2.56.2'))
        self.assertTrue(fits('0.2.56', '0.2.56.2'))
        self.assertTrue(fits(['0.2.55.5', '0.2.56.2'], '0.2.56.2'))
        self.assertTrue(fits(None, '0.2.56.2') and fits('>=9', None))

    def test_compat(self):
        line = '<!-- sp-compat {"hamish.sprocket": ">=0.2.55.5", "bepinex.bepinex": "6.0.0-be.788"} -->'
        self.assertEqual(updates.compat('Notes.\n\n' + line), '>=0.2.55.5')
        self.assertIsNone(updates.compat('Notes without one.'))
        self.assertIsNone(updates.compat('<!-- sp-compat {broken} -->'))


class Releases(unittest.TestCase):
    def test_newest_that_fits(self):
        pattern = updates.MODS[1][2]  # Battle Editor's own ZIP, not the combined one
        releases = [release(['Sprocket-Battle-Editor-and-Map-Framework-0.19.0.zip', 'Sprocket-Battle-Editor-0.19.0.zip'], '>=0.2.57'),
                    release(['Sprocket-Battle-Editor-0.18.1.zip'], '>=0.2.55.5'),
                    release(['Sprocket-Battle-Editor-0.18.5.zip'], '>=0.2.55.5', draft=True),
                    release(['Sprocket-Battle-Editor-0.18.0.zip'])]
        self.assertEqual(updates.newest(releases, pattern, '0.2.56.2')[:2], ('0.18.1', 'Sprocket-Battle-Editor-0.18.1.zip'))
        self.assertEqual(updates.newest(releases, pattern, '0.2.57.0')[0], '0.19.0')

    def test_needs_its_checksum(self):
        unchecked = {'body': '', 'assets': [{'name': 'Quality-of-Life-1.9.0.zip', 'browser_download_url': 'https://example/x'}]}
        self.assertIsNone(updates.newest([unchecked], updates.MODS[0][2], None))


class Installed(unittest.TestCase):
    def test_game_version(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, 'Sprocket_Data').mkdir()
            Path(t, 'Sprocket_Data', 'globalgamemanagers').write_bytes(
                b'\0' * 8 + b'\x0b\0\0\x006000.3.21f1\0' + b'\x08\0\0\x000.2.56.2' + b'\0' * 8)
            self.assertEqual(updates.game_version(t), '0.2.56.2')
            self.assertIsNone(updates.game_version(Path(t, 'missing')))

    def test_mod_version_from_its_dll(self):
        dll = Path(os.environ.get('WINDIR', r'C:\Windows'), 'Microsoft.NET/Framework64/v4.0.30319/System.dll')
        if not dll.is_file():
            self.skipTest('no .NET Framework DLL to read')
        with tempfile.TemporaryDirectory() as t:
            plugins = Path(t, 'Quality of Life', 'BepInEx', 'plugins')
            plugins.mkdir(parents=True)
            plugins.joinpath('SprocketQoL.dll').write_bytes(dll.read_bytes())
            self.assertEqual(updates.installed(t), {'SprocketQoL.dll': ('Quality of Life', '4.0.0.0')})


class Install(unittest.TestCase):
    def test_keeps_what_the_user_added(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            root = home / 'game'
            root.mkdir()
            game = Game(home, 'test', root, route={'BepInEx': ''})
            mod = game.mods_dir / 'Map Framework' / 'BepInEx' / 'plugins' / 'SprocketMaps'
            (mod / 'CustomMaps').mkdir(parents=True)
            (mod / 'SprocketMaps.dll').write_bytes(b'old')
            (mod / 'CustomMaps' / 'city.bundle').write_bytes(b'a map the user imported')
            game.enable('Map Framework')
            archive = home / 'Sprocket-Map-Framework-9.0.0.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('BepInEx/plugins/SprocketMaps/SprocketMaps.dll', b'new')
            updates.install(game, 'Map Framework', archive)
            self.assertIn('Map Framework', game.enabled)
            plugin = root / 'BepInEx' / 'plugins' / 'SprocketMaps'
            self.assertEqual((plugin / 'SprocketMaps.dll').read_bytes(), b'new')
            for folder in (plugin, mod):
                self.assertEqual((folder / 'CustomMaps' / 'city.bundle').read_bytes(), b'a map the user imported')


if __name__ == '__main__':
    unittest.main()
