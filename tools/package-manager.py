"""Build a source-only manager ZIP from an explicit public-file allowlist."""
import hashlib
from pathlib import Path
import py_compile
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / 'releases' / 'Sprocket-Mod-Manager-1.3.1.zip'
names = ('modman.pyw', 'loader_setup.py', 'mod_compat.py', 'test_loader_setup.py', 'test_mod_compat.py', 'README.md')
for name in names:
    if name.endswith(('.py', '.pyw')):
        py_compile.compile(str(root / 'manager' / name), doraise=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name in names:
        archive.write(root / 'manager' / name, 'ModManager/' + name)
    archive.write(root / 'LICENSE', 'ModManager/LICENSE')
with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist()) == len(names) + 1
digest = hashlib.sha256(out.read_bytes()).hexdigest()
out.with_suffix('.zip.sha256').write_text(f'{digest}  {out.name}\n', encoding='utf-8', newline='\n')
print(f'{out}\nSHA256 {digest}\n{out.stat().st_size} bytes')
