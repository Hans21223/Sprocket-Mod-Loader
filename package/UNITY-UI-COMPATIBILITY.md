# F1 and keybinding menus: fixed in loader 1.2.1

SprocketModAPI 0.3.0 calls `UnityEngine.RectOffset(left, right, top, bottom)` while building its menus. The generated Unity 6 wrapper omitted this managed convenience constructor. Its `MissingMethodException` disabled the menu controllers for that session while ordinary hotkeys continued to work.

The patched generator restores the overload by calling the existing native-backed empty constructor once, followed by the four padding setters. The original SprocketModAPI DLL is unchanged. New wrappers and their native method maps are written together. Builds and 200 focused checks passed; opening the menus in a new native game session remains to be tested.

## Upgrading an existing installation

1. Save your work and close Sprocket. Install loader 1.2.1 using Mod Manager or the manual instructions, replacing all five patch DLLs.
2. In the game folder, rename `BepInEx/interop` to an unused backup name, such as `interop.before-1.2.1`. If present, also rename `MLLoader/MelonLoader/Il2CppAssemblies` to an unused backup name, such as `Il2CppAssemblies.before-1.2.1`. Keep both backups until the menus work. These folders contain generated wrappers, not tank saves. Preserve `plugins`, `Mods`, `config`, `unity-libs` and the other loader files.
3. Launch normally. The loader will regenerate the missing wrapper caches; this start takes longer than usual. Check `BepInEx/LogOutput.log`, then test F1 and the keybinding menu. Restarting is required because the old failed menu controller cannot recover within the same session.

The official be.788 cache check uses the generator's assembly version rather than its file hash. The patch retains the compatible assembly version, so merely replacing the generator does not reliably invalidate an existing cache.

For advanced users who want to preserve existing generated caches, the repository includes an [optional .NET 8 repair tool](https://github.com/Hans21223/Sprocket-Mod-Loader/tree/main/tools/UnityUiCompatibility). It stages backups, verifies existing methods and remaps native method-token records before installing. It is source-only and is not needed for a fresh installation.

## Separate turret-spawn report

A report of failing to spawn after adding a turret was supplied alongside the menu error. The screenshot contains no first exception for that failed spawn, so this release does not claim to fix it. A full `BepInEx/LogOutput.log` from immediately after that failure is needed to identify the cause.
