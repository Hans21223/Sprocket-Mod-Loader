"""Read managed metadata without executing a DLL; choose Sprocket loader destinations; explain mods that can't work."""
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import re
import struct


# ---------- ECMA-335 metadata (standard library only; nothing is loaded or run) ----------

# Coded indexes: (tag bits, tables they can point at).
CODED = {
    'TypeDefOrRef': (2, (2, 1, 0x1B)), 'HasConstant': (2, (4, 8, 0x17)),
    'HasCustomAttribute': (5, (6, 4, 1, 2, 8, 9, 0x0A, 0, 0x0E, 0x17, 0x14, 0x11, 0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x2A, 0x2C, 0x2B)),
    'HasFieldMarshal': (1, (4, 8)), 'HasDeclSecurity': (2, (2, 6, 0x20)), 'MemberRefParent': (3, (2, 1, 0x1A, 6, 0x1B)),
    'HasSemantics': (1, (0x14, 0x17)), 'MethodDefOrRef': (1, (6, 0x0A)), 'MemberForwarded': (1, (4, 6)),
    'Implementation': (2, (0x26, 0x23, 0x27)), 'CustomAttributeType': (3, (6, 0x0A)),
    'ResolutionScope': (2, (0, 0x1A, 0x23, 1)), 'TypeOrMethodDef': (1, (2, 6)),
}
# Column layout of every table: 'u2'/'u4' fixed bytes, 's' string, 'g' guid, 'b' blob, int = row index into that
# table, other names = coded index.
SCHEMA = {
    0x00: ('u2', 's', 'g', 'g', 'g'), 0x01: ('ResolutionScope', 's', 's'), 0x02: ('u4', 's', 's', 'TypeDefOrRef', 0x04, 0x06),
    0x03: (0x04,), 0x04: ('u2', 's', 'b'), 0x05: (0x06,), 0x06: ('u4', 'u2', 'u2', 's', 'b', 0x08), 0x07: (0x08,),
    0x08: ('u2', 'u2', 's'), 0x09: (0x02, 'TypeDefOrRef'), 0x0A: ('MemberRefParent', 's', 'b'), 0x0B: ('u2', 'HasConstant', 'b'),
    0x0C: ('HasCustomAttribute', 'CustomAttributeType', 'b'), 0x0D: ('HasFieldMarshal', 'b'), 0x0E: ('u2', 'HasDeclSecurity', 'b'),
    0x0F: ('u2', 'u4', 0x02), 0x10: ('u4', 0x04), 0x11: ('b',), 0x12: (0x02, 0x14), 0x13: (0x14,), 0x14: ('u2', 's', 'TypeDefOrRef'),
    0x15: (0x02, 0x17), 0x16: (0x17,), 0x17: ('u2', 's', 'b'), 0x18: ('u2', 0x06, 'HasSemantics'),
    0x19: (0x02, 'MethodDefOrRef', 'MethodDefOrRef'), 0x1A: ('s',), 0x1B: ('b',), 0x1C: ('u2', 'MemberForwarded', 's', 0x1A),
    0x1D: ('u4', 0x04), 0x1E: ('u4', 'u4'), 0x1F: ('u4',), 0x20: ('u4', 'u2', 'u2', 'u2', 'u2', 'u4', 'b', 's', 's'),
    0x21: ('u4',), 0x22: ('u4', 'u4', 'u4'), 0x23: ('u2', 'u2', 'u2', 'u2', 'u4', 'b', 's', 's', 'b'), 0x24: ('u4', 0x23),
    0x25: ('u4', 'u4', 'u4', 0x23), 0x26: ('u4', 's', 'b'), 0x27: ('u4', 'u4', 's', 's', 'Implementation'),
    0x28: ('u4', 'u4', 's', 'Implementation'), 0x29: (0x02, 0x02), 0x2A: ('u2', 'u2', 'TypeOrMethodDef', 's'),
    0x2B: ('MethodDefOrRef', 'b'), 0x2C: (0x2A, 'TypeDefOrRef'),
}


class Metadata:
    """The tables of a managed DLL. `None` from `read` means native code (no .NET metadata)."""

    @staticmethod
    def read(data):
        def number(offset, size):
            if offset < 0 or offset + size > len(data):
                raise ValueError('Truncated managed image')
            return int.from_bytes(data[offset:offset + size], 'little')
        if data[:2] != b'MZ':
            return None
        pe = number(60, 4)
        if data[pe:pe + 4] != b'PE\0\0':
            return None
        optional, sections = pe + 24, []
        magic = number(optional, 2)
        if magic not in (0x10b, 0x20b):
            return None
        header = optional + number(pe + 20, 2)
        for i in range(number(pe + 6, 2)):
            pos = header + 40 * i
            sections.append((number(pos + 12, 4), number(pos + 16, 4), number(pos + 20, 4)))
        def offset(rva):
            for address, size, raw in sections:
                if address <= rva < address + size:
                    return raw + rva - address
            raise ValueError('Invalid managed RVA')
        directory = optional + (112 if magic == 0x20b else 96)
        cli = number(directory + 14 * 8, 4)
        if not cli:
            return None
        return Metadata(data, offset(number(offset(cli) + 8, 4)), number)

    def __init__(self, data, root, number):
        self.data, self.number = data, number
        if data[root:root + 4] != b'BSJB':
            raise ValueError('Invalid CLR metadata')
        pos = (root + 16 + number(root + 12, 4) + 3) & ~3
        count = number(pos + 2, 2)
        pos += 4
        self.streams = {}
        for _ in range(count):
            start, size = number(pos, 4), number(pos + 4, 4)
            end = data.index(b'\0', pos + 8, min(len(data), pos + 40))
            self.streams[data[pos + 8:end].decode('ascii')] = (root + start, size)
            pos = (end + 4) & ~3
        tables, _ = self.streams.get('#~', self.streams.get('#-', (0, 0)))
        if not tables or '#Strings' not in self.streams:
            raise ValueError('Missing metadata tables')
        heaps, valid = number(tables + 6, 1), number(tables + 8, 8)
        self.rows, pos = {}, tables + 24
        for table in range(64):
            if valid & (1 << table):
                self.rows[table] = number(pos, 4)
                pos += 4
        if heaps & 0x40:
            pos += 4  # extra data in some uncompressed (#-) streams
        self.sizes = {'s': 4 if heaps & 1 else 2, 'g': 4 if heaps & 2 else 2, 'b': 4 if heaps & 4 else 2}
        self.columns, self.start, self.width = {}, {}, {}
        for table in sorted(self.rows):
            if table not in SCHEMA:
                raise ValueError(f'Unknown metadata table {table:#x}')
            cols = [self._column_size(c) for c in SCHEMA[table]]
            self.columns[table], self.start[table], self.width[table] = cols, pos, sum(cols)
            pos += self.rows[table] * self.width[table]

    def _column_size(self, column):
        if isinstance(column, int):
            return 4 if self.rows.get(column, 0) >= 65536 else 2
        if column in ('u2', 'u4'):
            return int(column[1])
        if column in self.sizes:
            return self.sizes[column]
        bits, tables = CODED[column]
        return 4 if max((self.rows.get(t, 0) for t in tables), default=0) >= 1 << (16 - bits) else 2

    def table(self, table):
        """Rows of one table as tuples of raw column values (strings decoded, coded indexes left coded)."""
        if table not in self.rows:
            return []
        out, kinds = [], SCHEMA[table]
        for r in range(self.rows[table]):
            pos, row = self.start[table] + r * self.width[table], []
            for kind, size in zip(kinds, self.columns[table]):
                value = self.number(pos, size)
                row.append(self.string(value) if kind == 's' else value)
                pos += size
            out.append(tuple(row))
        return out

    def string(self, index):
        strings, size = self.streams['#Strings']
        if index >= size:
            raise ValueError('Invalid metadata string')
        start = strings + index
        return self.data[start:self.data.index(b'\0', start, strings + size)].decode('utf-8')

    def blob(self, index):
        start, size = self.streams.get('#Blob', (0, 0))
        if not start or index >= size:
            return b''
        length, pos = _compressed(self.data, start + index)
        return self.data[pos:pos + length]

    @staticmethod
    def decode(kind, value):
        """(table, 0-based row) a coded index points at, or None."""
        bits, tables = CODED[kind]
        tag, row = value & ((1 << bits) - 1), (value >> bits) - 1
        return (tables[tag], row) if tag < len(tables) and row >= 0 else None


def _compressed(data, pos):
    """ECMA-335 compressed unsigned integer: (value, position after it)."""
    b = data[pos]
    if b & 0x80 == 0:
        return b, pos + 1
    if b & 0xC0 == 0x80:
        return (b & 0x3F) << 8 | data[pos + 1], pos + 2
    return (b & 0x1F) << 24 | data[pos + 1] << 16 | data[pos + 2] << 8 | data[pos + 3], pos + 4


def _arity(signature):
    """How many parameters a method signature takes; -1 for a field; None if unreadable."""
    if not signature:
        return None
    try:
        if signature[0] & 0x0F == 0x06:
            return -1
        pos = 1
        if signature[0] & 0x10:  # generic method: count of type parameters first
            _, pos = _compressed(signature, pos)
        return _compressed(signature, pos)[0]
    except IndexError:
        return None


class Assembly:
    """The parts of a DLL's metadata the manager cares about: what it defines, references and calls."""

    def __init__(self, meta):
        self.meta = meta
        typerefs = meta.table(0x01)
        typedefs = meta.table(0x02)
        self.assembly_refs = [row[6] for row in meta.table(0x23)]
        nested = {n - 1: e - 1 for n, e in meta.table(0x29)}

        def ref_name(i, seen=()):
            scope, name, namespace = typerefs[i]
            target = Metadata.decode('ResolutionScope', scope)
            if target and target[0] == 1 and target[1] not in seen:  # nested in another type reference
                outer, assembly = ref_name(target[1], seen + (i,))
                return outer + '+' + name, assembly
            assembly = self.assembly_refs[target[1]] if target and target[0] == 0x23 and target[1] < len(self.assembly_refs) else None
            return (namespace + '.' + name if namespace else name), assembly

        self.typerefs = [ref_name(i) for i in range(len(typerefs))]

        def def_name(i, seen=()):
            _, name, namespace, *_ = typedefs[i]
            if i in nested and nested[i] not in seen:
                return def_name(nested[i], seen + (i,)) + '+' + name
            return namespace + '.' + name if namespace else name

        methods, fields = meta.table(0x06), meta.table(0x04)
        self.types = {}      # full name -> {member name: set of parameter counts (-1 = field)}
        self.extends = {}    # full name -> ('def', full name) / ('ref', (name, assembly)) / None
        for i, row in enumerate(typedefs):
            full = def_name(i)
            first_field, first_method = row[4] - 1, row[5] - 1
            last_field = typedefs[i + 1][4] - 1 if i + 1 < len(typedefs) else len(fields)
            last_method = typedefs[i + 1][5] - 1 if i + 1 < len(typedefs) else len(methods)
            members = self.types.setdefault(full, defaultdict(set))
            for m in methods[first_method:last_method]:
                members[m[3]].add(_arity(meta.blob(m[4])))
            for f in fields[first_field:last_field]:
                members[f[1]].add(-1)
            base = Metadata.decode('TypeDefOrRef', row[3])
            self.extends[full] = (('def', def_name(base[1])) if base and base[0] == 2 else
                                  ('ref', self.typerefs[base[1]]) if base and base[0] == 1 else None)
        self.namespaces = {name.rsplit('.', 1)[0] for name in self.types if '.' in name and not name.startswith('<')}
        # Calls into other assemblies: (type, its assembly, member name, parameter count).
        self.calls = []
        for parent, name, signature in meta.table(0x0A):
            target = Metadata.decode('MemberRefParent', parent)
            if target and target[0] == 1 and target[1] < len(self.typerefs):
                full, assembly = self.typerefs[target[1]]
                if assembly:
                    self.calls.append((full, assembly, name, _arity(meta.blob(signature))))


@lru_cache(maxsize=1024)
def _assembly(path, size, timestamp):
    try:
        meta = Metadata.read(Path(path).read_bytes())
        return Assembly(meta) if meta else None
    except (ValueError, IndexError, KeyError, UnicodeError, struct.error, OSError):
        return None


def assembly(path):
    path = Path(path)
    stat = path.stat()
    return _assembly(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def managed_types(data):
    """{'references': type names it uses, 'bases': external types its classes build on}; None for native code."""
    meta = Metadata.read(data)
    if meta is None:
        return None
    asm = Assembly(meta)
    bases = set()
    for full in asm.types:
        seen, base = set(), asm.extends.get(full)
        while base and base[0] == 'def' and base[1] not in seen:
            seen.add(base[1])
            base = asm.extends.get(base[1])
        if base and base[0] == 'ref':
            bases.add(base[1][0])
    return {'references': {name for name, _ in asm.typerefs}, 'bases': bases}


@lru_cache(maxsize=512)
def _inspect(path, size, timestamp):
    if size > 64 * 1024 * 1024:
        return {'kind': 'unknown', 'references': set()}
    try:
        metadata = managed_types(Path(path).read_bytes())
    except (ValueError, IndexError, KeyError, UnicodeError, struct.error):
        return {'kind': 'unknown', 'references': set()}
    if metadata is None: return {'kind': 'native', 'references': set()}
    bases, refs = metadata['bases'], metadata['references']
    if 'MelonLoader.MelonMod' in bases: kind = 'melon-mod'
    elif 'MelonLoader.MelonPlugin' in bases: kind = 'melon-plugin'
    elif 'BepInEx.Unity.IL2CPP.BasePlugin' in bases: kind = 'bepinex-il2cpp'
    elif 'BepInEx.IL2CPP.BasePlugin' in bases: kind = 'bepinex-old-il2cpp'
    elif any(x.endswith('.BaseUnityPlugin') for x in bases): kind = 'bepinex-mono'
    elif any(x.startswith(('Il2Cpp', 'MelonLoader.', 'SprocketModAPI.')) for x in refs): kind = 'melon-library'
    else: kind = 'managed-library'
    return {'kind': kind, 'references': refs}


def inspect_dll(path):
    stat = path.stat()
    return _inspect(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def plan(game, base, original):
    """Preserve explicit full layouts; correct loose DLLs and loader-relative ZIP layouts."""
    if Path(game.exe).name.lower() != 'sprocket.exe': return original
    infos = {src: inspect_dll(base / src) for src in original if src.lower().endswith('.dll')}
    kinds = {i['kind'] for i in infos.values()}
    bep = bool(kinds & {'bepinex-il2cpp', 'bepinex-old-il2cpp', 'bepinex-mono'})
    melon = bool(kinds & {'melon-mod', 'melon-plugin'})
    translation = ('Config.ini' in original and any(s.startswith('Translation/') for s in original))
    has_bep_translator = (game.root / 'BepInEx/plugins/XUnity.AutoTranslator/XUnity.AutoTranslator.Plugin.BepInEx-IL2CPP.dll').exists()
    result = dict(original)
    for src in original:
        parts = Path(src).parts
        # Full layouts are authoritative. In particular, do not move a loader's own libraries.
        if any(p.lower() in ('bepinex', 'mlloader', 'dotnet', '_inject') for p in parts): continue
        if translation:
            if src == 'Config.ini':
                result[src] = 'BepInEx/config/AutoTranslatorConfig.ini' if has_bep_translator else 'AutoTranslator/Config.ini'
            elif src.startswith('Translation/'):
                result[src] = ('BepInEx/' if has_bep_translator else 'AutoTranslator/') + src
            else:
                result[src] = 'AutoTranslator/' + src
            continue
        marker = next((i for i,p in enumerate(parts) if p.lower() in ('plugins','mods','userlibs','userdata')), None)
        if marker is not None:
            tail = '/'.join(parts[marker:])
            if parts[marker].lower() == 'plugins' and bep and not melon:
                result[src] = 'BepInEx/plugins/' + '/'.join(parts[marker + 1:])
            else:
                result[src] = 'MLLoader/' + tail
            continue
        info = infos.get(src)
        if len(parts) == 1 and info:
            dest = {'melon-mod':'MLLoader/Mods', 'melon-plugin':'MLLoader/Plugins',
                    'melon-library':'MLLoader/UserLibs', 'bepinex-il2cpp':'BepInEx/plugins',
                    'bepinex-old-il2cpp':'BepInEx/plugins', 'bepinex-mono':'BepInEx/plugins'}.get(info['kind'])
            if dest: result[src] = dest + '/' + parts[-1]
    return result


BEPINEX_CORE = 'BepInEx/core/BepInEx.Unity.IL2CPP.dll'


def validate(game, base, files):
    if Path(game.exe).name.lower() != 'sprocket.exe': return
    errors = []
    patcher = 'BepInEx/patchers/BepInEx.MelonLoader.Loader.Patcher.dll'
    dests = {d.lower() for d in files.values()}
    has_loader = (game.root / patcher).is_file() or patcher.lower() in dests
    has_bepinex = (game.root / BEPINEX_CORE).is_file() or BEPINEX_CORE.lower() in dests
    for src, dest in files.items():
        if not src.lower().endswith('.dll') or dest.lower().startswith(('bepinex/core/', 'dotnet/','mlloader/melonloader/')): continue
        info = inspect_dll(base / src)
        if info['kind'] in ('bepinex-mono','bepinex-old-il2cpp'):
            errors.append(f'{Path(src).name}: choose the BepInEx Unity IL2CPP CoreCLR build for this game.')
        if info['kind'] == 'bepinex-il2cpp' and not has_bepinex:
            errors.append('BepInEx is missing or disabled. Use Install mod loader to set it up first.')
        if info['kind'] in ('melon-mod','melon-plugin','melon-library') and not has_loader:
            errors.append('MLLoader is missing or disabled. Use Install mod loader to repair it first.')
    if errors: raise RuntimeError('\n'.join(dict.fromkeys(errors)))


def loader_notes(game):
    """Problems with the mod loader itself, which stop every mod rather than one; [] when none are seen."""
    if Path(game.exe).name.lower() != 'sprocket.exe': return []
    notes = []
    if not (game.root / BEPINEX_CORE).is_file():
        notes.append("The mod loader isn't installed, or it's disabled, so the mods you enable here can't load. "
                     "Close the game, click Install mod loader, start the game once, then check again.")
    elif not (game.root / 'BepInEx/LogOutput.log').is_file():
        notes.append("The mod loader is installed but hasn't run yet. Start the game once, then check again.")
    # A separate MelonLoader's own DLL (0.5 or 0.6+ layout); MLLoader keeps its copy under MLLoader/MelonLoader.
    if any((game.root / 'MelonLoader' / p / 'MelonLoader.dll').is_file() for p in ('', 'net6', 'net35')):
        notes.append("There's also a separate MelonLoader in the game folder (its MelonLoader folder). This setup runs "
                     "MelonLoader mods through MLLoader instead and hasn't been tested with a separate MelonLoader "
                     "running too. Uninstall it with the MelonLoader installer, then add its mods here with Add mod.")
    return notes


# ---------- Why an installed mod can't work here ----------

# Code the game itself provides, as the loaders generate it: calls into these are checked member by member.
GAME_CODE = ('MLLoader/MelonLoader/Il2CppAssemblies', 'BepInEx/interop', 'MelonLoader/Il2CppAssemblies')
# Everywhere else a DLL can be found at run time.
LIBRARIES = ('MLLoader', 'BepInEx', 'dotnet', 'MelonLoader', 'Mods', 'Plugins', 'UserLibs')
MOD_FOLDERS = ('MLLoader/Mods', 'MLLoader/Plugins', 'MLLoader/UserLibs', 'BepInEx/plugins', 'Mods', 'Plugins', 'UserLibs')
FRAMEWORK = ('System', 'Microsoft.', 'mscorlib', 'netstandard', 'WindowsBase', 'Mono.', 'Accessibility')
# Assemblies the mod loaders themselves ship, rather than the game or another mod.
LOADER_ASSEMBLIES = ('BepInEx', 'MelonLoader', 'Il2CppInterop', '0Harmony', 'MonoMod')
OBJECT_MEMBERS = {'.ctor', 'ToString', 'Equals', 'GetHashCode', 'GetType', 'Finalize', 'MemberwiseClone'}


def _dlls(folder):
    return {p.stem.lower(): p for p in Path(folder).rglob('*.dll')} if Path(folder).is_dir() else {}


def library_index(game):
    """(every DLL the game and its loaders can load: name -> path, the game's own code: name -> path)"""
    found, game_code = {}, {}
    for folder in LIBRARIES:
        found.update(_dlls(game.root / folder))
    for folder in GAME_CODE:
        code = _dlls(game.root / folder)
        game_code.update(code)
        found.update(code)
    return found, game_code


def mod_dlls(game):
    """Installed mod DLLs (not the loaders or the game's own code): name -> path."""
    found = {}
    for folder in MOD_FOLDERS:
        found.update(_dlls(game.root / folder))
    return found


def _lacks(available, full, assembly_name, member, arity, depth=0):
    """True if `full` (in that assembly) has no such member taking that many parameters, looking through its base
    types; False if it has, or it can't be told (a base type in a DLL that isn't here)."""
    if assembly_name.startswith(FRAMEWORK):  # reached System.Object & co.
        return member not in OBJECT_MEMBERS
    path = available.get(assembly_name.lower())
    asm = assembly(path) if path else None
    if asm is None or depth > 12:
        return False
    while True:
        if full not in asm.types:
            return True
        overloads = asm.types[full].get(member)
        if overloads and (arity is None or None in overloads or arity in overloads):
            return False
        if member in ('.ctor', '.cctor'):  # constructors aren't inherited
            return True
        base = asm.extends.get(full)
        if base is None:
            return True
        if base[0] == 'def':
            full = base[1]
            continue
        return _lacks(available, base[1][0], base[1][1] or '', member, arity, depth + 1) if base[1][1] else False


def check(game, base, files):
    """Notes (not errors) on a mod whose files install fine but can't work here: things it needs that the game and
    its loaders don't have, calls into game code this game doesn't have, or a library nothing uses."""
    available, game_code = library_index(game)
    for src in files:  # the mod's own DLLs count as available too
        if src.lower().endswith('.dll'):
            available.setdefault(Path(src).stem.lower(), base / src)
    notes = []
    for src in files:
        if not src.lower().endswith('.dll') or any(part in '/' + files[src].lower() for part in LOADER_FILES):
            continue  # a loader's own files aren't a mod to judge
        asm = assembly(base / src)
        if asm is None:
            continue
        name = Path(src).name
        missing = sorted({a for a in asm.assembly_refs if not a.startswith(FRAMEWORK) and a.lower() not in available})
        loader = [a for a in missing if a.startswith(LOADER_ASSEMBLIES)] if not (game.root / BEPINEX_CORE).is_file() else []
        if loader:  # without the loader nothing else can be judged: it also generates the game's code on first run
            notes.append(f'{name}: needs {", ".join(loader)}, part of the mod loader, which isn\'t installed or is '
                         'disabled, so this mod can\'t load. Click Install mod loader, start the game once, then check again.')
        elif missing and not game_code:
            notes.append(f'{name}: needs {", ".join(missing)}. The mod loader creates the game\'s parts the first time the '
                         'game starts with it, so start the game once, then check again.')
        elif missing:
            where = ("this version of the game doesn't have" if all(a.startswith('Il2Cpp') for a in missing) else
                     "isn't installed (another mod it needs, or part of the game this version doesn't have)")
            notes.append(f'{name}: needs {", ".join(missing)}, which {where}. That part of the mod will fail.')
        game_gone, unity_gone = [], []
        for full, assembly_name, member, arity in asm.calls:
            if assembly_name.lower() not in game_code or not _lacks(available, full, assembly_name, member, arity):
                continue
            owner = assembly(game_code[assembly_name.lower()])
            what = (f'{full.rsplit(".", 1)[-1]}.{member}' + (f' with {arity} argument{"s" * (arity != 1)}' if arity and arity > 0 else '')
                    if owner and full in owner.types else f'{full} (the whole type)')
            gone = game_gone if 'Sprocket' in full.split('.', 2)[0] + assembly_name else unity_gone
            if what not in gone:
                gone.append(what)
        for gone, text in ((game_gone, 'made for another version of the game. It uses {}, which this version doesn\'t '
                                       'have, so that code throws errors when it runs. It needs an update from its author.'),
                           (unity_gone, 'uses {}, which this game\'s Unity build doesn\'t have (a newer Unity, or a part '
                                        'the game leaves out), so that part fails.')):
            if gone:
                more = f' and {len(gone) - 4} more' if len(gone) > 4 else ''
                notes.append(f'{name}: ' + text.format(', '.join(gone[:4]) + more))
        if inspect_dll(base / src)['kind'] in ('melon-library', 'managed-library') and '/userlibs/' in '/' + files[src].lower():
            stem = Path(src).stem.lower()
            others = [p for key, p in mod_dlls(game).items() if key != stem] + \
                     [base / s for s in files if s != src and s.lower().endswith('.dll')]
            if not any(stem in {a.lower() for a in (assembly(p).assembly_refs if assembly(p) else ())} for p in others):
                notes.append(f'{name}: a library, not a mod. It does nothing on its own; it\'s there for other mods that '
                             'use it, and none installed do.')
    return notes


# ---------- What went wrong in the last game session ----------

LOGS = ('BepInEx/LogOutput.log', 'MLLoader/MelonLoader/Latest.log', 'MelonLoader/Latest.log')
PLATFORM = ('System.', 'MelonLoader.', 'HarmonyLib.', 'Il2CppInterop.', 'UnityEngine.', 'BepInEx.', 'Il2CppSystem.',
            'Mono.', 'Microsoft.', '(wrapper', 'Il2Cpp', 'Trampoline', 'DMD<')
FAILURE = re.compile(r'exception|error|failed|could not|not found|missing|not resolved', re.I)
LOADER_FILES = ('/bepinex/core/', '/bepinex/patchers/', '/mlloader/melonloader/', '/dotnet/', '/bepinex.melonloader.loader/')


def log_report(game, mods):
    """(log file, [(mod or source, count, most common message)]) from the newest loader log, plus one line for text
    the game's font can't show. `mods`: {mod name: [its installed files]}, to tell which mod an error came from."""
    log = next((game.root / p for p in LOGS if (game.root / p).is_file()), None)
    if log is None:
        return None, []
    namespaces, names, needs = {}, {}, {}
    for mod, paths in mods.items():
        for path in map(Path, paths):
            # A loader's own files (MelonLoader, BepInEx, the runtime) run every mod: an error passing through them
            # isn't theirs, so they don't claim errors.
            if path.suffix.lower() != '.dll' or not path.is_file() or any(part in path.as_posix().lower() for part in LOADER_FILES):
                continue
            names[path.stem.lower().replace(' ', '')] = mod
            asm = assembly(path)
            for ns in (asm.namespaces if asm else ()):
                namespaces[ns] = mod
            for ref in (asm.assembly_refs if asm else ()):
                needs.setdefault(ref.lower(), set()).add(mod)

    def owner(text):
        """The mod a stack frame, log source or [Tag] belongs to, if any."""
        text = text.strip()
        hit = max((ns for ns in namespaces if text == ns or text.startswith(ns + '.') or ns.startswith(text + '.')), key=len, default=None)
        if hit:
            return namespaces[hit]
        key = text.lower().replace(' ', '')
        return next((mod for stem, mod in names.items() if len(key) > 3 and (key in stem or stem in key)), None)

    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    problems, glyphs, i = defaultdict(list), 0, 0
    while i < len(lines):
        head = re.match(r'\[(Error|Warning)\s*:\s*([^\]]+)\]\s*(.*)', lines[i])
        i += 1
        if not head:
            continue
        level, source, message = head.group(1), head.group(2).strip(), head.group(3)
        stack = []
        while i < len(lines) and not lines[i].startswith('[') and lines[i].strip():
            stack.append(lines[i].strip())
            i += 1
        if 'was not found in the' in message and 'font asset' in message:
            glyphs += 1
            continue
        if 'NOT BUG' in message or (level == 'Warning' and not FAILURE.search(message + ' ' + ' '.join(stack[:2]))):
            continue
        frames = [s[3:].split('(')[0] for s in stack if s.startswith('at ') and not s[3:].startswith(PLATFORM)]
        tag = re.match(r'\[([^\]]+)\]', message)
        named = re.search(r'([A-Z][\w]+(?:\.[\w]+)+)', message)
        wanted = re.search(r"load file or assembly '([^,']+)", message)  # a missing DLL only one mod asks for is that mod's
        wanted = needs.get(wanted.group(1).lower(), set()) if wanted else set()
        loader = source in ('MelonLoader', 'Il2CppInterop', 'BepInEx', 'Unity')  # logs for everyone: not a mod's name
        who = (next((owner(f) for f in frames if owner(f)), None) or (owner(tag.group(1)) if tag else None)
               or (None if loader else owner(source)) or (next(iter(wanted)) if len(wanted) == 1 else None)
               or (owner(named.group(1)) if named else None)
               or ('Loader / game (not a particular mod)' if loader else source))
        problems[who].append((message or (stack[0] if stack else '')).strip())
    report = [(who, len(msgs), Counter(msgs).most_common(1)[0][0][:220]) for who, msgs in problems.items()]
    report.sort(key=lambda r: (r[0].startswith('Loader /'), -r[1]))
    if glyphs:
        report.append(("Text / fonts", glyphs, "Text on screen uses characters the game's font doesn't have (shown as "
                       "boxes). A translation needs a font with those characters."))
    return log, report
