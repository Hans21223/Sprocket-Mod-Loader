"""Mod manager + DLL injector (set up for Sprocket, works for any Windows game).

  modman.pyw                    GUI (double-click)
  python modman.pyw --selftest  self-check
  python modman.pyw --report "Sprocket"  why enabled mods may not work (also the "Mod report" button)

A mod is a folder, archive or single file in mods/<Game>/<Mod>/. Enable copies it into the game
(originals saved to backup/), disable puts them back. Where each file lands is decided by games.json:
  "roots"  extra install folders, e.g. _user/ -> Documents/My Games/Sprocket
  "route"  top-level name or glob -> folder it belongs in, e.g. "*.blueprint" -> the faction's Vehicles
Files the game already recognises (Sprocket_Data/..., _user/...) are copied as-is.
DLLs in a mod's _inject/ folder are injected into the game when you hit Launch.

"Decals & Paint" (Sprocket) browses Decals/ and Paint/ with subfolders, shows which blueprints use
each image and which images each blueprint uses. Moving/renaming an image repoints those blueprints
(originals copied to blueprint-backups/ first).
"""
import csv, ctypes, filecmp, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time, traceback, zipfile
from collections import Counter
from ctypes import wintypes as wt
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import unquote

HOME = Path(__file__).resolve().parent
INJECT_DIR = "_inject"


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def stamp(path):
    st = path.stat()
    return [st.st_size, st.st_mtime_ns]


def restore_file(backup, destination):
    """Restore across volumes; keep backup until the destination replacement succeeds."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.modman-restore-', dir=destination.parent)
    os.close(descriptor)
    try:
        shutil.copy2(backup, temporary)
        os.replace(temporary, destination)
        backup.unlink()
    finally:
        Path(temporary).unlink(missing_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


class Game:
    def __init__(self, home, name, dir, exe="", delay=5, roots=None, route=None, protect=None, originals=None):
        self.name, self.root, self.exe, self.delay = name, Path(dir), exe, delay
        self.roots = {k.lower(): Path(os.path.expandvars(v)) for k, v in (roots or {}).items()}
        self.route = route or {}
        self.protect = protect or []  # core game files the guard watches
        self.originals = {k: [h.upper() for h in v] for k, v in (originals or {}).items()}  # known release hashes
        self.mods_dir = home / "mods" / name
        self.backup = home / "backup" / name
        self.state = home / "state" / f"{name}.json"
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = load(self.state, {})  # mod -> {installed file: [size, mtime_ns] right after install}

    def mods(self):
        return sorted({p.name for p in self.mods_dir.iterdir() if p.is_dir()} | set(self.enabled), key=str.lower)

    def target(self, rel):
        head, _, rest = rel.partition("/")
        return self.roots[head.lower()] / rest if head.lower() in self.roots else self.root / rel

    def dest(self, parts, siblings):
        """Where a mod file installs: the first path component the game or route table recognises decides."""
        for i, name in enumerate(parts):
            if name.lower() in self.roots or (self.root / name).exists():
                return parts[i:]
            for pattern, parent in self.route.items():
                folder, _, marker = pattern.partition("/")  # "*/*.fdef" = a folder holding a .fdef file
                if fnmatch(name, folder) and (not marker or any(
                        len(s) == i + 2 and s[:i + 1] == parts[:i + 1] and fnmatch(s[-1], marker) for s in siblings)):
                    return (*parent.split("/"), *parts[i:]) if parent else parts[i:]
        return parts  # unrecognised: game folder, as-is

    def files(self, mod):
        """{file in the mod folder: where it installs}, both posix paths. _inject/ is left out."""
        base = self.mods_dir / mod
        srcs = [p.relative_to(base).parts for p in base.rglob("*") if p.is_file()]
        srcs = [s for s in srcs if s[0].lower() != INJECT_DIR]
        files = {"/".join(s): "/".join(self.dest(s, srcs)) for s in srcs}
        from mod_compat import plan
        return plan(self, base, files)

    def add(self, src):
        src = Path(src)
        archive = any(src.name.lower().endswith(e) for _, exts, _ in shutil.get_unpack_formats() for e in exts)
        dst = self.mods_dir / (src.name if src.is_dir() else src.stem)
        if dst.exists():
            raise RuntimeError(f"A mod named '{dst.name}' already exists")
        if src.is_dir():
            shutil.copytree(src, dst)
        elif archive:
            shutil.unpack_archive(src, dst)
        else:  # loose .blueprint / .png / .json ...
            dst.mkdir(parents=True)
            shutil.copy2(src, dst)
        return dst.name

    def enable(self, mod):
        if mod in self.enabled:
            return self.enabled[mod]
        files = self.files(mod)
        from mod_compat import validate
        validate(self, self.mods_dir / mod, files)
        owners = {d.lower(): m for m, fs in self.enabled.items() for d in fs}
        shared = {d.lower() for s, d in files.items() if d.lower() in owners and self.target(d).is_file()
                  and filecmp.cmp(self.mods_dir / mod / s, self.target(d), shallow=False)}  # same decal in two packs
        # ponytail: no load order, differing overlaps are refused. Add priorities if people need stacking.
        clash = sorted({owners[d.lower()] for d in files.values() if d.lower() in owners and d.lower() not in shared})
        if clash:
            raise RuntimeError(f"'{mod}' overwrites files of enabled mod(s): {', '.join(clash)}")
        done = self.enabled[mod] = {}
        try:
            for src, rel in files.items():
                dst, bak = self.target(rel), self.backup / rel
                if rel.lower() in shared:
                    done[rel] = stamp(dst)
                    continue
                if rel not in done and dst.exists() and not bak.exists():
                    bak.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, bak)
                done[rel] = None  # recorded before the copy, so a half-done copy still gets rolled back
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.mods_dir / mod / src, dst)
                done[rel] = stamp(dst)
        except BaseException:
            self.disable(mod)
            raise
        save(self.state, self.enabled)
        return done

    def disable(self, mod):
        """Undo a mod. Files changed since install (e.g. a tank re-saved in game) are kept; returns those."""
        files, kept = self.enabled.get(mod, {}), []
        others = {d.lower() for m, fs in self.enabled.items() if m != mod for d in fs}
        try:
            for rel, installed in reversed(list(files.items())):  # one at a time, so a failure leaves an accurate record
                dst, bak = self.target(rel), self.backup / rel
                if rel.lower() in others:
                    pass  # another enabled mod still uses this file; the last one out restores it
                elif installed and dst.exists() and stamp(dst) != installed:
                    kept.append(rel)
                    if bak.exists():
                        os.replace(bak, bak.with_name(bak.name + ".kept"))
                elif bak.exists():
                    restore_file(bak, dst)
                else:
                    dst.unlink(missing_ok=True)
                del files[rel]
        finally:
            if not files:
                self.enabled.pop(mod, None)
            save(self.state, self.enabled)
        return kept

    def remove(self, mod):
        """Disable a mod, then delete the manager's copy of it. Returns the files kept as in disable()."""
        folder = self.mods_dir / mod
        if not folder.resolve().is_relative_to(self.mods_dir.resolve()) or folder.resolve() == self.mods_dir.resolve():
            raise RuntimeError(f"Refusing to remove {folder}")
        kept = self.disable(mod) if mod in self.enabled else []
        if mod in self.enabled:
            raise RuntimeError(f"{mod} couldn't be fully disabled, so it wasn't removed")
        if folder.is_dir():
            shutil.rmtree(folder)
        elif folder.exists():
            folder.unlink()
        return kept

    def inject_dlls(self):
        return [p for m in self.enabled for p in (self.mods_dir / m / INJECT_DIR).glob("*.dll")]

    # --- Game file guard: keep a verified copy of core game files, notice outside changes (e.g. patchers), restore ---
    def _guard(self):
        path = self.state.with_name(f"{self.name}.guard.json")
        return path, load(path, {})  # file -> sha256 of its original

    def check_files(self):
        """[(file, state)] for protected files: 'original', 'changed' (restorable) or 'unknown' (no original on record)."""
        path, guard = self._guard()
        out = []
        for rel in self.protect:
            f = self.root / rel
            if not f.is_file():
                continue
            digest = sha256(f)
            if rel not in guard and digest in self.originals.get(rel, []):
                self.trust(rel, digest)  # matches a known original release: back it up now
                guard[rel] = digest
            out.append((rel, "unknown" if rel not in guard else "original" if digest == guard[rel] else "changed"))
        return out

    def trust(self, rel, digest=None):
        """Record the file as it is now as the original (after a verified release or a game update) and keep a copy."""
        path, guard = self._guard()
        f = self.root / rel
        copy = self.backup / "_originals" / rel
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, copy)
        guard[rel] = digest or sha256(f)
        if sha256(copy) != guard[rel]:
            raise RuntimeError(f"Backup of {rel} doesn't match the file; not recorded")
        save(path, guard)

    def restore_original(self, rel):
        path, guard = self._guard()
        copy = self.backup / "_originals" / rel
        if rel not in guard or not copy.is_file() or sha256(copy) != guard[rel]:
            raise RuntimeError(f"No verified original of {rel} to restore. Use Steam's 'Verify integrity of game files'.")
        shutil.copy2(copy, self.root / rel)
        if sha256(self.root / rel) != guard[rel]:
            raise RuntimeError(f"Restoring {rel} failed (is the game still running?)")


def mod_report(g):
    """Why enabled mods may not work: what their DLLs need or call that this game doesn't have, and which mod each
    error in the last game session's log came from. Reads files only; nothing is run."""
    import mod_compat
    lines = [f"Mod loader: {n}" for n in mod_compat.loader_notes(g)]
    gone = {m: [rel for rel in files if not g.target(rel).exists()] for m, files in g.enabled.items()}
    for m, rels in gone.items():
        if rels:
            lines.append(f"[{m}] is enabled but {len(rels)} of its files are missing from the game (deleted outside the "
                         f"Mod Manager, e.g. {rels[0]}). Disable and enable it again to put them back.")
    if lines:
        lines.append("")
    lines.append("Mods that install fine but can't fully work in this game:")
    notes = [(m, n) for m in g.enabled if (g.mods_dir / m).is_dir() for n in mod_compat.check(g, g.mods_dir / m, g.files(m))]
    lines += [f"  - [{m}] {n}" for m, n in notes] or ["  (none found)"]
    log, report = mod_compat.log_report(g, {m: [g.target(rel) for rel in files] for m, files in g.enabled.items()})
    if log is None:
        lines += ["", "No game log yet: launch the game once, then check again."]
    else:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(log.stat().st_mtime))
        lines += ["", f"Errors in the last game session (log {log}, {when}):"]
        lines += [f"  - {who}: {count}x  {first}" for who, count, first in report] or ["  (none)"]
    return lines


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
for _name, _res, _args in [
    ("OpenProcess", wt.HANDLE, [wt.DWORD, wt.BOOL, wt.DWORD]),
    ("IsWow64Process", wt.BOOL, [wt.HANDLE, ctypes.POINTER(wt.BOOL)]),
    ("VirtualAllocEx", wt.LPVOID, [wt.HANDLE, wt.LPVOID, ctypes.c_size_t, wt.DWORD, wt.DWORD]),
    ("VirtualFreeEx", wt.BOOL, [wt.HANDLE, wt.LPVOID, ctypes.c_size_t, wt.DWORD]),
    ("WriteProcessMemory", wt.BOOL, [wt.HANDLE, wt.LPVOID, wt.LPCVOID, ctypes.c_size_t, wt.LPVOID]),
    ("GetModuleHandleW", wt.HMODULE, [wt.LPCWSTR]),
    ("GetProcAddress", wt.LPVOID, [wt.HMODULE, wt.LPCSTR]),
    ("CreateRemoteThread", wt.HANDLE, [wt.HANDLE, wt.LPVOID, ctypes.c_size_t, wt.LPVOID, wt.LPVOID, wt.DWORD, wt.LPVOID]),
    ("WaitForSingleObject", wt.DWORD, [wt.HANDLE, wt.DWORD]),
    ("GetExitCodeThread", wt.BOOL, [wt.HANDLE, ctypes.POINTER(wt.DWORD)]),
    ("CloseHandle", wt.BOOL, [wt.HANDLE]),
]:
    getattr(k32, _name).restype, getattr(k32, _name).argtypes = _res, _args


def check(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return ok


def inject(pid, dll):
    """LoadLibraryW `dll` inside process `pid` (classic CreateRemoteThread injection)."""
    path = ctypes.create_unicode_buffer(str(Path(dll).resolve()))
    size = ctypes.sizeof(path)
    proc = check(k32.OpenProcess(0x43A, False, pid))  # CREATE_THREAD|VM_OPERATION|VM_READ|VM_WRITE|QUERY_INFORMATION
    try:
        wow = wt.BOOL()
        check(k32.IsWow64Process(proc, ctypes.byref(wow)))
        if wow.value:
            raise RuntimeError("Target is a 32-bit process: run modman with 32-bit Python")
        mem = check(k32.VirtualAllocEx(proc, None, size, 0x3000, 0x04))  # COMMIT|RESERVE, READWRITE
        check(k32.WriteProcessMemory(proc, mem, path, size, None))
        load_library = check(k32.GetProcAddress(k32.GetModuleHandleW("kernel32.dll"), b"LoadLibraryW"))
        thread = check(k32.CreateRemoteThread(proc, None, 0, load_library, mem, 0, None))
        try:
            if k32.WaitForSingleObject(thread, 15000):
                raise RuntimeError(f"{Path(dll).name}: DllMain did not return within 15s")
            code = wt.DWORD()
            check(k32.GetExitCodeThread(thread, ctypes.byref(code)))
        finally:
            k32.CloseHandle(thread)
        k32.VirtualFreeEx(proc, mem, 0, 0x8000)  # skipped on timeout: the thread may still be reading it
        # ponytail: exit code is the HMODULE's low 32 bits, so ~1 in 65536 loads reads as a false failure.
        if not code.value:
            raise RuntimeError(f"LoadLibrary failed inside the target for {dll} (wrong bitness or missing dependency?)")
    finally:
        k32.CloseHandle(proc)


def pids(exe):
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {exe}"], capture_output=True,
                         text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    # an exited game can linger as a 48 K husk while Steam holds its handle; only count ones using real memory
    return [int(r[1]) for r in csv.reader(out.splitlines()) if len(r) > 4 and r[0].lower() == exe.lower()
            and int(re.sub(r"\D", "", r[4]) or 0) > 1024]


IMAGE_DIRS = ("Decals", "Paint")
IMAGE_EXTS = (".png", ".jpg", ".jpeg")
REF = re.compile(r'"(imageURL|colourMapUrl)"\s*:\s*"((?:[^"\\]|\\.)*)"')
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def image_refs(text):
    """[(kind, ref)] for every decal image / paint colour map in a blueprint's JSON text."""
    return [("decal" if key == "imageURL" else "paint", json.loads(f'"{val}"')) for key, val in REF.findall(text) if val]


def image_rel(ref):
    """'Sprocket/Decals/a.png' or 'file:///C:/.../My%20Games/Sprocket/Decals/a.png' -> 'Decals/a.png'. Built-in -> None."""
    m = re.search(r"(?:^|/)Sprocket/((?:Decals|Paint)/.+)", unquote(ref) if ref.startswith("file:") else ref)
    return m and m.group(1)


class Images:
    """Sprocket's Decals/ and Paint/ folders plus which blueprints use which image."""

    def __init__(self, user, backup):
        self.user, self.backup = Path(user), Path(backup)
        self.scan()

    def scan(self):
        self.uses, self.users = {}, {}  # blueprint -> [(kind, ref, rel)]; rel.lower() -> {blueprints}
        for bp in (self.user / "Factions").rglob("*.blueprint"):
            text = bp.read_bytes().decode("utf-8", "replace")
            self.uses[bp] = [(kind, ref, image_rel(ref)) for kind, ref in image_refs(text)]
            for _, _, rel in self.uses[bp]:
                if rel:
                    self.users.setdefault(rel.lower(), set()).add(bp)

    def move(self, pairs):
        """Move/rename images [(old, new)] ('Decals/sub/a.png' style) and repoint every blueprint using them."""
        pairs, renames = list(pairs), {}
        for old, new in pairs:
            root = old.split("/")[0]
            if new.split("/")[0] != root or root not in IMAGE_DIRS:
                raise RuntimeError(f"{old}: images have to stay inside their own Decals or Paint folder")
            if (self.user / new).exists() or new.lower() in {n.lower() for n in renames.values()}:
                raise RuntimeError(f"{new} already exists")
            renames[old.lower()] = new
        edits = {}
        for bp in {bp for old in renames for bp in self.users.get(old, ())}:
            text = bp.read_bytes().decode("utf-8")
            for _, ref in image_refs(text):
                new = renames.get((image_rel(ref) or "").lower())
                if new:
                    fixed = (self.user / new).as_uri() if ref.startswith("file:") else f"Sprocket/{new}"
                    text = text.replace(json.dumps(ref, ensure_ascii=False), json.dumps(fixed, ensure_ascii=False))
            if any((image_rel(ref) or "").lower() in renames for _, ref in image_refs(text)):
                raise RuntimeError(f"Couldn't update {bp.name}, nothing was moved")
            edits[bp] = text
        moved = []
        try:
            for old, new in pairs:
                (self.user / new).parent.mkdir(parents=True, exist_ok=True)
                os.replace(self.user / old, self.user / new)
                moved.append((old, new))
        except BaseException:
            for old, new in reversed(moved):
                os.replace(self.user / new, self.user / old)
            raise
        keep = self.backup / time.strftime("%Y%m%d-%H%M%S")
        for bp, text in edits.items():
            (keep / bp.relative_to(self.user)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bp, keep / bp.relative_to(self.user))
            bp.write_bytes(text.encode("utf-8"))
        self.scan()
        return len(edits)

    def zip(self, bps, out):
        """Zip blueprints + the decals/paint they use, laid out like My Games/Sprocket. Returns images not on disk.
        Old file:/// image links (only valid on this PC) become Sprocket/... links in the zipped copy."""
        images, missing = {}, set()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.comment = b"Extract into Documents/My Games/Sprocket, or add it as a mod in Mod Manager"
            for bp in bps:
                text = bp.read_bytes().decode("utf-8")
                for _, ref, rel in self.uses[bp]:
                    if not rel:
                        continue
                    if ref.startswith("file:"):
                        text = text.replace(json.dumps(ref, ensure_ascii=False), json.dumps(f"Sprocket/{rel}", ensure_ascii=False))
                    if (self.user / rel).is_file():
                        images[rel.lower()] = rel
                    else:
                        missing.add(rel)
                name = bp.relative_to(self.user).as_posix()
                if name not in z.namelist():
                    z.writestr(name, text.encode("utf-8"))
                faction = self.user / "Factions" / bp.relative_to(self.user / "Factions").parts[0]
                extras = [bp.with_suffix(".bpMeta"), bp.parent / "Profiles" / f"{bp.stem}.png"]
                if faction.name != "Default":  # a custom faction only shows up in game with its .fdef
                    extras.append(faction / f"{faction.name}.fdef")
                for extra in extras:
                    if extra.is_file() and extra.relative_to(self.user).as_posix() not in z.namelist():
                        z.write(extra, extra.relative_to(self.user).as_posix())
            for rel in sorted(images.values(), key=str.lower):
                z.write(self.user / rel, rel)
        return sorted(missing, key=str.lower)


TURRET_RING = "99281776-6b29-4ffb-9d8b-04139ca7b6a2"
TRAVERSE_MOTOR = "147d4042-4a13-4477-9adf-12e8291481e0"
ADDON_STRUCTURE = "8f8a9d20-eb45-482e-b149-014c964c4e2c"
PROJECTED_DECAL = "e59ff736-a6ea-4a1a-a4c5-6437ed15b872"


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def euler_to_matrix(rot):
    """Unity's Quaternion.Euler(x, y, z) as a 3x3 matrix: rotate about z, then x, then y (degrees)."""
    x, y, z = map(math.radians, rot[:3])
    rx = [[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]]
    ry = [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]
    rz = [[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]]
    return matmul(ry, matmul(rx, rz))


def matrix_to_euler(m):
    x = math.asin(max(-1.0, min(1.0, -m[1][2])))
    if abs(m[1][2]) < 0.999999:
        y, z = math.atan2(m[0][2], m[2][2]), math.atan2(m[1][0], m[1][1])
    else:  # gimbal lock (pitch +-90): fold roll into yaw
        y, z = math.atan2(-m[2][0], m[0][0]), 0.0
    return [math.degrees(a) % 360 for a in (x, y, z)]


def turrets(bp):
    """[(ring vuid, description)] for each turret in a parsed blueprint."""
    if "objects" not in bp:
        raise RuntimeError("This blueprint is in an old save format. Open it in Sprocket, save it once, then try again.")
    kids = {}
    for o in bp["objects"]:
        kids.setdefault(o["pvuid"], []).append(o)

    def under(v):
        return [d for c in kids.get(v, []) for d in [c, *under(c["vuid"])]]

    out = []
    for o in bp["objects"]:
        if o["guid"] == TURRET_RING:
            parts = under(o["vuid"])
            x, y, z = o["transform"]["pos"]
            out.append((o["vuid"], f"Turret {len(out) + 1}:  {sum('cannon' in p for p in parts)} gun(s), "
                                   f"{len(parts)} parts, at x {x:.2f}  y {y:.2f}  z {z:.2f}"))
    return out


def turret_to_addon(bp, rings):
    """Turn turrets (by ring vuid) of a parsed blueprint into add-on structures, in place.
    The turret body keeps its shape, add-ons and decals and sits where the ring sat. The ring and traverse
    motor go. Everything else on the turret (guns, crew, hatches, other turrets) moves to the part the
    turret sat on, at the same spot, so nothing you built is lost."""
    objs = {o["vuid"]: o for o in bp["objects"]}
    removed = set()
    for ring in (objs[v] for v in rings):
        body = objs[ring.get("structureID", ring.get("compartmentBodyID", {}).get("structureVuid"))]
        # Seen in real saves: bodies are never rotated/scaled, rings are (sloped hulls, sponsons, rear turrets).
        if any(body["transform"]["rot"]) or {1.0} != {*body["transform"]["scale"], *ring["transform"]["scale"]}:
            raise RuntimeError("This turret has a rotated or scaled body, which isn't supported")
        ring_pos, ring_rot = ring["transform"]["pos"], euler_to_matrix(ring["transform"]["rot"])
        tilted = any(ring["transform"]["rot"])

        def lift(o, local):  # move `o` from the turret's frame to the ring's parent, same spot in the world
            t = o["transform"]
            t["pos"] = [p + sum(ring_rot[i][k] * local[k] for k in range(3)) for i, p in enumerate(ring_pos)]
            if tilted:  # the 4th rot value is the placement tool's spin around the face; it's relative, keep it
                t["rot"] = matrix_to_euler(matmul(ring_rot, euler_to_matrix(t["rot"]))) + t["rot"][3:]
            o["pvuid"] = ring["pvuid"]

        body_local = body["transform"]["pos"]
        for o in objs.values():
            on_body = o["pvuid"] == body["vuid"]
            if on_body and o["guid"] == TRAVERSE_MOTOR:
                removed.add(o["vuid"])
            elif o["pvuid"] == ring["vuid"] and o is not body:
                lift(o, o["transform"]["pos"])
            elif on_body and o["guid"] not in (ADDON_STRUCTURE, PROJECTED_DECAL):
                lift(o, [a + b for a, b in zip(body_local, o["transform"]["pos"])])
        lift(body, body_local)
        body["guid"], body["transform"]["rot"] = ADDON_STRUCTURE, list(ring["transform"]["rot"])  # exact, body had none
        removed.add(ring["vuid"])
    stack = list(removed)  # anything hanging off a removed part goes with it
    while stack:
        v = stack.pop()
        for o in objs.values():
            if o["pvuid"] == v and o["vuid"] not in removed:
                removed.add(o["vuid"])
                stack.append(o["vuid"])

    gone = [objs[v] for v in removed]
    kept = [o for o in bp["objects"] if o["vuid"] not in removed]
    is_block_ref = lambda k: k.endswith(("BlueprintVuid", "ConstraintsVuid"))
    dead_components = {v for o in gone for k, v in o.items() if isinstance(v, int) and not is_block_ref(k)
                       and k not in ("vuid", "pvuid", "flags", "structureID")}
    still_used = {v for o in kept for k, v in o.items() if is_block_ref(k)}
    dead_blocks = {v for o in gone for k, v in o.items() if is_block_ref(k)} - still_used
    bp["objects"] = kept
    bp["blueprints"] = [b for b in bp["blueprints"] if b["id"] not in dead_blocks]
    for b in bp["blueprints"]:  # e.g. the gunner seat lists the traverse motor it operated
        for k, v in b["blueprint"].items():
            if isinstance(v, list) and v and all(isinstance(x, int) for x in v):
                b["blueprint"][k] = [x for x in v if x not in dead_components]
    for o in kept:
        if o["transform"].get("mirrorVuid") in removed:
            o["transform"]["mirrorVuid"] = -1


def guarded(fn, then=None):
    """Tk callback that shows errors in a dialog instead of dying silently, then runs `then`."""
    def run(*_):
        from tkinter import messagebox
        try:
            fn()
        except Exception as e:
            messagebox.showerror("Mod Manager", str(e))
        if then:
            then()
    return run


def dark(win):
    """Dark colours for every Tk/ttk widget made after this call, plus a dark Windows title bar."""
    from tkinter import ttk
    bg, field, fg, sel, line = "#1e1f22", "#2b2d30", "#dfe1e5", "#2f65ca", "#43454a"
    for pattern, value in [("*Background", bg), ("*Foreground", fg), ("*Entry.Background", field),
                           ("*Listbox.Background", field), ("*selectBackground", sel), ("*selectForeground", "white"),
                           ("*insertBackground", fg), ("*activeBackground", line), ("*activeForeground", fg),
                           ("*highlightBackground", bg), ("*TCombobox*Listbox.Background", field)]:
        win.option_add(pattern, value)
    win.configure(bg=bg)
    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=line, darkcolor=bg,
                    lightcolor=bg, troughcolor=bg, arrowcolor=fg, selectbackground=sel, selectforeground="white")
    style.map(".", background=[("disabled", bg)], foreground=[("disabled", "#80848b")])
    style.configure("TButton", background=field, padding=(10, 4))
    style.map("TButton", background=[("pressed", sel), ("active", line)])
    style.configure("Treeview", background=field, fieldbackground=field)
    style.map("Treeview", background=[("selected", sel)], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", background=bg)
    style.map("Treeview.Heading", background=[("active", line)])
    style.configure("TNotebook.Tab", background=bg, padding=(12, 4))
    style.map("TNotebook.Tab", background=[("selected", field), ("active", line)], foreground=[("!selected", "#80848b")])
    style.map("TCombobox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
              selectbackground=[("readonly", field)], background=[("active", line)])
    style.configure("TScrollbar", background=line, troughcolor=bg, bordercolor=bg)
    try:  # DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 10 2004+)
        win.update_idletasks()
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.windll.user32.GetParent(win.winfo_id()), 20,
                                                   ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass


def images_window(parent, lib, exe):
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    def walk(tree, node=""):
        for i in tree.get_children(node):
            yield i
            yield from walk(tree, i)

    def label(bp):
        return bp.relative_to(lib.user / "Factions").with_suffix("").as_posix().replace("/Blueprints/", "/")

    def show(path):
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as im:
                size = im.size
                im.thumbnail((320, 320))
                preview.photo = ImageTk.PhotoImage(im)
            preview.configure(image=preview.photo, text=f"{path.name}   {size[0]} x {size[1]}")
        except Exception:
            preview.configure(image="", text=f"{path.name}\n({'no preview' if path.exists() else 'file is missing'})")

    def fill_detail(lines):  # [(text, ("img", rel) | ("bp", iid) | None)]
        detail.delete(0, "end")
        rows[:] = [target for _, target in lines]
        for text, _ in lines:
            detail.insert("end", text)

    def refill():
        lib.scan()
        opened = {i for t in (images, bps) for i in walk(t) if t.item(i, "open")}
        images.delete(*images.get_children())
        bps.delete(*bps.get_children())
        listed.clear()

        def add(folder, node):
            for p in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                rel = p.relative_to(lib.user).as_posix()
                if p.is_dir():
                    add(p, images.insert(node, "end", iid=rel, text=p.name, open=rel in opened))
                elif p.suffix.lower() in IMAGE_EXTS:
                    listed[rel.lower()] = rel
                    images.insert(node, "end", iid=rel, text=p.name, values=(len(lib.users.get(rel.lower(), ())),))
        for d in IMAGE_DIRS:
            (lib.user / d).mkdir(exist_ok=True)
            add(lib.user / d, images.insert("", "end", iid=d, text=d, open=True))
        missing = {r.lower(): r for refs in lib.uses.values() for _, _, r in refs if r and r.lower() not in listed}
        if missing:
            node = images.insert("", "end", iid="?missing", text=f"Missing, used but not on disk ({len(missing)})")
            for rel in sorted(missing.values(), key=str.lower):
                images.insert(node, "end", iid=f"?missing/{rel}", text=rel, values=(len(lib.users[rel.lower()]),))

        for bp in sorted(lib.uses, key=lambda b: label(b).lower()):
            parts, node = label(bp).split("/"), ""
            for i in range(len(parts) - 1):
                folder = "/".join(parts[:i + 1])
                if not bps.exists(folder):
                    bps.insert(node, "end", iid=folder, text=parts[i], open=folder in opened)
                node = folder
            rels = {r.lower() for _, _, r in lib.uses[bp] if r}
            bps.insert(node, "end", iid=str(bp), text=parts[-1], values=(len(rels), sum(r not in listed for r in rels) or ""))

    def on_image():
        sel = images.selection()
        if not sel or sel[0] in IMAGE_DIRS or sel[0] == "?missing" or (lib.user / sel[0]).is_dir():
            return
        rel = sel[0].removeprefix("?missing/")
        show(lib.user / rel)
        users = sorted(lib.users.get(rel.lower(), ()), key=lambda b: label(b).lower())
        fill_detail([(f"Used by {len(users)} blueprint(s):", None)] + [(f"   {label(b)}", ("bp", str(b))) for b in users])

    def on_blueprint():
        sel = bps.selection()
        if not sel or not sel[0].endswith(".blueprint"):
            return
        refs, lines = lib.uses[Path(sel[0])], []
        for kind in ("paint", "decal"):
            counts = Counter(rel or ref for k, ref, rel in refs if k == kind)
            lines.append((f"{kind.title()} ({len(counts)}):", None))
            for name, n in sorted(counts.items(), key=lambda kv: kv[0].lower()):
                is_file = name.split("/")[0] in IMAGE_DIRS
                text = name if is_file else "built-in" if GUID.fullmatch(name) else name
                note = "   MISSING" if is_file and name.lower() not in listed else ""
                lines.append((f"   {text}{f'  x{n}' if n > 1 else ''}{note}", ("img", name) if is_file else None))
        fill_detail(lines)
        preview.configure(image="", text=Path(sel[0]).stem)

    def on_detail():
        pick = detail.curselection()
        if pick and rows[pick[0]] and rows[pick[0]][0] == "img":
            show(lib.user / rows[pick[0]][1])

    def jump():  # double-click a detail line: open that image / blueprint in its tab
        pick = detail.curselection()
        if not pick or not rows[pick[0]]:
            return
        kind, key = rows[pick[0]]
        tree, tab = (images, img_tab) if kind == "img" else (bps, bp_tab)
        if kind == "img":
            key = listed.get(key.lower(), f"?missing/{key}")
        if tree.exists(key):
            tabs.select(tab)
            tree.see(key)
            tree.selection_set(key)

    def chosen():
        sel = [i for i in images.selection() if i not in IMAGE_DIRS and not i.startswith("?")]
        if not sel:
            raise RuntimeError("Select images or folders in the Images tab first")
        return sel

    def pairs_for(iid, dest):  # a folder moves every image inside it
        p = lib.user / iid
        if p.is_file():
            return [(iid, dest)]
        return [(q.relative_to(lib.user).as_posix(), f"{dest}/{q.relative_to(p).as_posix()}")
                for q in p.rglob("*") if q.suffix.lower() in IMAGE_EXTS]

    def apply(pairs, folders):
        if pids(exe):
            raise RuntimeError("Close Sprocket first, it could save over the updated blueprints")
        n = lib.move(pairs)
        for f in folders:  # drop folders the move left empty
            for d in sorted((lib.user / f).rglob("*"), reverse=True) + [lib.user / f]:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
        status["text"] = f"Moved {len(pairs)} image(s), updated {n} blueprint(s). Old copies in {lib.backup}"

    def move_to():
        sel = chosen()
        dest = filedialog.askdirectory(parent=win, title="Move to folder (use Make New Folder for a new one)",
                                       initialdir=lib.user / sel[0].split("/")[0])
        if not dest:
            return
        try:
            dest = Path(dest).resolve().relative_to(lib.user.resolve()).as_posix()
        except ValueError:
            raise RuntimeError("Pick a folder inside Decals or Paint") from None
        apply([pair for i in sel for pair in pairs_for(i, f"{dest}/{Path(i).name}")],
              [i for i in sel if (lib.user / i).is_dir()])

    def rename():
        old = Path(chosen()[0])
        new = simpledialog.askstring("Rename", "New name:", initialvalue=old.name, parent=win)
        if not new or new == old.name:
            return
        if (lib.user / old).is_file() and not Path(new).suffix:
            new += old.suffix
        apply(pairs_for(old.as_posix(), f"{old.parent.as_posix()}/{new}"), [old.as_posix()] if (lib.user / old).is_dir() else [])

    def select_unused():
        unused = [rel for key, rel in listed.items() if not lib.users.get(key)]
        images.selection_set(unused)
        status["text"] = f"Selected {len(unused)} unused image(s). 'Move to folder' tidies them away."

    def open_folder():
        sel = [i for i in images.selection() if not i.startswith("?")]
        p = lib.user / (sel[0] if sel else "Decals")
        os.startfile(p if p.is_dir() else p.parent)

    def zip_selected():
        chosen_bps = sorted({Path(i) for s in bps.selection() for i in [s, *walk(bps, s)] if i.endswith(".blueprint")})
        if not chosen_bps:
            raise RuntimeError("Select blueprints, or a faction/folder to zip all of it")
        name = chosen_bps[0].stem if len(chosen_bps) == 1 else bps.item(bps.selection()[0], "text")
        out = filedialog.asksaveasfilename(parent=win, title="Save blueprint zip", initialfile=f"{name}.zip",
                                           initialdir=Path.home() / "Desktop", defaultextension=".zip",
                                           filetypes=[("Zip", "*.zip")])
        if not out:
            return
        missing = lib.zip(chosen_bps, out)
        status["text"] = f"Zipped {len(chosen_bps)} blueprint(s) with their paint and decals to {out}"
        if missing:
            messagebox.showwarning("Decals & Paint", "Zipped, but these images aren't on this PC so they're not in it:\n"
                                   + "\n".join(missing), parent=win)

    def pick(title, prompt, options):  # multi-select list dialog, returns chosen indexes
        dlg = tk.Toplevel(win)
        dlg.title(title)
        dlg.transient(win)
        dark(dlg)
        ttk.Label(dlg, text=prompt).pack(padx=10, pady=(10, 4), anchor="w")
        box = tk.Listbox(dlg, selectmode="extended", width=70, height=min(10, len(options)), activestyle="none")
        box.pack(padx=10, fill="both", expand=True)
        for option in options:
            box.insert("end", option)
        box.selection_set(0)
        chosen = []
        ttk.Button(dlg, text="Convert", command=lambda: (chosen.extend(box.curselection()), dlg.destroy())).pack(pady=10)
        dlg.grab_set()
        dlg.wait_window()
        return chosen

    def convert_turrets():
        sel = [i for i in bps.selection() if i.endswith(".blueprint")]
        if len(sel) != 1:
            raise RuntimeError("Select one blueprint first")
        src = Path(sel[0])
        bp = json.loads(src.read_bytes().decode("utf-8"))
        found = turrets(bp)
        if not found:
            raise RuntimeError(f"{src.stem} has no turrets")
        chosen = pick("Turret to add-on", f"Turn which turret(s) of {src.stem} into add-on structures?\n"
                      "Guns, crew and other parts on them move to the hull, at the same spot.", [t for _, t in found])
        if not chosen:
            return
        turret_to_addon(bp, [found[i][0] for i in chosen])
        out, n = src.with_name(f"{src.stem} (add-on).blueprint"), 2
        while out.exists():
            out, n = src.with_name(f"{src.stem} (add-on {n}).blueprint"), n + 1
        bp["header"]["name"] = out.stem
        out.write_bytes(json.dumps(bp, indent=2, ensure_ascii=False).replace("\n", "\r\n").encode("utf-8"))
        status["text"] = f"Saved {out.name} next to the original (the original is untouched). Open it in Sprocket."

    def tree_tab(title, columns, buttons=()):
        frame = ttk.Frame(tabs)
        tabs.add(frame, text=title)
        bar = ttk.Frame(frame)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        for text, fn in buttons:
            ttk.Button(bar, text=text, command=guarded(fn, refill if fn in (move_to, rename, convert_turrets) else None)).pack(
                side="left", padx=(0, 6))
        tree = ttk.Treeview(frame, columns=columns, height=24)
        tree.column("#0", width=340)
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=70, anchor="e")
        scroll = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return frame, tree

    win = tk.Toplevel(parent)
    win.title("Decals & Paint")
    dark(win)
    body = ttk.Frame(win)
    body.pack(fill="both", expand=True, padx=8, pady=6)
    tabs = ttk.Notebook(body)
    tabs.pack(side="left", fill="both", expand=True)
    side = ttk.Frame(body)
    side.pack(side="left", fill="y", padx=(8, 0))
    preview = ttk.Label(side, anchor="center", compound="top", text="Select an image or blueprint")
    preview.pack(fill="x")
    detail = tk.Listbox(side, width=50, height=20, activestyle="none")
    detail.pack(fill="both", expand=True, pady=(6, 0))
    status = ttk.Label(win, text="Double-click a line on the right to jump to that image or blueprint.")
    status.pack(fill="x", padx=8, pady=(0, 6))
    rows, listed = [], {}  # detail line targets; image rel.lower() -> rel for every image on disk
    img_tab, images = tree_tab("Images", ["used by"], [("Move to folder...", move_to), ("Rename...", rename),
                                                      ("Select unused", select_unused), ("Open folder", open_folder),
                                                      ("Refresh", refill)])
    bp_tab, bps = tree_tab("Blueprints", ["images", "missing"],
                           [("Zip...", zip_selected), ("Turret to add-on...", convert_turrets)])
    images.bind("<<TreeviewSelect>>", guarded(on_image))
    bps.bind("<<TreeviewSelect>>", guarded(on_blueprint))
    detail.bind("<<ListboxSelect>>", guarded(on_detail))
    detail.bind("<Double-1>", guarded(jump))
    refill()


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    import loader_setup
    cfg = HOME / "games.json"
    games = load(cfg, {})
    # First run: the game this folder sits in, else Sprocket in any Steam library.
    found = None if games else HOME.parent if (HOME.parent / 'Sprocket.exe').is_file() else loader_setup.find_sprocket()
    if found:
        games['Sprocket'] = {'dir': str(found), 'exe': 'Sprocket.exe',
                             'route': {'BepInEx': '', 'dotnet': '', 'MLLoader': '',
                                       'Mods': 'MLLoader', 'Plugins': 'MLLoader',
                                       'UserLibs': 'MLLoader', 'UserData': 'MLLoader'}}
        save(cfg, games)
    installing = False

    def game():
        if not pick.get():
            raise RuntimeError("Add a game first")
        return Game(HOME, pick.get(), **games[pick.get()])

    def act(fn):
        return guarded(fn, refresh)

    def open_images():
        g = game()
        user = g.roots.get("_user")
        if not user or not (user / "Decals").is_dir():
            raise RuntimeError(f"{g.name} has no Decals/Paint folder set up (a '_user' root in games.json)")
        images_window(win, Images(user, HOME / "blueprint-backups"), Path(g.exe).name)

    def refresh():
        sel = box.curselection()
        box.delete(0, "end")
        if pick.get():
            g = game()
            for m in g.mods():
                box.insert("end", f"[{'x' if m in g.enabled else ' '}] {m}")
        if sel:
            box.selection_set(sel[0])

    def selected():
        if not box.curselection():
            raise RuntimeError("Select a mod first")
        return box.get(box.curselection()[0])[4:]

    def toggle():
        g, m = game(), selected()
        if m in g.enabled:
            kept = g.disable(m)
            status["text"] = f"Disabled {m}"
            if kept:
                messagebox.showinfo("Mod Manager", "Kept these because they changed after install:\n" + "\n".join(kept))
        else:
            files = list(g.enable(m))
            status["text"] = f"Enabled {m}: {len(files)} file(s) -> {os.path.commonpath(files) if files else '-'}"
            import mod_compat
            notes = mod_compat.check(g, g.mods_dir / m, g.files(m))
            if notes:
                messagebox.showwarning("Mod Manager", f"{m} is enabled, but it won't fully work in this game:\n\n" + "\n\n".join(notes))

    def remove_mod():
        g, m = game(), selected()
        if not messagebox.askyesno("Remove mod", f"Remove {m}?\n\nIts files leave the game, your original files come "
                                   "back, and the Mod Manager's copy is deleted. To use it again, add it again."):
            return
        kept = g.remove(m)
        status["text"] = f"Removed {m}"
        if kept:
            messagebox.showinfo("Mod Manager", "Kept these because they changed after install:\n" + "\n".join(kept))

    def show_report():
        g = game()
        status["text"] = "Checking mods..."
        win.update_idletasks()
        text = "\n".join(mod_report(g))
        status["text"] = "Mod report ready."
        top_win = tk.Toplevel(win)
        top_win.title(f"Mod report - {g.name}")
        view = tk.Text(top_win, wrap="word", width=110, height=34, font=("Consolas", 10))
        bar = ttk.Scrollbar(top_win, command=view.yview)
        view.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        view.pack(fill="both", expand=True)
        view.insert("1.0", text)
        view.configure(state="disabled")

    def add_game():
        d = filedialog.askdirectory(title="Game install folder")
        exe = d and filedialog.askopenfilename(title="Game executable", initialdir=d, filetypes=[("Programs", "*.exe")])
        if exe:
            games[Path(d).name] = {"dir": d, "exe": os.path.relpath(exe, d)}
            save(cfg, games)
            pick["values"] = sorted(games)
            pick.set(Path(d).name)

    def add_mod():
        picked = filedialog.askopenfilenames(title="Mod files: .zip, .blueprint, .png, ... (cancel to pick a folder)")
        picked = picked or [filedialog.askdirectory(title="Mod folder")]
        added = [game().add(p) for p in picked if p]
        if added:
            status["text"] = f"Added {', '.join(added)}"

    def check_files(launching=False):
        """Game file guard: say if a core game file was changed outside the Mod Manager and offer to restore it."""
        g = game()
        for rel, state in g.check_files():
            if state == "changed" and messagebox.askyesno("Game files", f"{rel} has been changed outside the Mod Manager, "
                    "for example by a patcher. Patched game code breaks after Sprocket updates and can crash the game.\n\n"
                    f"Restore the original {rel} now?" + ("\n(No = launch with the changed file.)" if launching else "")):
                g.restore_original(rel)
                messagebox.showinfo("Game files", f"Original {rel} restored.")
            elif state == "unknown" and messagebox.askyesno("Game files", f"{rel} doesn't match a known original Sprocket release.\n\n"
                    "Yes: this is a fresh Sprocket update from Steam, keep it as the new original.\n"
                    "No: leave it. If it was patched, use Steam's 'Verify integrity of game files' to get the original back."):
                g.trust(rel)
        states = dict(g.check_files())
        status["text"] = "Game files: " + (", ".join(f"{k} {v}" for k, v in states.items()) or "nothing protected")

    def launch():
        g = game()
        check_files(launching=True)
        subprocess.Popen([str(g.root / g.exe)], cwd=g.root)
        dlls = g.inject_dlls()
        if dlls:
            status["text"] = f"Waiting for {g.exe} to inject {len(dlls)} DLL(s)..."
            win.after(g.delay * 1000, act(lambda: inject_when_up(g, dlls, 60)))

    def inject_when_up(g, dlls, tries):
        found = pids(Path(g.exe).name)
        if not found and tries:
            return win.after(1000, act(lambda: inject_when_up(g, dlls, tries - 1)))
        if not found:
            raise RuntimeError(f"{g.exe} never showed up, nothing injected")
        for d in dlls:
            inject(found[0], d)
        status["text"] = f"Injected {len(dlls)} DLL(s) into {g.exe} (pid {found[0]})"

    def inject_manual():
        dll = filedialog.askopenfilename(title="DLL to inject", filetypes=[("DLL", "*.dll")])
        default = Path(games.get(pick.get(), {}).get("exe", "")).name
        target = dll and simpledialog.askstring("Inject", "Process name or PID:", initialvalue=default)
        if not target:
            return
        pid = int(target) if target.isdigit() else next(iter(pids(target)), None)
        if pid is None:
            raise RuntimeError(f"{target} is not running")
        inject(pid, dll)
        status["text"] = f"Injected {Path(dll).name} into pid {pid}"

    def setup_loader():
        import queue, threading
        nonlocal installing
        if installing:
            return
        g = game()
        loader_setup.validate_game(g, pids)
        # MLLoader only comes from Nexus Mods (it needs a login), so it can't be downloaded here: use a copy the
        # user already has, found in Downloads or the Desktop, and only ask when there's none.
        melon = loader_setup.find_melon(HOME)
        if melon is None:
            ask = loader_setup.needs_melon(g) or messagebox.askyesnocancel('Install mod loader',
                "MLLoader wasn't found in Downloads or on the Desktop. It's only needed for MelonLoader mods, and it "
                f"only comes from Nexus Mods: {loader_setup.MELON_PAGE}\n\n"
                "Yes: choose the MLLoader ZIP you downloaded.\n"
                "No: install without it now. BepInEx mods will work; click Install mod loader again later to add it.\n"
                "Cancel: don't install anything.")
            if ask is None:
                status['text'] = 'Setup cancelled.'
                return
            if ask:
                chosen = filedialog.askopenfilename(title='Choose MLLoader IL2CPP 2.3.9 ZIP (Nexus Iron Nest mod 26)',
                                                    filetypes=[('MLLoader archive', '*.zip')])
                if not chosen:
                    status['text'] = f'Setup cancelled. Get MLLoader IL2CPP 2.3.9 from {loader_setup.MELON_PAGE}'
                    return
                melon = Path(chosen)
        installing = True
        messages = queue.Queue()
        controls = [pick, box, *top.winfo_children()[1:], *bottom.winfo_children()]
        for control in controls:
            control.configure(state='disabled')
        status['text'] = f'Preparing loader for {g.name}...'

        def worker():
            try:
                result = loader_setup.install(g, HOME, melon, pids, lambda text: messages.put(('progress', text)))
                messages.put(('done', result))
            except Exception as error:
                messages.put(('error', str(error)))

        def poll():
            nonlocal installing
            while not messages.empty():
                kind, text = messages.get_nowait()
                status['text'] = text
                if kind != 'progress':
                    installing = False
                    for control in controls:
                        control.configure(state='normal')
                    pick.configure(state='readonly')
                    refresh()
                    if kind == 'error':
                        messagebox.showerror('Loader setup', text)
                    else:
                        import mod_compat
                        if mod_compat.separate_melonloader(g.root):
                            messagebox.showwarning('Loader setup', text + "\n\nThere's also a separate MelonLoader in "
                                "the game folder. Uninstall it with the MelonLoader installer so only one loader runs, "
                                "then add its mods here with Add mod.")
                    return
            win.after(100, poll)

        threading.Thread(target=worker, daemon=True).start()
        win.after(100, poll)

    def close():
        if installing:
            messagebox.showinfo('Loader setup', 'Wait for setup to finish before closing Mod Manager.')
        else:
            win.destroy()

    win = tk.Tk()
    # An error in a button no guarded() wraps would otherwise only reach the (invisible) console.
    win.report_callback_exception = lambda *error: stopped("".join(traceback.format_exception(*error)))
    win.title("Mod Manager")
    win.protocol('WM_DELETE_WINDOW', close)
    dark(win)
    top = ttk.Frame(win)
    top.pack(fill="x", padx=8, pady=6)
    pick = ttk.Combobox(top, values=sorted(games), state="readonly")
    pick.pack(side="left", fill="x", expand=True)
    pick.bind("<<ComboboxSelected>>", act(lambda: check_files()))
    for text, fn in [("Add game", add_game), ("Open mods folder", lambda: os.startfile(game().mods_dir)),
                     ("Decals & Paint", open_images), ("Check game files", lambda: check_files())]:
        ttk.Button(top, text=text, command=act(fn)).pack(side="left", padx=(6, 0))
    box = tk.Listbox(win, width=60, height=18, activestyle="none", font=("Consolas", 10))
    box.pack(fill="both", expand=True, padx=8)
    box.bind("<Double-1>", act(toggle))
    bottom = ttk.Frame(win)
    bottom.pack(fill="x", padx=8, pady=6)
    for text, fn in [("Add mod", add_mod), ("Enable / Disable", toggle), ("Remove mod", remove_mod), ("Refresh", lambda: None), ("Mod report", show_report),
                     ("Install mod loader", setup_loader), ("Launch", launch), ("Inject DLL", inject_manual)]:
        ttk.Button(bottom, text=text, command=act(fn)).pack(side="left", padx=(0, 6))
    status = ttk.Label(win, text="Double-click a mod to enable/disable it.")
    status.pack(fill="x", padx=8, pady=(0, 6))
    if games:
        pick.set(sorted(games)[0])
    refresh()
    if games:
        win.after(200, act(lambda: check_files()))  # after the window shows
    win.mainloop()


def selftest():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "game/Data").mkdir(parents=True)
        (t / "game/a.txt").write_text("orig")
        route = {"BepInEx": "", "Decals": "_user", "*/*.fdef": "_user/Factions",
                 "*.blueprint": "_user/Factions/Default/Blueprints/Vehicles", "*.png": "_user/Decals"}
        g = Game(t, "G", t / "game", roots={"_user": str(t / "user")}, route=route)
        mods = {
            "m1": {"a.txt": "m1", "sub/b.txt": "m1", "_inject/x.dll": ""},
            "m2": {"A.TXT": "m2"},
            "m3": {"Pack/tank.blueprint": "t", "Pack/Decals/d.png": "d", "Fac/Fac.fdef": "f",
                   "Fac/Blueprints/v.blueprint": "v", "BepInEx/plugins/icon.png": "i", "Wrap/Data/x.txt": "x",
                   "_user/Settings.json": "s"},
            "p1": {"Decals/s.png": "same"}, "p2": {"Decals/s.png": "same"}, "p3": {"Decals/s.png": "other"},
        }
        for mod, files in mods.items():
            for rel, text in files.items():
                (g.mods_dir / mod / rel).parent.mkdir(parents=True, exist_ok=True)
                (g.mods_dir / mod / rel).write_text(text)

        g.enable("m1")
        assert (t / "game/a.txt").read_text() == "m1" and (t / "game/sub/b.txt").exists()
        assert not (t / "game/_inject").exists() and len(g.inject_dlls()) == 1
        try:
            g.enable("m2")
            raise AssertionError("conflict not caught")
        except RuntimeError:
            pass
        assert set(Game(t, "G", t / "game").enabled["m1"]) == {"a.txt", "sub/b.txt"}  # persisted
        g.disable("m1")
        assert (t / "game/a.txt").read_text() == "orig" and not (t / "game/sub/b.txt").exists() and not g.enabled

        assert g.files("m3") == {
            "Pack/tank.blueprint": "_user/Factions/Default/Blueprints/Vehicles/tank.blueprint",
            "Pack/Decals/d.png": "_user/Decals/d.png",
            "Fac/Fac.fdef": "_user/Factions/Fac/Fac.fdef",
            "Fac/Blueprints/v.blueprint": "_user/Factions/Fac/Blueprints/v.blueprint",
            "BepInEx/plugins/icon.png": "BepInEx/plugins/icon.png",
            "Wrap/Data/x.txt": "Data/x.txt",
            "_user/Settings.json": "_user/Settings.json",
        }
        g.enable("m3")
        tank = t / "user/Factions/Default/Blueprints/Vehicles/tank.blueprint"
        assert (t / "user/Decals/d.png").read_text() == "d" and tank.exists()
        tank.write_text("re-saved in game")
        assert g.disable("m3") == ["_user/Factions/Default/Blueprints/Vehicles/tank.blueprint"]
        assert tank.exists() and not (t / "user/Decals/d.png").exists() and not g.enabled

        g.enable("p1")
        g.enable("p2")  # identical shared decal is fine
        try:
            g.enable("p3")
            raise AssertionError("differing file not refused")
        except RuntimeError:
            pass
        g.disable("p1")
        assert (t / "user/Decals/s.png").read_text() == "same"  # p2 still needs it
        g.disable("p2")
        assert not (t / "user/Decals/s.png").exists() and not g.enabled

    with tempfile.TemporaryDirectory() as t:
        user = Path(t) / "My Games/Sprocket"
        for rel in ("Decals/a.png", "Decals/b.png", "Paint/p.png"):
            (user / rel).parent.mkdir(parents=True, exist_ok=True)
            (user / rel).write_bytes(b"img")
        bp = user / "Factions/F/Blueprints/Vehicles/T.blueprint"
        bp.parent.mkdir(parents=True)
        old_url, new_url = (user / "Decals/a.png").as_uri(), (user / "Decals/Mine/a.png").as_uri()
        original = ('{\r\n "blueprints": [\r\n'
                    '  {"type": "decal", "blueprint": {"imageURL": "Sprocket/Decals/a.png"}},\r\n'
                    f'  {{"type": "decal", "blueprint": {{"imageURL": "{old_url}"}}}},\r\n'
                    '  {"type": "decal", "blueprint": {"imageURL": "Sprocket/Decals/gone.png"}},\r\n'
                    '  {"type": "paintJob", "blueprint": {"colourMapUrl": "Sprocket/Paint/p.png"}},\r\n'
                    '  {"type": "paintJob", "blueprint": {"colourMapUrl": "821c5c82-a326-46ca-bfd0-bd2a75830ed7"}}\r\n'
                    ' ]\r\n}')
        bp.write_bytes(original.encode())
        assert image_rel("file:///C:/Users/x/Documents/My%20Games/Sprocket/Paint/a%20b.png") == "Paint/a b.png"
        assert image_rel("821c5c82-a326-46ca-bfd0-bd2a75830ed7") is None
        lib = Images(user, Path(t) / "bak")
        assert len(lib.uses[bp]) == 5 and lib.users["decals/a.png"] == {bp} and "decals/b.png" not in lib.users
        assert lib.move([("Decals/a.png", "Decals/Mine/a.png")]) == 1
        assert (user / "Decals/Mine/a.png").exists() and not (user / "Decals/a.png").exists()
        assert bp.read_bytes().decode() == original.replace(f'"{old_url}"', f'"{new_url}"').replace(
            '"Sprocket/Decals/a.png"', '"Sprocket/Decals/Mine/a.png"')  # only the refs changed, CRLF kept
        assert lib.users["decals/mine/a.png"] == {bp} and any((Path(t) / "bak").rglob("T.blueprint"))
        try:
            lib.move([("Decals/b.png", "Paint/b.png")])
            raise AssertionError("cross-folder move not refused")
        except RuntimeError:
            pass

        (user / "Factions/F/F.fdef").write_text("{}")
        (bp.parent / "Profiles").mkdir()
        (bp.parent / "Profiles/T.png").write_bytes(b"img")
        assert lib.zip([bp], Path(t) / "T.zip") == ["Decals/gone.png"]
        with zipfile.ZipFile(Path(t) / "T.zip") as z:
            assert set(z.namelist()) == {"Factions/F/Blueprints/Vehicles/T.blueprint", "Factions/F/F.fdef",
                                         "Factions/F/Blueprints/Vehicles/Profiles/T.png", "Decals/Mine/a.png", "Paint/p.png"}
            zipped = z.read("Factions/F/Blueprints/Vehicles/T.blueprint").decode()
        assert "file:" not in zipped and zipped.count('"Sprocket/Decals/Mine/a.png"') == 2  # portable links

    with tempfile.TemporaryDirectory() as t:  # game file guard
        t = Path(t)
        (t / "game").mkdir()
        core = t / "game/Core.dll"
        core.write_bytes(b"original code")
        known = sha256(core)
        g = Game(t, "G", t / "game", protect=["Core.dll"], originals={"Core.dll": [known]})
        assert g.check_files() == [("Core.dll", "original")]  # known release: backed up automatically
        core.write_bytes(b"patched code")
        assert g.check_files() == [("Core.dll", "changed")]
        g.restore_original("Core.dll")
        assert core.read_bytes() == b"original code" and g.check_files() == [("Core.dll", "original")]
        core.write_bytes(b"new game update")  # after an update the user confirms it as the new original
        g2 = Game(t, "G2", t / "game", protect=["Core.dll"], originals={"Core.dll": [known]})
        assert g2.check_files() == [("Core.dll", "unknown")]
        g2.trust("Core.dll")
        assert g2.check_files() == [("Core.dll", "original")]
        try:
            Game(t, "G3", t / "game", protect=["Core.dll"]).restore_original("Core.dll")
            raise AssertionError("restore without a verified original not refused")
        except RuntimeError:
            pass

    tf = lambda *pos: {"mirrorVuid": -1, "pos": list(pos), "rot": [0.0, 0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    bp = {"v": "2.0", "header": {"name": "T"}, "meshes": [], "objects": [  # shaped like a real RGM-58 save
        {"guid": "7f8a9d20-eb45-482e-b149-014c964c4e2c", "vuid": 0, "pvuid": -1, "flags": 2, "plateStructure": 1,
         "structureBlueprintVuid": 4, "transform": tf(0.0, 0.0, 0.0)},
        {"guid": TURRET_RING, "vuid": 110, "pvuid": 0, "flags": 2, "turretRing": 111, "basket": 112, "decoupler": 113,
         "ringModel": 114, "ringBlueprintVuid": 26, "structureID": 118, "basketBlueprintVuid": 29, "transform": tf(0.0, 1.5, 0.25)},
        {"guid": "7f8a9d20-eb45-482e-b149-014c964c4e2c", "vuid": 118, "pvuid": 110, "flags": 2, "plateStructure": 119,
         "structureBlueprintVuid": 30, "transform": tf(0.0, 0.5, 0.0)},
        {"guid": TRAVERSE_MOTOR, "vuid": 115, "pvuid": 118, "flags": 2, "motor": 116, "motorModel": 117,
         "traverseConstraintsVuid": 27, "motorBlueprintVuid": 28, "transform": tf(0.0, 0.4, 0.0)},
        {"guid": "crew", "vuid": 328, "pvuid": 118, "flags": 2, "crewSeat": 329, "seatBlueprintVuid": 46, "transform": tf(0.5, -0.5, -0.25)},
        {"guid": ADDON_STRUCTURE, "vuid": 152, "pvuid": 118, "flags": 3, "plateStructure": 153,
         "structureBlueprintVuid": 42, "transform": tf(0.0, 0.0, 0.5)},
        {"guid": PROJECTED_DECAL, "vuid": 354, "pvuid": 118, "flags": 2, "decalBlueprintVuid": 353, "transform": tf(0.0, 0.0, 1.0)},
    ], "blueprints": [{"id": i, "type": t, "blueprint": b} for i, t, b in [
        (4, "structure", {}), (26, "turretRing", {"motorVuid": 116}), (27, "turret", {}), (28, "motor", {}),
        (29, "turretBasket", {}), (30, "structure", {}), (42, "structure", {}), (353, "decal", {}),
        (46, "crewSeat", {"operatedBehaviours": [116, 139, 145]})]]}
    assert [v for v, _ in turrets(bp)] == [110]
    turret_to_addon(bp, [110])
    objs = {o["vuid"]: o for o in bp["objects"]}
    assert set(objs) == {0, 118, 328, 152, 354}  # ring + motor gone
    assert objs[118]["guid"] == ADDON_STRUCTURE and objs[118]["pvuid"] == 0 and objs[118]["transform"]["pos"] == [0.0, 2.0, 0.25]
    assert objs[328]["pvuid"] == 0 and objs[328]["transform"]["pos"] == [0.5, 1.5, 0.0]  # crew moved to hull, same spot
    assert objs[152]["pvuid"] == 118 and objs[354]["pvuid"] == 118  # add-ons and decals stay on it
    blocks = {b["id"]: b["blueprint"] for b in bp["blueprints"]}
    assert set(blocks) == {4, 30, 42, 353, 46} and blocks[46]["operatedBehaviours"] == [139, 145]
    close = lambda a, b: all(abs(x - y) < 1e-6 for x, y in zip(a, b))
    for rot in ([10.9, 0, 0], [90, 270, 0], [270, 90, 33], [0.28, 12, 359.7], [45, 200, 80]):  # incl. gimbal lock
        m = euler_to_matrix(rot)
        assert all(close(r1, r2) for r1, r2 in zip(m, euler_to_matrix(matrix_to_euler(m)))), rot
    assert close(euler_to_matrix([90, 270, 0, 0])[1][:1] + [r[1] for r in euler_to_matrix([90, 270, 0])], [0, -1, 0, 0])  # sponson: up -> -x
    rear = dict(bp, objects=[  # rear-facing turret, newer save style (compartmentBodyID)
        {"guid": "hull", "vuid": 0, "pvuid": -1, "flags": 2, "transform": tf(0.0, 0.0, 0.0)},
        {"guid": TURRET_RING, "vuid": 1, "pvuid": 0, "flags": 2, "compartmentBodyID": {"structureVuid": 2},
         "transform": {**tf(0.0, 1.5, -1.0), "rot": [0.0, 180.0, 0.0, 0.0]}},
        {"guid": "body", "vuid": 2, "pvuid": 1, "flags": 2, "transform": tf(0.0, 0.5, 0.0)},
        {"guid": "gun", "vuid": 3, "pvuid": 2, "flags": 2, "transform": {**tf(0.0, 0.0, 1.0), "rot": [0.0, 10.0, 0.0, 0.0]}},
    ])
    turret_to_addon(rear, [1])
    gun, body = next(o for o in rear["objects"] if o["vuid"] == 3), next(o for o in rear["objects"] if o["vuid"] == 2)
    assert close(body["transform"]["pos"], [0, 2.0, -1.0]) and body["transform"]["rot"] == [0.0, 180.0, 0.0, 0.0]
    assert gun["pvuid"] == 0 and close(gun["transform"]["pos"], [0, 2.0, -2.0]) and close(gun["transform"]["rot"], [0, 190, 0, 0])
    try:
        turrets({"v": "0.2", "blueprints": []})
        raise AssertionError("old format not refused")
    except RuntimeError:
        pass

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(1)
        assert child.pid in pids(Path(sys.executable).name)
        inject(child.pid, Path(os.environ["WINDIR"]) / "System32" / "winmm.dll")
    finally:
        child.kill()

    # A manager opened without its other files (as from inside the ZIP) says so; a complete one has no startup problem.
    with tempfile.TemporaryDirectory() as lone:
        assert "inside the ZIP" in startup_problem(Path(lone))
    assert startup_problem() is None
    with tempfile.TemporaryDirectory() as folder:
        log = crash_log("Traceback: test", [Path(folder) / "missing" / "deeper", Path(folder)])
        assert log == Path(folder) / "modman-error.log" and "test" in log.read_text(encoding="utf-8")
    print("selftest ok")


# Double-clicked, modman.pyw has no console: anything that stops it must be said in a box, or it just seems not to open.

def startup_problem(home=HOME):
    """Why the window can't open, said so a player can fix it, or None."""
    missing = [name for name in ("loader_setup.py", "mod_compat.py") if not (home / name).is_file()]
    if missing:
        return (f"The Mod Manager's other files aren't next to it ({', '.join(missing)} missing).\n\n"
                "If you opened it inside the ZIP, drag the ModManager folder out of the ZIP first, "
                "then open modman from that folder.")
    try:
        import tkinter  # noqa: F401  (the window)
    except ImportError:
        return ("Python is installed without Tkinter, the part that draws windows.\n\n"
                "Run the Python installer again, choose Modify, tick \"tcl/tk and IDLE\", finish, "
                "then open the Mod Manager again.")
    return None


def fail(text):
    """Windows' own message box: it works even when Tkinter is what's missing."""
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "Mod Manager", 0x10)  # MB_ICONERROR
    except Exception:
        print(text)


def crash_log(details, folders=None):
    """The full error in modman-error.log (next to the manager, or in Temp if that folder can't be written): its path."""
    for folder in folders or [HOME, Path(tempfile.gettempdir())]:
        try:
            path = folder / "modman-error.log"
            path.write_text(details, encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def stopped(details):
    """An error nothing else caught: saved and shown, never silent."""
    log = crash_log(details)
    fail("The Mod Manager hit an error:\n\n" + details.strip().splitlines()[-1]
         + (f"\n\nThe details are saved in {log}. Send that file when you ask for help." if log else ""))


if __name__ == "__main__":
    if sys.version_info < (3, 9):  # str.removeprefix, Path.is_relative_to
        fail(f"Mod Manager needs Python 3.9 or newer; this is Python {sys.version.split()[0]}. Get it from python.org.")
        sys.exit(1)
    if "--selftest" in sys.argv:
        selftest()
    elif "--report" in sys.argv:  # python modman.pyw --report "<game name from games.json>"
        name = sys.argv[sys.argv.index("--report") + 1]
        print("\n".join(mod_report(Game(HOME, name, **load(HOME / "games.json", {})[name]))))
    else:
        problem = startup_problem()
        if problem:
            fail(problem)
            sys.exit(1)
        try:
            gui()
        except Exception:
            stopped(traceback.format_exc())
            sys.exit(1)
