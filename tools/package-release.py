"""Package the loader overlay and corresponding source; no game data."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'package'
VERSION = '1.2.0'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

source = PACKAGE / 'Source/Il2CppInterop-patched-source.zip'
with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    base = ROOT / 'src/Il2CppInterop'
    for path in sorted(base.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in ('bin', 'obj', '.git', '.vs') for part in rel.parts):
            continue
        archive.write(path, 'Il2CppInterop/' + rel.as_posix())
with zipfile.ZipFile(source) as archive:
    assert archive.testzip() is None
    assert not any(n.endswith(('GameAssembly.dll', 'Assembly-CSharp.dll', 'Sprocket.exe')) for n in archive.namelist())

checksums = PACKAGE / 'SHA256SUMS.txt'
checksums.write_text(''.join(f'{sha(p)}  {p.relative_to(PACKAGE).as_posix()}\n'
    for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p != checksums), encoding='utf-8', newline='\n')
out = ROOT / 'releases'
out.mkdir(exist_ok=True)
release = out / f'Sprocket-Mod-Loader-{VERSION}.zip'
with zipfile.ZipFile(release, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(PACKAGE.rglob('*')):
        if path.is_file():
            archive.write(path, f'Sprocket-Mod-Loader-{VERSION}/' + path.relative_to(PACKAGE).as_posix())
with zipfile.ZipFile(release) as archive:
    assert archive.testzip() is None
release.with_suffix('.zip.sha256').write_text(f'{sha(release)}  {release.name}\n', encoding='utf-8', newline='\n')
print(f'{release}\nSHA256 {sha(release)}\n{release.stat().st_size} bytes')
