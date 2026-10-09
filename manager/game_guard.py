"""Game-build fingerprints for backups and the validated Sprocket loader profile."""
import hashlib
from pathlib import Path
import re
import struct


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


def trace_failure(native):
    """Why the loader could not find its three hook targets in this GameAssembly, or None when it can.
    The same trace as Il2CppInterop's SprocketUnity6Profile.Trace, which the loader runs at every start: game
    updates move these functions, and an update that changes Unity's IL2CPP runtime code is refused."""
    data = Path(native).read_bytes()
    u8 = lambda at: data[at] if 0 <= at < len(data) else -1
    i16 = lambda at: struct.unpack_from('<H', data, at)[0]
    i32 = lambda at: struct.unpack_from('<i', data, at)[0]
    try:
        pe = i32(0x3C)
        if data[pe:pe + 4] != b'PE\0\0' or i16(pe + 24) != 0x20B:
            return 'not an x64 image'
        headers = pe + 24 + i16(pe + 20)
        sections = [struct.unpack_from('<IIII', data, headers + 40 * i + 8) for i in range(i16(pe + 6))]
        def offset(rva):
            for size, address, raw_size, raw in sections:
                if address <= rva < address + min(size, raw_size):
                    return raw + rva - address
            return -1
        at = lambda rva, n=1: data[offset(rva):offset(rva) + n] if offset(rva) >= 0 else b''
        directory = lambda index: struct.unpack_from('<II', data, pe + 24 + 112 + 8 * index)
        table, table_size = directory(3)
        ends = {}
        for i in range(table_size // 12):
            begin, end = struct.unpack_from('<II', data, offset(table) + 12 * i)
            ends.setdefault(begin, end)
        exports, names = directory(0)[0], {}
        count, functions, name_table, ordinals = struct.unpack_from('<IIII', data, offset(exports) + 24)
        for i in range(count):
            name_offset = offset(struct.unpack_from('<I', data, offset(name_table) + 4 * i)[0])
            name = data[name_offset:data.index(b'\0', name_offset)].decode('ascii', 'replace')
            ordinal = struct.unpack_from('<H', data, offset(ordinals) + 2 * i)[0]
            names[name] = struct.unpack_from('<I', data, offset(functions) + 4 * ordinal)[0]
    except (struct.error, ValueError, IndexError):
        return 'unreadable GameAssembly'

    def displaced(rva, length):
        field = at(rva + length - 4, 4)
        return rva + length + struct.unpack('<i', field)[0] if len(field) == 4 else -1

    def thunk(name):  # an exported thunk starts with a jump to its implementation
        rva = names.get(name, -1)
        return displaced(rva, 5) if rva >= 0 and at(rva) == b'\xe9' else -1

    def callees(rva):  # function starts reached by a call or jump with a 32-bit displacement
        found, end = [], ends.get(rva, rva)
        body = at(rva, end - rva)
        for i in range(len(body) - 4):
            target = displaced(rva + i, 5) if body[i] in (0xE8, 0xE9) else \
                displaced(rva + i, 6) if body[i] == 0x0F and i + 5 < len(body) and body[i + 1] & 0xF0 == 0x80 else -1
            if target in ends and target not in found:
                found.append(target)
        return found

    def one(name, candidates, size, expected):
        matches = [rva for rva in candidates if ends.get(rva, rva) - rva == size and expected(rva)]
        if len(matches) != 1:
            raise LookupError(f'{name} {"not found" if not matches else "is ambiguous"}')
        return matches[0]

    try:
        one('Class::Init', callees(names.get('mono_class_instance_size', -1)), 103,
            lambda rva: at(rva, 16) == bytes.fromhex('40534883EC20488BD9F6813501000002'))
        field_caller = one('Field::StaticGetValue', [thunk('il2cpp_field_static_get_value')], 96, lambda rva: True)
        one('GetDefaultFieldValue', callees(field_caller), 341, lambda rva: at(rva, 5) == bytes.fromhex('48895C2408'))
        virtual_caller = one('Object::GetVirtualMethod', [thunk('il2cpp_object_get_virtual_method')], 239, lambda rva: True)
        context = one('GetGenericVirtualMethod', callees(virtual_caller), 62, lambda rva: at(rva + 0x18, 28) == bytes.fromhex(
            '488B424048894C24204C89442428488B481048894C2430488D4C2420'))
        one('GenericMethod::GetMethod', callees(context), 2338, lambda rva: at(rva, 7) == bytes.fromhex('40555356574154'))
    except LookupError as failure:
        return str(failure)
    return None


def require_supported_build(root):
    """Refuse mixed game files, and builds whose IL2CPP runtime the loader cannot trace."""
    native = Path(root) / NATIVE
    if not native.is_file():
        raise RuntimeError('GameAssembly.dll is missing. ' + VERIFY + ' No files were installed.')
    issue = problem(root, NATIVE, digest(native))
    if issue:
        raise RuntimeError(issue + ' No files were installed.')
    failure = trace_failure(native)
    if failure:
        raise RuntimeError(f"This Sprocket build is not supported by the loader: the update changed the game's "
                           f'IL2CPP runtime ({failure}). Wait for a Sprocket Mod Loader update. No files were installed.')
