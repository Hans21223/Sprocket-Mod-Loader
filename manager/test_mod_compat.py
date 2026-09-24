"""Tests for mod_compat's metadata reader. The reader never runs a DLL, so these read real .NET files that ship with
Python's host OS or a game install when present, and pure signature bytes otherwise."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mod_compat
from mod_compat import Metadata, Assembly, _arity, _compressed


def dotnet_dlls():
    """Some managed DLLs on this PC to read: the game's generated assemblies if MODMAN_TEST_GAME names a game folder
    with BepInEx set up, else the .NET Framework's own."""
    game = os.environ.get('MODMAN_TEST_GAME')
    folders = ([Path(game) / 'BepInEx/interop'] if game else []) + \
              [Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319']
    for folder in folders:
        found = sorted(folder.glob('*.dll'))[:60] if folder.is_dir() else []
        if found:
            return found
    return []


class Signatures(unittest.TestCase):
    def test_compressed_integers(self):
        self.assertEqual(_compressed(bytes([0x03]), 0), (3, 1))
        self.assertEqual(_compressed(bytes([0x80, 0x80]), 0), (0x80, 2))
        self.assertEqual(_compressed(bytes([0xC0, 0x00, 0x40, 0x00]), 0), (0x4000, 4))

    def test_parameter_counts(self):
        self.assertEqual(_arity(bytes([0x20, 0x04, 0x01, 0x08, 0x08, 0x08, 0x08])), 4)   # instance void (int x4)
        self.assertEqual(_arity(bytes([0x30, 0x01, 0x02, 0x01, 0x13, 0x00, 0x13, 0x00])), 2)  # generic, 2 params
        self.assertEqual(_arity(bytes([0x06, 0x08])), -1)                                  # a field
        self.assertIsNone(_arity(b''))


class RealAssemblies(unittest.TestCase):
    def test_reads_every_table_without_errors(self):
        dlls = dotnet_dlls()
        if not dlls:
            self.skipTest('no managed DLLs on this PC to read')
        read = 0
        for dll in dlls:
            meta = Metadata.read(dll.read_bytes())
            if meta is None:
                continue
            asm = Assembly(meta)
            self.assertTrue(asm.types, dll.name)
            for members in asm.types.values():
                for counts in members.values():
                    self.assertTrue(all(c is None or c >= -1 for c in counts))
            read += 1
        self.assertGreater(read, 0)

    def test_native_code_is_not_managed(self):
        kernel = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/kernel32.dll'
        if not kernel.is_file():
            self.skipTest('no kernel32.dll')
        self.assertIsNone(Metadata.read(kernel.read_bytes()))


if __name__ == '__main__':
    unittest.main()
