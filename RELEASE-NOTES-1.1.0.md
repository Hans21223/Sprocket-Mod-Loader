**Loader-level fix for the cannon-inspector crash with MelonLoader and BepInEx mods.**

Hello Melon 1.0.0 and Sprocket QoL 1.3.0 patched different managed wrappers of the same native function. The previous backend installed a second detour into the first hook's callback. Version 1.1.0 shares one physical detour and chains the wrappers, preserving both mods' patches.

**Hello Melon remains unchanged.** The original 1.0.0 DLL was used for the final in-game check: its cannon hook ran and QoL's Gun length panel rendered together, with the game still running. 111 relay regression checks passed; HarmonySupport builds with zero errors.

Download **Sprocket-Mod-Loader-1.1.0.zip**, extract it, and follow README.md. For an existing 1.0.0 installation, the new loader file is `Patch/BepInEx/core/Il2CppInterop.HarmonySupport.dll`. Close the game and back up the old file before replacing it; use the mod manager's disable/update/enable flow for a managed install.

The original game fingerprint guard and startup repairs remain in place. Supported: **Sprocket 0.2.55.5 / Unity 6000.3.21f1, Windows x64**. The MLLoader test used version 2.3.9. This is not a universal compatibility claim for all MelonLoader mods, and standalone MelonLoader is not covered.

The ZIP includes source, licenses, checksums, installation/removal instructions, and the failure analysis. MLLoader, Hello Melon, QoL and game files are not bundled. Download the named release asset rather than GitHub's automatically generated Source code ZIP.
