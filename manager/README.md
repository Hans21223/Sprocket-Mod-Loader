# Mod Manager with one-click loader setup

Windows, Python 3.9 or newer with Tkinter. Pillow is optional for image previews.

**No Python yet?** Install **Python install manager** from [python.org/downloads](https://www.python.org/downloads/), then open Command Prompt, type `py` and answer **y** to each question. If it opens **App execution aliases**, turn on **Python (default)**, **Python (default windowed)** and **Python install manager**, and turn off the **App Installer** `python.exe` / `python3.exe` entries. Check with `py --version`; if no Python is installed yet, run `py install default`. Full steps and fixes: [Install Python](https://github.com/Hans21223/Sprocket-Mod-Loader#install-python).

For MelonLoader mods, also download the **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9 ZIP** from [Tong317's Nexus page](https://www.nexusmods.com/ironnest/mods/26) and leave it in Downloads. The manager finds it there. MLLoader isn't redistributed here, and Nexus Mods needs a login, so the manager can't download it itself. BepInEx mods don't need it.

1. **Put this `ModManager` folder somewhere it can stay.** The Sprocket game folder is a good place (in Steam, right-click **Sprocket** → **Manage** → **Browse local files**). It keeps the backups used to undo changes, so don't delete it later.

   **Upgrading?** Copy `modman.pyw`, `loader_setup.py`, `mod_compat.py` and `game_guard.py` over the ones in your existing manager folder. Keep your games.json, mods, state and backup folders.
2. **Close Sprocket**, then double-click `modman.pyw`. The manager finds Sprocket next to its folder or in any Steam library and selects it at the top. If it doesn't, click **Add game**, choose the game folder, then choose `Sprocket.exe`.
3. **Click Install mod loader.** Setup downloads official BepInEx be.788 and the checksum-verified Sprocket loader 1.2.2 patch, backs up the files it replaces, installs everything, and turns on one combined entry: `Sprocket mod loader - BepInEx + MLLoader`. MLLoader is included when its ZIP is in Downloads, on the Desktop, or in or next to this folder. The manager keeps checked copies for later installs, and can also use matching ZIPs downloaded in your browser.

   Without the ZIP it asks: **Yes** to choose it, **No** to install without MLLoader for now (click **Install mod loader** again later to add it). It won't leave MLLoader out once MelonLoader mods use it.
4. **Wait for "Installed and verified … loader files"** at the bottom.
5. **Click Launch.** The first start is slower than usual while BepInEx sets itself up.
6. **Add gameplay mods:** click **Add mod**, choose the mod's ZIP, folder or DLL, then double-click it in the list to enable it (`[x]`). Add mods one at a time. To get rid of a mod, select it and click **Remove mod**: it's disabled, the game's originals come back, and the manager's copy is deleted. **Remove all mods** does that for every mod, the loader included, then deletes the loader's leftover folders and files (`BepInEx`, `MLLoader`, `dotnet`, `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version`, BepInEx's `changelog.txt`) so Sprocket is back to unmodded. It asks first, and never touches a separate MelonLoader, saves or tanks.

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

The installer accepts the separately traced Sprocket 0.2.55.5 and 0.2.56.0 / Unity 6000.3.21f1 native and metadata pairs. It refuses an unsupported or running game. Future Steam updates need a newly validated patch. The 0.2.56.0 native targets were checked offline; gameplay testing remains pending.

The installer also checks the matching game metadata. An older GameAssembly with updated metadata is a mixed installation and must be repaired with Steam's **Verify integrity of game files**. Game-file backups now record the Steam build and metadata; the manager will not restore an older native DLL after an update. After verifying a fresh update, **Check game files** can record the new original while preserving the previous backup. This does not make a new game build compatible with the loader patch.

## What changed

Loader 1.2.2 and manager 1.3.5 support the separately checked 0.2.56.0 game files, block restoring older native backups after Steam updates, and ignore confirmed exited crash processes when checking whether the game is open. Live and uncertain processes still block installation. All 66 manager tests passed; gameplay testing remains pending.

Disabling a manually preinstalled mod now preserves its duplicate backup outside the game instead of restoring an identical active DLL. If a mod DLL was changed outside the manager, it stays tracked and the manager explains why disabling could not finish. Edited saves and other user data remain preserved.

The 1.2.1 loader includes the earlier shared-hook and by-reference struct fixes plus the missing Unity constructor used by SprocketModAPI's F1 and keybinding menus. If upgrading an existing installation, close the game and [back up and rename the generated cache folders](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/docs/UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation) after installing, then relaunch to regenerate them. Original third-party mod DLLs are unchanged; native menu testing remains pending.

The previously documented crash during shutdown remains unresolved. Installation and repeat verification of all 316 package files passed on both the Steam and test copies; manager fixtures and the self-test passed. These file checks do not establish gameplay compatibility for every mod.

The manager package contains source only, under the repository's LGPL-3.0 license; no game files, user configuration, saves, gameplay mods or cached downloads. Run `python modman.pyw --selftest`, `python -m unittest -v test_loader_setup` and `python -m unittest -v test_mod_compat` from this folder for local checks.
