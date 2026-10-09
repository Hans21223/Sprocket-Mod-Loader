# Sprocket Mod Loader compatibility pack 1.2.3

An **unofficial Sprocket-specific patch for BepInEx 6 be.788**, version 1.2.3. This is the loader compatibility package.

## New in 1.2.3

Game updates no longer need a new loader when they keep Unity's IL2CPP runtime unchanged, which is the usual case for Sprocket's patches and experimental builds. At every start the bridge finds its three native hook targets itself. It follows the exported call paths used to trace 0.2.55.5 and 0.2.56.0, and accepts each target only as the single candidate with the verified entry bytes, calling-convention bytes and function length. It no longer pins exact GameAssembly and metadata fingerprints. An update that changes that runtime code is refused, as before, and the game runs without mods until the loader is updated. BepInEx and MLLoader already regenerate their interop assemblies after an update. The Mod Manager's **Install mod loader** check uses the same trace.

Tested on Sprocket **0.2.56.1** (experimental): the runtime trace, BepInEx, MLLoader and four BepInEx plugins started, and the game reached the main menu. The trace finds the previously verified targets in 0.2.55.5 and 0.2.56.0.

## New in 1.2.2

Adds a separately traced native profile for Sprocket **0.2.56.0** while retaining **0.2.55.5** support. Both the runtime and installer require a matching native DLL and metadata pair. The three hook functions and four caller/helper functions match the previous build after validated relocations. The accompanying manager records Steam build and metadata context so an older native backup cannot replace an updated game DLL. Builds, native profile checks, 111 hook-chain checks and manager fixtures passed. No game session was launched for this update.

## New in 1.2.1

Restores the missing Unity `RectOffset(left, right, top, bottom)` constructor in generated wrappers. This addresses the reported SprocketModAPI F1 menu and keybinding menu failure while preserving the original mod DLL. The patch adds `Il2CppInterop.Generator.dll` to the four existing compatibility libraries. Builds and 200 focused checks passed; opening the actual game menus remains to be tested. See [UNITY-UI-COMPATIBILITY.md](UNITY-UI-COMPATIBILITY.md) for the cause and upgrade instructions.

## Included from 1.2.0

Fixes by-reference IL2CPP struct conversion in the Harmony bridge. This repairs the Sprocket Tweaks crash when entering the editor and building wheels. See MELON-BYREF-CRASH.md. The separate Mod Manager download now offers an Install mod loader button for automatic setup.

## Included from 1.1.0

The loader now shares native hooks between BepInEx wrappers and MLLoader aliases. This fixes the tested cannon-inspector crash with original Hello Melon 1.0.0 and Sprocket QoL 1.3.0. See MELON-HOOK-CRASH.md. Existing 1.0.0 installs need the new `Patch/BepInEx/core/Il2CppInterop.HarmonySupport.dll`; update it with the game closed and through your manager if it owns the loader. No changes to Hello Melon are needed.

## Supported game

- Windows x64, Sprocket with Unity **6000.3.21f1**'s IL2CPP runtime: tested on **0.2.55.5**, **0.2.56.0** and **0.2.56.1**.
- Base loader: **BepInEx Unity.IL2CPP win-x64 6.0.0-be.788+5b766a3**.

A game update can still break compatibility, for example by moving to another Unity version. The bridge then refuses to start mods and says so in `BepInEx/LogOutput.log`; the game itself runs normally. Individual mods can also need updates when the game code they patch changes. If older game code was restored into updated game assets, use Steam's **Verify integrity of game files**.

## Install

**No PowerShell required:** use the separate Mod Manager's **Install mod loader** button, or follow [MANUAL-INSTALL.md](MANUAL-INSTALL.md) to install with File Explorer only. The PowerShell preparation helper below is optional.

1. Close Sprocket. If a mod manager installed your current loader, disable that loader in the manager first. Do not mix manager-installed and manually installed copies.
2. Extract this ZIP into a normal writable folder, such as Downloads. Double-click **Prepare Loader.cmd**. It downloads the exact official BepInEx build, checks its checksum, and creates **Ready-to-copy** with the patch already applied. It does not change or launch the game. Windows PowerShell is included in Windows; Python and a .NET SDK are not needed.
3. Open Steam > Sprocket > Properties > Installed Files > Browse. Before copying anything, back up any existing `BepInEx`, `dotnet`, `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version` and `changelog.txt` to a separate folder. If another loader owns `winhttp.dll`, uninstall that loader using its own instructions first.
4. Copy the **contents** of Ready-to-copy into the folder containing **Sprocket.exe**. Merge folders and replace the loader files when prompted. Do not copy the outer Ready-to-copy folder itself. Start with third-party plugins removed to a temporary folder.
5. Start the game normally through Steam. The first launch generates interoperability files and may need internet access for BepInEx dependencies. Check `BepInEx/LogOutput.log` for **Sprocket / Unity 6000.3.21f1 runtime traced**, then confirm that the main menu works.
6. Close the game, put a compatible **BepInEx IL2CPP** mod in `BepInEx/plugins` according to that mod's instructions, and relaunch. Add mods one at a time. No gameplay mod is included here.

Never launch with the unpatched official build between steps: Prepare Loader applies the compatibility files before you install anything.

### Upgrading an existing installation

Install the five patch libraries, then follow [the cache upgrade instructions](UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation) before launching. An old generated cache can retain the missing constructor even after the generator is replaced. Back up and rename only the generated cache folders; preserve plugins, settings and Unity base libraries.

### Mod Manager installation

If using the accompanying user's ModManager, import the prepared **Ready-to-copy folder** as one new mod named `BepInEx be.788 - Sprocket 6000.3.21 Patch`. Keep the original BepInEx and other loader entries disabled, then enable the new entry. **Do not import this outer sharing ZIP:** its patch and source folders are not an installable game layout. An existing entry with that name may already contain this patch; a duplicate is unnecessary.

### If the download is unavailable

Get `BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788+5b766a3.zip` from [official BepInEx build 788](https://builds.bepinex.dev/projects/bepinex_be). Put it beside Prepare Loader.cmd and run preparation again. The script checks it before use. Other builds are rejected. If a failed download left a ZIP there, replace it with the correct download. If Ready-to-copy already exists, use a fresh extraction of this pack.

Official base ZIP SHA-256: `F4CC496BD098A0DF4164B81E3737297707F13A47C2478DBA2F60EEFAB784817A`.

## Disable or remove

- Manager install: close the game and disable this loader entry through the same manager.
- Manual install: close the game and rename this pack's `winhttp.dll` to `winhttp.dll.disabled` to stop its startup loader. This does not erase plugins or settings. For a full rollback, restore the loader files/folders from your pre-install backup; preserve any plugins or settings you want first. For a fresh install with no prior loader, the top-level items listed in step 3 came from the prepared package. Do not remove game files such as GameAssembly.dll or Sprocket_Data.
- Returning to the original unpatched BepInEx on this game version can reproduce the original failure. Keep its startup DLL disabled for vanilla play.

## How it works

Sprocket compiles its Unity game code into native code with IL2CPP. BepInEx uses Doorstop (`winhttp.dll`) to start its .NET loader inside the game. Il2CppInterop supplies the bridge that lets managed mods call the game's native objects and register managed components. The patch repairs three bridge targets for this exact game binary; it does not edit Sprocket.exe or GameAssembly.dll on disk.

See **WHY-THE-OLD-LOADER-FAILED.md** for the black-screen/crash explanation and **VALIDATION.md** for the evidence and limits.

## Share and source

The release archive is **Sprocket-Mod-Loader-1.2.2.zip**. Recipients prepare their own official base download. No personal saves, blueprints, game binaries, generated game assemblies, or gameplay plugins are included. Do not distribute your installed game folder or a populated BepInEx folder.

`Source/Il2CppInterop-patched-source.zip` contains the corresponding bridge source, build instructions and modification notices. The patched bridge is LGPL-3.0-only; TerraFX remains MIT. License texts and attribution are in Licenses and THIRD-PARTY-NOTICES.md. The preparation scripts use LGPL-3.0-only. BepInEx and its bundled dependencies are downloaded unchanged from the upstream host before the bridge overlay is applied locally; they retain their upstream licenses. This is an unofficial compatibility package with no upstream endorsement.
