"""Verified, reversible Sprocket loader setup. No process injection or game-binary patching."""
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

GAME_HASH = '18a9a15b5e5f11898ed4dc34fc3e2d4c12950c3b37ac1fa499e8b00592dedd56'
MOD = 'Sprocket mod loader - BepInEx + MLLoader'
BASE_NAME = 'BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788+5b766a3.zip'
BASE_HASH = 'f4cc496bd098a0df4164b81e3737297707f13a47c2478dba2f60eefab784817a'
BASE_URL = 'https://builds.bepinex.dev/projects/bepinex_be/788/' + BASE_NAME.replace('+', '%2B')
PATCH_NAME = 'Sprocket-Mod-Loader-1.2.0.zip'
PATCH_HASH = '4f4c01dd01ebfa388e80d93b51a669cb380d7f7ce5da2a2f13b2e952f9536262'
PATCH_URL = 'https://github.com/Hans21223/Sprocket-Mod-Loader/releases/download/v1.2.0/' + PATCH_NAME
MELON_HASH = 'bdc630e635de656c47f2a011f5e700115e09b70c3b33ac512018ef728f39d9cd'
MELON_PAGE = 'https://www.nexusmods.com/ironnest/mods/26'


def remove_tree(path, parent):
    resolved, boundary = path.resolve(), parent.resolve()
    if resolved == boundary or not resolved.is_relative_to(boundary):
        raise RuntimeError(f'Refusing to remove a folder outside {boundary}')
    shutil.rmtree(path)


def digest(path):
    # Read in chunks rather than hashlib.file_digest, which only exists from Python 3.11.
    sha = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            sha.update(chunk)
    return sha.hexdigest()


def verify(path, expected):
    if digest(path) != expected:
        raise RuntimeError(f'Checksum failed: {Path(path).name}. Obtain the exact supported ZIP again.')


def download(cache, name, url, expected, report):
    target = cache / name
    if target.exists():
        verify(target, expected)
        return target
    report(f'Downloading {name}...')
    temporary = target.with_suffix('.download')
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Sprocket-Mod-Manager/1.0'})
        with urllib.request.urlopen(request, timeout=60) as source, temporary.open('wb') as out:
            shutil.copyfileobj(source, out)
        verify(temporary, expected)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def extract(archive, destination, prefix=''):
    """Only write ordinary relative files, even if an archive is malformed."""
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name = item.filename.replace('\\', '/')
            if prefix and not name.startswith(prefix):
                continue
            name = name[len(prefix):]
            parts = PurePosixPath(name).parts
            if not parts or item.is_dir():
                continue
            if name.startswith('/') or any(p in ('..', '.') or ':' in p for p in parts):
                raise RuntimeError('Unsafe path in loader archive')
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('Loader archive escapes its staging folder')
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as source, target.open('wb') as out:
                shutil.copyfileobj(source, out)


def validate_game(game, running):
    if not (game.root / 'Sprocket.exe').is_file() or not (game.root / 'GameAssembly.dll').is_file():
        raise RuntimeError('Select the Sprocket game folder containing Sprocket.exe.')
    if running('Sprocket.exe'):
        raise RuntimeError('Close Sprocket before installing the loader.')
    if digest(game.root / 'GameAssembly.dll') != GAME_HASH:
        raise RuntimeError('This Sprocket build is not supported by the patch. No files were installed.')


def install(game, home, melon_zip, running, report=lambda message: None):
    home = Path(home)
    validate_game(game, running)
    cache = home / 'loader-cache'
    cache.mkdir(parents=True, exist_ok=True)
    melon = Path(melon_zip) if melon_zip else cache / 'MLLoader-2.3.9.zip'
    if not melon.is_file():
        raise RuntimeError('Choose your MLLoader IL2CPP 2.3.9 ZIP from Nexus Mods first.')
    verify(melon, MELON_HASH)
    cached_melon = cache / 'MLLoader-2.3.9.zip'
    if melon.resolve() != cached_melon.resolve():
        shutil.copyfile(melon, cached_melon)
        verify(cached_melon, MELON_HASH)
    base = download(cache, BASE_NAME, BASE_URL, BASE_HASH, report)
    patch = download(cache, PATCH_NAME, PATCH_URL, PATCH_HASH, report)
    with tempfile.TemporaryDirectory(prefix='loader-prepare-', dir=cache) as tmp:
        prepared = Path(tmp) / 'prepared'
        prepared.mkdir()
        report('Preparing BepInEx, the Sprocket patch and MLLoader...')
        extract(base, prepared)
        extract(patch, prepared, 'Sprocket-Mod-Loader-1.2.0/Patch/')
        extract(cached_melon, prepared)
        # Keep patch libraries authoritative even if a future package contains a core folder.
        extract(patch, prepared, 'Sprocket-Mod-Loader-1.2.0/Patch/')
        for relative in ('winhttp.dll', 'doorstop_config.ini', 'BepInEx/core/Il2CppInterop.HarmonySupport.dll',
                         'BepInEx/patchers/BepInEx.MelonLoader.Loader.Patcher.dll', 'MLLoader/MelonLoader/MelonLoader.dll'):
            if not (prepared / relative).is_file():
                raise RuntimeError(f'Prepared loader is missing {relative}')
        validate_game(game, running)  # Downloads can take time; recheck before touching the game.
        return install_prepared(game, home, prepared, report)


def install_prepared(game, home, prepared, report=lambda message: None):
    """Migrate overlapping loader entries atomically, retaining the normal disable backups.

    Recovery journal survives a failed rollback. Unrelated mods are never disabled.
    Callers must close the game and validate its build before entering here.
    """
    files = {p.relative_to(prepared).as_posix(): p for p in prepared.rglob('*') if p.is_file()}
    if not files:
        raise RuntimeError('The prepared loader is empty')
    lower = {p.lower() for p in files}
    old = [m for m, paths in game.enabled.items() if lower.intersection(p.lower() for p in paths)]
    for mod in old:
        outside = [p for p in game.enabled[mod] if p.lower() not in lower]
        if outside:
            raise RuntimeError(f'{mod} combines loader files with other content. Disable it before setup.')
    # Explicit paths bypass generic mod routing (e.g. a user's DLL or JSON routing rule).
    for relative in files:
        target = game.target(relative)
        if target.resolve() != (game.root / relative).resolve():
            raise RuntimeError(f'Game routing redirects loader file {relative}; fix games.json before setup.')
    if MOD in game.enabled and old == [MOD] and all(
            game.target(p).is_file() and digest(game.target(p)) == digest(src) for p, src in files.items()):
        return 'Loader already installed and verified. Use Launch to start Sprocket.'
    pending = Path(home) / 'loader-recovery' / game.name
    if not pending.resolve().is_relative_to((Path(home) / 'loader-recovery').resolve()):
        raise RuntimeError('Invalid game name for loader recovery')
    if pending.exists():
        raise RuntimeError(f'A previous setup needs recovery. Preserve this folder: {pending}')
    pending.mkdir(parents=True)
    old_enabled = copy.deepcopy(game.enabled)
    source_dir = game.mods_dir / MOD
    snapshots = []
    # Snapshot exactly the paths the transaction may change, including backup/metadata files.
    paths = {game.state}
    for relative in files:
        paths.update((game.target(relative), game.backup / relative,
                      (game.backup / relative).with_name(Path(relative).name + '.kept')))
    try:
        for index, path in enumerate(sorted(paths, key=str)):
            exists = path.exists()
            if exists and not path.is_file():
                raise RuntimeError(f'Expected a file: {path}')
            copy_path = pending / 'files' / str(index)
            if exists:
                copy_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, copy_path)
            snapshots.append((path, copy_path, exists))
        if source_dir.exists():
            shutil.copytree(source_dir, pending / 'previous-mod')
        (pending / 'journal.json').write_text(json.dumps(
            {'files': [[str(a), str(b.relative_to(pending)), c] for a, b, c in snapshots], 'mod': str(source_dir)}, indent=2))
    except BaseException:
        remove_tree(pending, Path(home) / 'loader-recovery')
        raise
    try:
        report('Installing loader; backing up existing files...')
        for mod in old:
            # Content remains recoverable in the journal, even if edited since installation.
            game.disable(mod)
        if source_dir.exists():
            remove_tree(source_dir, game.mods_dir)
        shutil.copytree(prepared, source_dir)
        # Use an exact manifest for this install, independent of generic import routing.
        original_files = game.files
        try:
            game.files = lambda mod: {p: p for p in files} if mod == MOD else original_files(mod)
            game.enable(MOD)
        finally:
            game.files = original_files
        for relative, source in files.items():
            if digest(game.target(relative)) != digest(source):
                raise RuntimeError(f'Installed checksum failed: {relative}')
        # Retain a snapshot for manual recovery after success (not shipped/published).
        archive = Path(home) / 'loader-history'
        archive.mkdir(exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix='before-setup-', dir=archive))
        destination.rmdir()
        os.replace(pending, destination)
    except BaseException as failure:
        try:
            for path, snapshot, existed in reversed(snapshots):
                if existed:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(snapshot, path)
                else:
                    path.unlink(missing_ok=True)
            if source_dir.exists():
                remove_tree(source_dir, game.mods_dir)
            if (pending / 'previous-mod').exists():
                shutil.copytree(pending / 'previous-mod', source_dir)
            game.enabled = old_enabled
            remove_tree(pending, Path(home) / 'loader-recovery')
        except BaseException as recovery_error:
            raise RuntimeError(f'Setup failed: {failure}. Recovery needs attention: {recovery_error}. '
                               f'Backups and journal: {pending}') from failure
        raise RuntimeError(f'Setup failed; previous files restored: {failure}') from failure
    return f'Installed and verified {len(files)} loader files. Use Launch to start Sprocket.'
