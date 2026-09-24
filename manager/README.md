# Mod Manager with one-click loader setup

Windows, Python 3.11 or newer with Tkinter. Pillow is optional for image previews.

1. Extract this folder beside `Sprocket.exe` as `ModManager`. Existing users copy `modman.pyw` and `loader_setup.py` into their manager folder; keep their existing games.json, mods, state and backup folders.
2. Double-click `modman.pyw`. A fresh manager next to Sprocket detects its game folder; otherwise use **Add game**.
3. Select the intended game copy, close Sprocket, then click **Install mod loader**.
4. On the first run, choose the **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9 ZIP** downloaded from [Tong317's Nexus page](https://www.nexusmods.com/ironnest/mods/26). The verified ZIP is cached locally; later installations use one click. It is not redistributed here.
5. Setup downloads official BepInEx be.788 and the Sprocket 1.2.0 patch, verifies exact SHA-256 hashes, prepares the files, installs them, and enables one combined loader entry. Click **Launch** afterward. Gameplay mods remain separate.

This installs Doorstop/BepInEx files on disk for the next game launch. It does not use PowerShell to inject code into a running process. The manager's separate **Inject DLL** feature is not used by this button.

Prefer no installer script at all? Follow the [manual File Explorer instructions](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/package/MANUAL-INSTALL.md). The loader and mods still run code when the game starts; Python is not inherently a safety guarantee. The manager's safeguards are exact download checksums, published source, game-build checks, backups and rollback.

## Updates and removal

Overlapping loader-only entries are replaced by **Sprocket mod loader - BepInEx + MLLoader**. Unrelated mods remain enabled. An entry containing both loader files and additional content is refused so it can be separated first. Repeat setup verifies an existing installation and repairs changed package files; changed configuration files covered by the package are backed up.

Use the normal **Enable / Disable** button on the combined loader entry to disable it and restore the originals. Runtime-generated files such as caches, configuration and Melon preferences are not removed by disabling. Do not delete `backup` or `state` while using the manager.

Installation failures restore files and manager state. A snapshot of every affected file is retained under `loader-history/before-setup-*` after success. `journal.json` maps original paths to numbered copies under `files`. Do not share that folder: it may contain your local configuration and paths. If an interrupted installation leaves `loader-recovery`, setup refuses to overwrite it; preserve the journal and copies for recovery.

The installer supports only Sprocket 0.2.55.5 / Unity 6000.3.21f1 with the verified GameAssembly hash. It refuses an unsupported or running game. A Steam update needs a newly validated patch.

## What changed

The 1.2.0 bridge includes both the earlier shared-hook repair and the by-reference struct conversion fix for Sprocket Tweaks' editor crash. [Technical explanation](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/docs/MELON-BYREF-CRASH.md).

This is a preview: a separate crash during shutdown remains unresolved. Installation and repeat verification of all 316 package files passed on both the Steam and test copies; nine installer regression tests and the manager self-test passed.

The manager package contains source only, under the repository's LGPL-3.0 license; no game files, user configuration, saves, gameplay mods or cached downloads. Run `python modman.pyw --selftest` and `python -m unittest -v test_loader_setup` from this folder for local checks.
