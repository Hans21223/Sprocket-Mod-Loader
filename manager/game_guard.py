"""Game-build fingerprints for backups and the validated Sprocket loader profile."""
import hashlib
from pathlib import Path
import re


NATIVE = 'GameAssembly.dll'
METADATA = 'Sprocket_Data/il2cpp_data/Metadata/global-metadata.dat'
GAME_HASH = '18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56'
METADATA_HASH = '6B0D5FB3E62F4F765C2E56289B8DCD8BC81F21FCCEF938D69CEDFFA5D31C52E0'
PROFILE_BUILD = {'appid': '1674170', 'buildid': '25392405', 'manifest': '2900396840838466543'}
UPDATED_GAME_HASH = 'ADB36B5F04662BE0D40C6E548C797394659A9C0D4B009E3C0E718833ABF90B3A'
UPDATED_METADATA_HASH = '1B3052E0BC7391633366F8E246BB61F56B4F21D290A67949CB4E44CB5FEB2912'
VERIFY = "Use Steam's Verify integrity of game files to restore the matching game files."


def supported_pairs():
    return {GAME_HASH: METADATA_HASH, UPDATED_GAME_HASH: UPDATED_METADATA_HASH}


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            sha.update(chunk)
    return sha.hexdigest().upper()


def steam_build(root):
    """Installed Steam build for this exact Sprocket checkout, never a nearby test copy."""
    root = Path(root).resolve()
    manifest = root.parent.parent / 'appmanifest_1674170.acf'
    if root.parent.name.lower() != 'common' or not manifest.is_file():
        return None
    text = manifest.read_text(encoding='utf-8', errors='replace')
    values = dict(re.findall(r'"([^"\r\n]+)"\s+"([^"\r\n]*)"', text))
    if values.get('appid') != '1674170' or values.get('installdir', '').lower() != root.name.lower():
        return None
    if not values.get('buildid', '').isdigit():
        return None
    return {'appid': values['appid'], 'buildid': values['buildid'], 'manifest': values.get('manifest', '')}


def context(root, rel):
    result = {'steam': steam_build(root)}
    if rel.replace('\\', '/').lower() == NATIVE.lower():
        metadata = Path(root) / METADATA
        result['metadata_sha256'] = digest(metadata) if metadata.is_file() else None
    return result


def original_context(root, rel, native_hash):
    """Recover the known old profile context for legacy backups without blessing current update files."""
    result = context(root, rel)
    if rel.replace('\\', '/').lower() == NATIVE.lower() and native_hash.upper() == GAME_HASH:
        result['metadata_sha256'] = METADATA_HASH
        if result['steam'] is not None:
            result['steam'] = dict(PROFILE_BUILD)
    return result


def problem(root, rel, native_hash, saved=None):
    current = context(root, rel)
    is_native = rel.replace('\\', '/').lower() == NATIVE.lower()
    pairs = supported_pairs()
    if is_native and native_hash.upper() in pairs and current.get('metadata_sha256') != pairs[native_hash.upper()]:
        version = '0.2.55.5' if native_hash.upper() == GAME_HASH else '0.2.56.0'
        return (f'GameAssembly.dll belongs to Sprocket {version}, but its game metadata does not match. '
                'The game contains files from different builds. ' + VERIFY)
    if saved is None:
        saved = original_context(root, rel, native_hash)
    if saved.get('steam') is not None and current.get('steam') != saved['steam']:
        return ('Steam updated Sprocket after this game-file backup was recorded. '
                'Restoring that backup would replace the updated game code with an older build. ' + VERIFY)
    if 'metadata_sha256' in saved and current.get('metadata_sha256') != saved['metadata_sha256']:
        return ('Sprocket game metadata changed after this game-file backup was recorded. '
                'The previous game code cannot be restored into this build. ' + VERIFY)
    return None


def require_supported_pair(root):
    """Only the separately traced code/metadata pairs are accepted; future builds need native tracing."""
    native, metadata = Path(root) / NATIVE, Path(root) / METADATA
    native_hash = digest(native) if native.is_file() else ''
    if native_hash not in supported_pairs():
        raise RuntimeError('This Sprocket build is not supported by the patch. No files were installed.')
    issue = problem(root, NATIVE, native_hash)
    if issue:
        raise RuntimeError(issue + ' No files were installed.')
    if not metadata.is_file() or digest(metadata) != supported_pairs()[native_hash]:
        raise RuntimeError('Sprocket GameAssembly and game metadata belong to different builds. ' + VERIFY +
                           ' No files were installed.')
