"""One-click updates for Hans21223's mods, this manager and its loader, from their GitHub releases. A release is offered
only when its sp-compat line fits the installed Sprocket, and every download is checked against the release's SHA-256."""
import json
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request

import loader_setup
from mod_compat import Metadata

VERSION = '1.4.0'  # this manager
OWNER = 'Hans21223'
# A mod: the DLL whose version is the mod's, its repository, and its release ZIP (the version in the name).
MODS = (('SprocketQoL.dll', 'Sprocket-Quality-of-Life', r'Quality-of-Life-([\d.]+)\.zip'),
        ('SprocketBattles.dll', 'Sprocket-Battle-Editor', r'Sprocket-Battle-Editor-([\d.]+)\.zip'),
        ('SprocketMaps.dll', 'Sprocket-Battle-Editor', r'Sprocket-Map-Framework-([\d.]+)\.zip'),
        ('SprocketLanguage.dll', 'Sprocket-Language-Framework', r'Sprocket-Language-Framework-([\d.]+)\.zip'))
MANAGER = ('Sprocket-Mod-Loader', r'Sprocket-Mod-Manager-([\d.]+)\.zip')
# The manager's own files an update replaces. Its Python runtime is in use while it runs, so it stays.
MANAGER_FILES = ('*.py', '*.pyw', '*.md', 'LICENSE')


def version(text):
    parts = [int(p) for p in re.findall(r'\d+', text)][:4]
    return tuple(parts + [0] * (4 - len(parts)))  # 1.8.8 == 1.8.8.0


def compat(body):
    """A release's game versions (the "hamish.sprocket" of its sp-compat line), or None without one."""
    found = re.search(r'<!--\s*sp-compat\s+(\{.*?\})\s*-->', body or '', re.S)
    try:
        return json.loads(found.group(1)).get('hamish.sprocket') if found else None
    except ValueError:
        return None


def fits(spec, game):
    """Whether a game version fits an sp-compat value: "0.2.56" (those parts), ">=0.2.55.5", or a list of them.
    Unstated, or a game version the manager can't read: it fits."""
    if spec is None or game is None:
        return True
    if isinstance(spec, list):
        return any(fits(s, game) for s in spec)
    op, text = re.match(r'\s*(>=|<=|==|>|<)?\s*(.*)', str(spec)).groups()
    want, have = version(text), version(game)
    if op is None:
        stated = len(re.findall(r'\d+', text))
        return have[:stated] == want[:stated]
    return {'>=': have >= want, '<=': have <= want, '==': have == want, '>': have > want, '<': have < want}[op]


def game_version(root):
    """Sprocket's own version, e.g. "0.2.56.2": the length-prefixed bundleVersion string in globalgamemanagers."""
    try:
        data = (Path(root) / 'Sprocket_Data' / 'globalgamemanagers').read_bytes()
    except OSError:
        return None
    for found in re.finditer(rb'([\x05-\x10])\x00\x00\x00(\d+\.\d+\.\d+(?:\.\d+)?)', data):
        if found.group(1)[0] == len(found.group(2)):  # Unity's own version ("6000.3.21f1") doesn't match its length
            return found.group(2).decode()
    return None


def installed(mods_dir, enabled=()):
    """{dll: (mod folder, version)} for this author's mods the manager holds; an enabled copy wins."""
    found = {}
    for dll, _, _ in MODS:
        for path in sorted(Path(mods_dir).glob('*/**/' + dll), key=lambda p: p.relative_to(mods_dir).parts[0] in enabled):
            try:
                row = Metadata.read(path.read_bytes()).table(0x20)[0]
            except (ValueError, IndexError, KeyError, OSError):
                continue
            found[dll] = (path.relative_to(mods_dir).parts[0], '.'.join(map(str, row[1:5])))
    return found


def newest(releases, pattern, game):
    """(version, ZIP name, its URL, its .sha256 URL) of the newest release ZIP matching `pattern` that fits the game."""
    best = None
    for release in releases:
        if release.get('draft') or not fits(compat(release.get('body')), game):
            continue
        assets = {a['name']: a['browser_download_url'] for a in release.get('assets', [])}
        for name, url in assets.items():
            found = re.fullmatch(pattern, name)
            if found and name + '.sha256' in assets and (best is None or version(found.group(1)) > version(best[0])):
                best = (found.group(1), name, url, assets[name + '.sha256'])
    return best


def fetch(url, timeout=20):
    request = urllib.request.Request(url, headers={'User-Agent': 'Sprocket-Mod-Manager/' + VERSION})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check(root, mods_dir, enabled=()):
    """Updates to offer: (what, installed version, new version, ZIP name, URL, .sha256 URL, mod folder or None for
    this manager). Pre-releases count: Battle Editor and Map Framework only come as those."""
    game, have, releases, found = game_version(root), installed(mods_dir, enabled), {}, []

    def latest(repo, pattern):
        if repo not in releases:
            releases[repo] = json.loads(fetch(f'https://api.github.com/repos/{OWNER}/{repo}/releases?per_page=20'))
        return newest(releases[repo], pattern, game)

    for dll, repo, pattern in MODS:
        if dll in have and (best := latest(repo, pattern)) and version(best[0]) > version(have[dll][1]):
            found.append((have[dll][0], have[dll][1], *best, have[dll][0]))
    if (best := latest(*MANAGER)) and version(best[0]) > version(VERSION):
        found.append(('Mod Manager', VERSION, *best, None))
    return found


def install(game, folder, archive):
    """A mod's new release laid over its folder: what the user added there (Map Framework's CustomMaps) stays.
    shortcut: a file a new release dropped stays too; remove the mod and add it again if one ever matters."""
    on = folder in game.enabled
    if on:
        game.disable(folder)
        if folder in game.enabled:
            raise RuntimeError(f"{folder} couldn't be fully disabled, so it wasn't updated")
    loader_setup.extract(archive, game.mods_dir / folder)
    if on:
        game.enable(folder)


def apply(game, home, update, report):
    """Downloads and installs one update; True when it was this manager (it then needs a restart)."""
    what, _, new, name, url, sha_url, folder = update
    report(f'Updating {what} to {new}...')
    expected = fetch(sha_url).decode('utf-8', 'replace').split()[0].lower()
    cache = Path(home) / 'loader-cache'
    cache.mkdir(exist_ok=True)
    archive = loader_setup.download(cache, name, url, expected, report)
    if folder is not None:
        install(game, folder, archive)
    else:
        with tempfile.TemporaryDirectory(dir=home) as staging:
            loader_setup.extract(archive, Path(staging), 'ModManager/')
            for pattern in MANAGER_FILES:
                for path in Path(staging).glob(pattern):
                    shutil.copy2(path, Path(home) / path.name)
    archive.unlink(missing_ok=True)  # installed: a copy per release would only pile up
    return folder is None
