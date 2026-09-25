# Mod Manager with one-click loader setup

Windows, Python 3.9 or newer with Tkinter (the [python.org](https://www.python.org/downloads/) installer includes it with the default options). Pillow is optional for image previews.

Before you start, download the **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9 ZIP** from [Tong317's Nexus page](https://www.nexusmods.com/ironnest/mods/26). Keep it as a ZIP. It is not redistributed here.

1. **Put this `ModManager` folder in the Sprocket game folder**, next to `Sprocket.exe`. To find that folder: in Steam, right-click **Sprocket** → **Manage** → **Browse local files**. Open the manager ZIP and drag the `ModManager` folder in. Don't use **Extract All** with its suggested location: the extra folder it adds stops the manager finding the game.

   ```text
   Sprocket\
   ├── ModManager\
   │   └── modman.pyw
   └── Sprocket.exe
   ```

   **Upgrading?** Copy `modman.pyw`, `loader_setup.py` and `mod_compat.py` over the ones in your existing manager folder. Keep your games.json, mods, state and backup folders.
2. **Close Sprocket**, then double-click `modman.pyw`. Sprocket is selected at the top. If it isn't, click **Add game**, choose the game folder, then choose `Sprocket.exe`.
3. **Click Install mod loader.** The first time, choose the MLLoader ZIP you downloaded. The manager keeps a checked copy, so later installs need only the click.
4. **Wait for "Installed and verified … loader files"** at the bottom. Setup downloads official BepInEx be.788 and the Sprocket 1.2.0 patch, checks their exact SHA-256 hashes, backs up the files it replaces, installs everything, and turns on one combined entry: `Sprocket mod loader - BepInEx + MLLoader`.
5. **Click Launch.** The first start is slower than usual while BepInEx sets itself up.
6. **Add gameplay mods:** click **Add mod**, choose the mod's ZIP, folder or DLL, then double-click it in the list to enable it (`[x]`). Add mods one at a time.

This installs Doorstop/BepInEx files on disk for the next game launch. It does not use PowerShell to inject code into a running process. The manager's separate **Inject DLL** feature is not used by this button.

Prefer no installer script at all? Follow the [manual File Explorer instructions](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/package/MANUAL-INSTALL.md). The loader and mods still run code when the game starts; Python is not inherently a safety guarantee. The manager's safeguards are exact download checksums, published source, game-build checks, backups and rollback.

## Where mods go, and why a mod doesn't work

Add a mod as a ZIP, folder or single DLL. The manager reads each DLL's .NET metadata (it never runs it) and puts it
where its loader looks: MelonLoader mods in `MLLoader\Mods`, MelonLoader plugins in `MLLoader\Plugins`, libraries in
`MLLoader\UserLibs`, BepInEx plugins in `BepInEx\plugins`. A full folder layout inside the mod is kept as it is.
A mod whose loader isn't installed yet can't be enabled: click **Install mod loader** first.

A mod can install correctly and still not work, because it was made for another version of the game or of Unity.
When you enable one, the manager warns you if it can tell, and **Mod report** (or `python modman.pyw --report "Sprocket"`)
first says if the mod loader isn't installed, hasn't run yet, or shares the game folder with a separate
MelonLoader. Then it lists for every enabled mod:

- things it needs that the game and its loaders don't have (for example a part of the game this version dropped);
- game or Unity code it calls that this version doesn't have (checked by name and number of arguments), which it will
  throw errors on;
- libraries that do nothing because no installed mod uses them;
- enabled mods whose files were deleted outside the manager;
- which mod each error in the last game session's log came from, and text the game's font can't show.

The manager can't fix these: they need an update from the mod's author. `python -m unittest -v test_mod_compat` checks
the metadata reader.

## Updates and removal

Overlapping loader-only entries are replaced by **Sprocket mod loader - BepInEx + MLLoader**. Unrelated mods remain enabled. An entry containing both loader files and additional content is refused so it can be separated first. Repeat setup verifies an existing installation and repairs changed package files; changed configuration files covered by the package are backed up.

Use the normal **Enable / Disable** button on the combined loader entry to disable it and restore the originals. Runtime-generated files such as caches, configuration and Melon preferences are not removed by disabling. Do not delete `backup` or `state` while using the manager.

Installation failures restore files and manager state. A snapshot of every affected file is retained under `loader-history/before-setup-*` after success. `journal.json` maps original paths to numbered copies under `files`. Do not share that folder: it may contain your local configuration and paths. If an interrupted installation leaves `loader-recovery`, setup refuses to overwrite it; preserve the journal and copies for recovery.

The installer supports only Sprocket 0.2.55.5 / Unity 6000.3.21f1 with the verified GameAssembly hash. It refuses an unsupported or running game. A Steam update needs a newly validated patch.

## What changed

The 1.2.0 bridge includes both the earlier shared-hook repair and the by-reference struct conversion fix for Sprocket Tweaks' editor crash. [Technical explanation](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/docs/MELON-BYREF-CRASH.md).

This is a preview: a separate crash during shutdown remains unresolved. Installation and repeat verification of all 316 package files passed on both the Steam and test copies; nine installer regression tests and the manager self-test passed.

The manager package contains source only, under the repository's LGPL-3.0 license; no game files, user configuration, saves, gameplay mods or cached downloads. Run `python modman.pyw --selftest`, `python -m unittest -v test_loader_setup` and `python -m unittest -v test_mod_compat` from this folder for local checks.
