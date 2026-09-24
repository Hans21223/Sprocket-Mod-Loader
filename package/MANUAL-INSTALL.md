# Install without PowerShell or scripts

This method uses File Explorer only. Close Sprocket first and back up any existing loader files before replacing them. For a loader already managed by Mod Manager, use its Install mod loader button instead so its backups and enabled-mod records stay consistent.

1. Download the official [BepInEx be.788 Windows x64 IL2CPP ZIP](https://builds.bepinex.dev/projects/bepinex_be/788/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788%2B5b766a3.zip).
2. Extract its contents into the game folder containing **Sprocket.exe**. `winhttp.dll`, `doorstop_config.ini`, `BepInEx` and `dotnet` belong beside that executable.
3. Open the **Sprocket-Mod-Loader-1.2.0.zip** compatibility package. Copy the **BepInEx** folder inside **Patch** into the game folder, merging folders and replacing the four bridge DLLs. Do not copy the entire Patch folder itself. Do not launch between steps 2 and 3.
4. If you want Melon mods, download **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9** from [Tong317's Nexus page](https://www.nexusmods.com/ironnest/mods/26). Extract its **BepInEx** and **MLLoader** folders into the same game folder.
5. Put compatible BepInEx plugins in `BepInEx/plugins`, or compatible Melon mods in `MLLoader/Mods`. Launch the game normally.

You do not need to run **Prepare Loader.cmd** or **Prepare-Loader.ps1** with this method. Those optional helpers download and assemble files; they do not inject into a running process.

## Choosing an option

| Method | Requirements | Checks and backups |
| --- | --- | --- |
| Mod Manager: Install mod loader | Python 3.11+ and Tkinter; no PowerShell | Checks exact game and package hashes; automatic file backups and failure rollback |
| Manual File Explorer copy | No installer script or Python | You choose the exact packages and manage backups yourself |
| Optional Prepare Loader helper | PowerShell | Verifies downloads and prepares files; you copy them into the game |

The manager does not ask you to change PowerShell execution policy, disable antivirus, or paste commands into an elevated terminal. Manual copying avoids running an installer script, but the loader and mods still execute code when the game starts. Changing the scripting language does not prove a download is safe. Use the linked upstream downloads, review the published source, and install mods you trust. Checksums detect changed files; they are not a guarantee that code is harmless.

Only the exact Sprocket build described in README.md is supported. Version 1.2.0 is a preview; see MELON-BYREF-CRASH.md for the remaining shutdown issue.
