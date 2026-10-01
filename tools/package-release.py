"""Package the loader overlay and corresponding source; no game data."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'package'
VERSION = '1.2.1'
PATCH_DLLS = {
    'Il2CppInterop.Runtime.dll', 'Il2CppInterop.Common.dll',
    'Il2CppInterop.HarmonySupport.dll', 'Il2CppInterop.Generator.dll',
    'TerraFX.Interop.Windows.dll',
}

def public_files():
    for path in sorted(PACKAGE.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(PACKAGE)
        if any(part == 'Ready-to-copy' or part.startswith('preparing-') for part in rel.parts):
            continue
        if path.name.startswith('BepInEx-') and path.suffix == '.zip':
            continue
        if path.suffix.lower() == '.dll' and (rel.parent.as_posix() != 'Patch/BepInEx/core'
                                            or path.name not in PATCH_DLLS):
            raise RuntimeError(f'Unexpected DLL in sharing package: {rel}')
        yield path

actual_patch = {p.name for p in (PACKAGE / 'Patch/BepInEx/core').glob('*.dll')}
if actual_patch != PATCH_DLLS:
    raise RuntimeError(f'Compatibility overlay is incomplete or contains unexpected DLLs: {actual_patch}')

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
    for p in public_files() if p != checksums), encoding='utf-8', newline='\n')
out = ROOT / 'releases'
out.mkdir(exist_ok=True)
release = out / f'Sprocket-Mod-Loader-{VERSION}.zip'
with zipfile.ZipFile(release, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in public_files():
        archive.write(path, f'Sprocket-Mod-Loader-{VERSION}/' + path.relative_to(PACKAGE).as_posix())
with zipfile.ZipFile(release) as archive:
    assert archive.testzip() is None
release.with_suffix('.zip.sha256').write_text(f'{sha(release)}  {release.name}\n', encoding='utf-8', newline='\n')
print(f'{release}\nSHA256 {sha(release)}\n{release.stat().st_size} bytes')
