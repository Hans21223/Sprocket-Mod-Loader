Adds an **Install mod loader** button to Mod Manager and fixes the second Melon mod crash when entering the vehicle editor with Sprocket Tweaks.

- **Sprocket-Mod-Manager-1.2.0.zip:** extract as ModManager beside Sprocket.exe. Requires Windows and Python 3.11+ with Tkinter. Existing users replace the two Python files and keep their configuration/data. First use asks for the MLLoader 2.3.9 ZIP from Nexus; later installs are one click.
- **Sprocket-Mod-Loader-1.2.0.zip:** standalone patch/preparation package for manual setup, with corresponding bridge source and licenses.
- Setup verifies the game and every downloaded archive, migrates loader-only entries, preserves unrelated mods, and rolls back on failure.
- No PowerShell is needed for the manager button. Manual File Explorer instructions are also included for people who prefer no installer script.
- Fixes conversion of native by-reference structs in the Harmony bridge. The old conversion interpreted wheel blueprint data as an object pointer and crashed while reading MeshGuid.
- Verified editor entry with original Hello Melon 1.0.0, Sprocket Tweaks 1.1.0, MLLoader 2.3.9 and QoL; tyre weight and cannon callbacks ran. Full campaigns and arbitrary mod combinations are not covered.

Only Sprocket 0.2.55.5 / Unity 6000.3.21f1 Windows x64 is supported. This remains a BepInEx-hosted MLLoader bridge, not a standalone MelonLoader release. Close the game before setup.

Preview limitation: a separate UnityPlayer crash was recorded during a later shutdown. The editor-entry fix passed its test; the shutdown failure is not yet resolved. The installer itself passed nine regression tests, the manager self-test, and installation plus repeat verification of 316 files in both the Steam and test copies.
