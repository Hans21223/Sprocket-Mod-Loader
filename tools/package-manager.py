"""Build the manager ZIP from an explicit public-file allowlist, with Python's own runtime so players install nothing.
Run it with the 64-bit Python 3.14 that gets bundled: "Mod Manager.exe" is that Python's signed pythonw.exe, renamed."""
import hashlib
import io
from pathlib import Path
import py_compile
import shutil
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'manager'))
import updates  # noqa: E402  (the version)

assert sys.version_info[:2] == (3, 14) and sys.maxsize > 2 ** 32, 'run this with 64-bit Python 3.14: it gets bundled'
runtime = Path(sys.base_prefix)
out = root / 'releases' / f'Sprocket-Mod-Manager-{updates.VERSION}.zip'
out.parent.mkdir(exist_ok=True)
names = ('modman.pyw', 'loader_setup.py', 'mod_compat.py', 'game_guard.py', 'updates.py',
         'test_loader_setup.py', 'test_mod_compat.py', 'test_game_guard.py', 'test_disable.py',
         'test_process_state.py', 'test_updates.py', 'README.md')
for name in names:
    if name.endswith(('.py', '.pyw')):
        py_compile.compile(str(root / 'manager' / name), doraise=True)

# The standard library, compiled, in one ZIP as python.org's embeddable Python has it; without tests and tools.
# Compiled from a copy: Python can't write its .pyc files into its own install folder.
stdlib = io.BytesIO()
with tempfile.TemporaryDirectory() as scratch:
    shutil.copytree(runtime / 'Lib', Path(scratch, 'Lib'), ignore=shutil.ignore_patterns(
        'test', 'tests', 'idlelib', 'ensurepip', 'venv', 'turtledemo', 'pydoc_data', 'site-packages', '__pycache__'))
    lib = Path(scratch, 'Lib')
    with zipfile.PyZipFile(stdlib, 'w', zipfile.ZIP_DEFLATED) as library:
        library.writepy(str(lib))  # a plain folder: only its top-level modules, so each package too
        for package in sorted(p for p in lib.iterdir() if (p / '__init__.py').is_file()):
            library.writepy(str(package))

with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name in names:
        archive.write(root / 'manager' / name, 'ModManager/' + name)
    archive.write(root / 'LICENSE', 'ModManager/LICENSE')
    archive.write(runtime / 'pythonw.exe', 'ModManager/Mod Manager.exe')
    for name in ('python314.dll', 'python3.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
        archive.write(runtime / name, 'ModManager/' + name)
    archive.writestr('ModManager/Mod Manager._pth', 'python\\python314.zip\r\npython\\DLLs\r\npython\r\n.\r\nimport site\r\n')
    archive.write(root / 'manager' / 'bundle' / 'sitecustomize.py', 'ModManager/python/sitecustomize.py')
    archive.write(runtime / 'LICENSE.txt', 'ModManager/python/LICENSE-Python.txt')
    archive.writestr('ModManager/python/python314.zip', stdlib.getvalue())
    for path in sorted((runtime / 'DLLs').iterdir()):
        if path.is_file() and not path.name.startswith(('_test', 'xx')):
            archive.write(path, 'ModManager/python/DLLs/' + path.name)
    for path in sorted((runtime / 'tcl').rglob('*')):
        if path.is_file() and 'demos' not in path.parts:
            archive.write(path, 'ModManager/python/tcl/' + path.relative_to(runtime / 'tcl').as_posix())

with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
    listed = set(archive.namelist())
    assert {'ModManager/' + n for n in names} | {'ModManager/Mod Manager.exe', 'ModManager/python/python314.zip'} <= listed
digest = hashlib.sha256(out.read_bytes()).hexdigest()
out.with_suffix('.zip.sha256').write_text(f'{digest}  {out.name}\n', encoding='utf-8', newline='\n')
print(f'{out}\nSHA256 {digest}\n{out.stat().st_size:,} bytes, {len(listed)} files')
