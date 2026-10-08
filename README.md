# Sprocket Mod Loader

Lets you use **BepInEx** and **MelonLoader** (through MLLoader) mods in **Sprocket** on Windows.

The official BepInEx crashes or hangs on a black screen with this Sprocket version. This is a patched version that works with it. It is only the loader: gameplay mods are downloaded separately.

> [!IMPORTANT]
> **Loader 1.2.2 supports exact Sprocket 0.2.55.5 and 0.2.56.0 native/metadata pairs (Unity 6000.3.21f1) on 64-bit Windows.** Its 0.2.56.0 profile was validated offline; gameplay testing remains pending. Use the accompanying Mod Manager 1.3.5, which verifies both game files and preserves backups across Steam updates.

**Contents:** [Pick an install method](#pick-an-install-method) · [Easy install](#easy-install-mod-manager) · [Manual install](#manual-install-no-python) · [Check that it worked](#check-that-it-worked) · [Troubleshooting](#troubleshooting) · [What's new](#whats-new) · [Technical details](#technical-details)

## Pick an install method

| | **Easy: Mod Manager** (recommended) | **Manual: copy the files yourself** |
| --- | --- | --- |
| You need | Python 3.9 or newer | Nothing extra |
| What you do | Click **Install mod loader** | Download and copy three things |
| Backups and undo | Automatic; one click to turn it off | You make and restore backups yourself |
| Adding mods | Click **Add mod**, then switch it on | Copy each mod into the right folder |

Both methods install the same loader. Use only one of them, and don't mix a manager install with manually copied files.

**On Linux or Steam Deck?** Mod Manager is Windows-only. Follow the [Linux and Steam Deck guide](docs/LINUX.md) instead: a few terminal commands and one Steam launch option.

## Easy install: Mod Manager

### What you need

1. **Python 3.9 or newer.** New to Python, or not sure you have it? Follow [Install Python](#install-python) below. It takes about five minutes.
2. **The Mod Manager:** [download Sprocket-Mod-Manager-1.3.5.zip with the loader 1.2.2 installer](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/download/v1.2.2/Sprocket-Mod-Manager-1.3.5.zip).
3. **Only for MelonLoader mods, the MLLoader ZIP.** Download **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9** from [Tong317's MLLoader page on Nexus Mods](https://www.nexusmods.com/ironnest/mods/26) and leave it in your Downloads folder as a ZIP. The manager finds it there. It can't download MLLoader for you, because Nexus Mods needs you to log in. Only need BepInEx mods? Skip this.

Don't use GitHub's green **Code → Download ZIP** button or the "Source code" downloads. Those are for developers and can't be installed.

### Install Python

The Mod Manager is a Python program, so Windows needs Python to open it. To type a command below, open **Command Prompt**: press the Windows key, type `cmd`, press Enter.

**1. Check whether you already have it.** In Command Prompt, type `py --version` and press Enter. If it says **Python 3.9** or newer (for example `Python 3.14.0`), you're done: go to [Install the loader](#install-the-loader). If it says something else, carry on.

**2. Install the Python Install Manager.** On [python.org/downloads](https://www.python.org/downloads/), click **Download Python install manager**, open the downloaded file and click **Install**. (It's the same as **Python Install Manager** in the Microsoft Store.) This installs the tool that installs Python, not Python itself yet.

**3. Let it set itself up.** In Command Prompt, type `py` and press Enter. The first time, a setup helper asks a few questions. Type **y** and press Enter for each one.

If it says *"Your app execution alias settings are configured to launch other commands"*, type **y** and Windows Settings opens on **App execution aliases**. There:
- Turn **on** everything named **Python (default)**, **Python (default windowed)** and **Python install manager**. If they're already on, turn them off and on again.
- Turn **off** the **App Installer** entries for `python.exe` and `python3.exe`. Those open the Microsoft Store instead of Python.

Then go back to Command Prompt and answer the rest with **y**, including installing the latest Python.

**4. Check it worked.** Close Command Prompt, open a new one, and type `py --version`. It should now say `Python 3.something`. If it says no Python is installed, type `py install default`, wait for it to finish, and check again.

**Prefer the classic installer?** On [python.org/downloads/windows](https://www.python.org/downloads/windows/), under the newest **Python 3** release, click **Download Windows installer (64-bit)**. Run it and click **Install Now**. Its default options include everything the Mod Manager needs, and `.pyw` files open with a double-click right away. Don't install both the classic installer's **Python launcher** and the Install Manager: they fight over the `py` command.

### Install the loader

1. **Put the `ModManager` folder somewhere it can stay.** Double-click `Sprocket-Mod-Manager-1.3.5.zip` to open it, then drag the `ModManager` folder out. The Sprocket game folder is a good place (in Steam, right-click **Sprocket** → **Manage** → **Browse local files**). Don't delete this folder later: it keeps the backups used to undo changes.
2. **Close Sprocket** if it's running, then **double-click `modman.pyw`** in the `ModManager` folder. The manager finds Sprocket in your Steam library by itself and selects it in the box at the top.
3. **Click Install mod loader.** That's the only click it needs. The manager downloads the official BepInEx and this patch, checks that they're the exact expected files, backs up anything it replaces, and installs. MLLoader is included if its ZIP is in your Downloads folder or on your Desktop.

   If it can't find MLLoader, it asks first. Choose **Yes** to pick the ZIP yourself, or **No** to install without it for now. BepInEx mods work without it. To add MLLoader later, click **Install mod loader** again.
4. **Wait until it finishes.** The bottom line reads **Installed and verified … loader files**, and the list shows `[x] Sprocket mod loader - BepInEx + MLLoader`.
5. **Click Launch.** The first start after installing takes longer than usual while BepInEx sets itself up. When the main menu appears, the loader is working.

**Upgrading an existing loader?** After installation, close the game and [back up and rename its generated cache folders](docs/UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation). Old caches can retain the missing F1 menu constructor until regenerated.

### Add a mod

1. Download the mod. It can be a ZIP, a folder or a single `.dll` file.
2. Click **Add mod** and choose it. To add a folder, click **Cancel** in the file window and a folder window opens.
3. Double-click the mod in the list, or select it and click **Enable / Disable**. `[x]` means it's on.
4. Click **Launch**.

The manager puts each mod in the folder its loader reads, so you don't need to know where it goes. If it warns that a mod won't fully work, click **Mod report** to see why. Usually the mod was made for a different Sprocket version and needs an update from its author.

Add mods one at a time. If the game breaks, you'll know which mod caused it.

**A mod to start with: [Sprocket Quality of Life](https://github.com/Hans21223/Sprocket-Quality-of-Life/releases).** It adds tools to the vehicle editor's panels: turret to add-on, merging add-ons, Boolean cuts, gun length in calibers, speed and acceleration per gear, and more. Download the ZIP from its Releases page, then **Add mod** and enable it. It's a BepInEx mod, so it doesn't need MLLoader. If you have the older `Sprocket.TurretAddon.dll`, remove it: Quality of Life includes it.

### Turn mods or the loader off

- **One mod:** select it and click **Enable / Disable**.
- **Delete a mod for good:** select it and click **Remove mod**. It's turned off first, so your original files come back, then the Mod Manager's copy is deleted.
- **Back to the unmodded game, keeping your mods:** disable `Sprocket mod loader - BepInEx + MLLoader`. Your original files are put back.
- **Remove everything:** click **Remove all mods**. It removes every mod and the mod loader, deletes what the loader left in the game folder (`BepInEx`, `MLLoader`, `dotnet`, `winhttp.dll` and so on, with mod settings and logs), and puts your original files back. Saves and tanks aren't touched. It lists what it will delete and asks first.
- Don't delete the `backup` or `state` folders inside `ModManager`. The manager needs them to put your original files back.

More on the manager, including upgrading from an older version: [manager/README.md](manager/README.md).

## Manual install (no Python)

This uses File Explorer only.

1. **Close Sprocket and open your game folder.** In Steam, right-click **Sprocket** → **Manage** → **Browse local files**.
2. **Back up any loader you already have.** If the game folder has any of `BepInEx`, `dotnet`, `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version` or `changelog.txt`, copy them to a folder somewhere else first. If they came from a different loader, uninstall it using its own instructions.
3. **Install the official BepInEx.** Download [BepInEx be.788 for Windows x64 IL2CPP](https://builds.bepinex.dev/projects/bepinex_be/788/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788%2B5b766a3.zip). Extract everything inside it into the game folder, so that `winhttp.dll` and the `BepInEx` folder sit next to `Sprocket.exe`.
4. **Optional, for MelonLoader mods:** download **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9** from [Nexus Mods](https://www.nexusmods.com/ironnest/mods/26) and extract its `BepInEx` and `MLLoader` folders into the game folder.
5. **Add the patch last. Don't start the game before this step:** unpatched BepInEx fails on this Sprocket version. Download [Sprocket-Mod-Loader-1.2.2.zip](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/download/v1.2.2/Sprocket-Mod-Loader-1.2.2.zip) and open it. Go into `Sprocket-Mod-Loader-1.2.2\Patch` and drag the `BepInEx` folder into the game folder. When Windows asks, choose **Replace the files in the destination** (5 files).

   If a loader was installed before, [back up and rename the generated cache folders](docs/UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation) before relaunching.
6. **Start Sprocket through Steam** as usual. The first start takes longer than usual.

Your game folder should now look like this:

```text
Sprocket\
├── BepInEx\
│   ├── core\         <- the patch replaced 5 files here
│   └── plugins\      <- BepInEx mods go here (create it if it isn't there)
├── dotnet\
├── MLLoader\         <- only if you did step 4
│   └── Mods\         <- MelonLoader mods go here
├── doorstop_config.ini
├── winhttp.dll
├── GameAssembly.dll
└── Sprocket.exe
```

**To add a mod**, close the game, put the mod in the folder shown above (or wherever its own instructions say) and start the game again.

**To turn the loader off**, rename `winhttp.dll` to `winhttp.dll.disabled`. Your mods and settings stay where they are; rename the file back to turn the loader on again. To remove the loader completely, delete the loader files listed in step 2 and restore your backup if you made one. Never delete game files such as `GameAssembly.dll` or `Sprocket_Data`.

The loader ZIP also contains **Prepare Loader.cmd**, an optional helper that downloads and checks BepInEx for you and builds a ready-to-copy folder. See its [instructions](package/README.md). More detail on manual installation: [package/MANUAL-INSTALL.md](package/MANUAL-INSTALL.md).

## Check that it worked

- The game reaches the main menu.
- In the game folder, open `BepInEx\LogOutput.log` in Notepad. It contains this line:

  ```text
  Sprocket 0.2.56.0 / Unity 6000.3.21f1 compatibility profile: native and metadata SHA-256 verified
  ```

## Troubleshooting

| What you see | What to do |
| --- | --- |
| *This Sprocket build is not supported by the patch. No files were installed.* | Nothing was changed. Loader 1.2.2 requires the exact files from Sprocket **0.2.55.5** or **0.2.56.0**. In Steam, right-click **Sprocket** → **Properties**: under **Installed Files** click **Verify integrity of game files**. If you are using a newer game build, wait for an updated patch and keep the loader disabled. |
| *The game contains files from different builds*, or an older backup cannot be restored | Close Sprocket and use Steam's **Verify integrity of game files**. The manager preserves the old backup and refuses to mix it with updated game files. After verification, **Check game files** can record the matching update as the new original. |
| Sprocket doesn't start at all, or hangs on a black screen, even before installing anything | Leftovers from an earlier mod install, often the official BepInEx, which hangs on this Sprocket version. Verifying the game files in Steam doesn't remove them. In Steam, right-click **Sprocket** → **Manage** → **Browse local files**, and move these to your Desktop if they're there: `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version`, `version.dll`, and the folders `BepInEx`, `MLLoader`, `MelonLoader`, `dotnet`. Then start Sprocket again. |
| *Add a game first*, or *Select the Sprocket game folder containing Sprocket.exe.* | The manager couldn't find Sprocket by itself, for example because it isn't in a Steam library. Click **Add game**, choose the game folder, then choose `Sprocket.exe`. |
| *Close Sprocket before installing the loader.* | Quit the game, then try again. Manager 1.3.5 ignores confirmed exited crash processes; a live process or one whose state cannot be confirmed still blocks installation. |
| *Checksum failed: …* | The file isn't the exact version needed. For MLLoader, download **V0.7.3 / 2.3.9** again from Nexus. |
| *… need MLLoader …* | You have MelonLoader mods, so the manager won't install without MLLoader. Put the MLLoader ZIP in your Downloads folder and click **Install mod loader** again. |
| *module 'hashlib' has no attribute 'file_digest'* | You have Mod Manager 1.3.0. [Download 1.3.5](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/download/v1.2.2/Sprocket-Mod-Manager-1.3.5.zip). |
| Double-clicking `modman.pyw` does nothing, or opens it as text | Python isn't installed, or Windows doesn't know to open `.pyw` files with it. Follow [Install Python](#install-python), then right-click `modman.pyw` → **Open with** → **Choose another app** → **Python**, tick **Always**. From 1.3.3, anything else that stops the manager opening shows a message saying what to do. |
| Double-clicking `modman.pyw`, or typing `python`, opens the Microsoft Store | Windows' **App Installer** shortcut is in the way. Press the Windows key, type **manage app execution aliases**, press Enter. Turn **off** **App Installer** `python.exe` and `python3.exe`, turn **on** **Python (default)** and **Python (default windowed)**. See [Install Python](#install-python) step 3. |
| A black window says *"Your app execution alias settings are configured to launch other commands besides 'py' and 'python'"* | That's the Python Install Manager's setup helper. Type **y**, press Enter, and follow [Install Python](#install-python) step 3. |
| `py` or `python` says *not recognized* / *command not found* | Did the Python Install Manager install? Then press the Windows key, type **manage app execution aliases**, press Enter, and turn **Python (default)** and **Python install manager** off and on again. Open a new Command Prompt and try again. |
| `py --version` says no Python is installed | The Install Manager is there, but not Python itself yet. Type `py install default` and wait. |
| `py` says *can't open file* | An old **Python launcher** from the classic installer takes priority over the Install Manager. Press the Windows key, type **installed apps**, press Enter (on Windows 10: **Apps & features**). In the page's search box type **python launcher**; if it's there, click **…** next to it → **Uninstall**. Then open a new Command Prompt. |
| *The Mod Manager's other files aren't next to it* | You opened `modman` inside the ZIP. Drag the `ModManager` folder out of the ZIP first, then open `modman` from that folder. |
| *Python is installed without Tkinter* | Run the Python installer again, choose **Modify**, tick **tcl/tk and IDLE**, finish, then open the Mod Manager again. |
| *The Mod Manager hit an error* | The full error is saved in `modman-error.log` in the `ModManager` folder. Send that file when you ask for help. |
| Black screen or crash at startup after a manual install | The patch probably isn't in place. Repeat [manual step 5](#manual-install-no-python). |
| **Mod report** says a mod *needs BepInEx.Core, BepInEx.Unity.IL2CPP, which isn't installed*, or says the mod loader isn't installed | The loader isn't installed in this game folder, or it's disabled. Close the game, click **Install mod loader**, start the game once, then click **Mod report** again. |
| There's a `MelonLoader` folder in the game folder, or **Mod report** reads its log from `MelonLoader\Latest.log` | That's a separate MelonLoader. This setup doesn't use it and hasn't been tested with it. Uninstall it with the MelonLoader installer, install this loader, then add your MelonLoader mods again with **Add mod**. |
| A mod is on but doesn't do anything, or shows errors | In the Mod Manager, click **Mod report**. It lists what the mod needs that this Sprocket version doesn't have, and which mod each error in the last game session came from. Only the mod's author can fix these. |
| F1 or the keybinding menu fails with a missing `RectOffset` constructor | Install loader 1.2.2 and [regenerate the old wrapper caches](docs/UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation). Keep the original SprocketModAPI DLL. |
| The game crashes when you quit | A previously documented shutdown problem that hasn't been fixed yet. |

## What's new

- **1.2.2 (loader, current) and 1.3.5 (Mod Manager):** adds separately validated Sprocket 0.2.56.0 native/metadata support while retaining 0.2.55.5. Prevents old game-code backups from being restored across Steam updates, fixes duplicate mod DLL restoration when disabling, and ignores confirmed exited crash processes. Native checks, 111 shared-hook checks and 66 manager tests passed; new-game gameplay testing remains pending.
- **1.2.1 (loader):** restores the missing Unity constructor used by SprocketModAPI's F1 and keybinding menus. Original mod DLLs are unchanged. Builds and 200 focused checks passed; native menu testing remains pending. [Cause and upgrade instructions](docs/UNITY-UI-COMPATIBILITY.md).
- **1.3.4 (Mod Manager):** download recovery and clean unmodding. If an official download is cut off or blocked by a filter, setup retries and explains what happened, or automatically uses a browser download from your Downloads folder. Adds **Remove all mods** to cleanly remove all mods and loader files, restoring original game files.
- **1.3.3 (Mod Manager):** never closes without a word. Opened inside the ZIP, or on a Python without Tkinter, it says so and what to do; any other error is shown and saved in `modman-error.log`.
- **1.3.2 (Mod Manager):** one click installs everything. The manager finds Sprocket in any Steam library and the MLLoader ZIP in Downloads, so it no longer has to sit in the game folder or ask for files. MLLoader is optional: without it, BepInEx mods still work. **Mod report** says plainly when the loader is missing.
- **1.3.1 (Mod Manager):** runs on Python 3.9 and newer. 1.3.0 stopped at startup on Python 3.10 and older.
- **1.3.0 (Mod Manager):** puts each mod in the folder its loader reads, works across drives, and explains why a mod can't work in **Mod report**. [Details](manager/README.md#where-mods-go-and-why-a-mod-doesnt-work).
- **1.2.0 (loader):** fixes the crash when entering the editor with Sprocket Tweaks. Adds one-click setup to the Mod Manager. [Cause and validation](docs/MELON-BYREF-CRASH.md).
- **1.1.0 (loader):** MelonLoader (MLLoader) mods and BepInEx mods can patch the same game code without crashing, for example Hello Melon with Sprocket QoL. [Cause, fix and validation](docs/MELON-HOOK-CRASH.md).

**Known issue:** a separate crash can happen when the game shuts down. The earlier editor fix was tested, but crash-free gameplay and shutdown are not guaranteed.

All releases: [GitHub Releases](https://github.com/Hans21223/Sprocket-Mod-Loader/releases).

## Technical details

### Why the original loader failed

The original Il2CppInterop bridge selected the wrong internal function for its field-default-value hook. The baseline crashed inside that hook. The patch also corrects a generic-method calling convention and supplies a verified class-initialization target.

Earlier tests hung on a black screen during menu loading, including with BepInEx alone. The exact cause of that silent hang was not isolated; the Class::Init warning alone does not prove the fallback caused it. See the [full failure explanation](package/WHY-THE-OLD-LOADER-FAILED.md).

### How the patch works

BepInEx starts its .NET loader through Doorstop. Il2CppInterop connects managed mods to Sprocket's native IL2CPP game code. This package includes the runtime with three verified native targets, its matching Common library and TerraFX dependency, the shared Harmony bridge, and the generator's Unity UI constructor repair. It does not patch Sprocket.exe, GameAssembly.dll or third-party mod DLLs on disk.

The bridge checks the matching GameAssembly.dll and metadata SHA-256 values and function starting bytes before using the game-specific targets:

```text
18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56
ADB36B5F04662BE0D40C6E548C797394659A9C0D4B009E3C0E718833ABF90B3A
```

These are the native fingerprints for 0.2.55.5 and 0.2.56.0 respectively; the required metadata fingerprints are in [the package README](package/README.md). The new native functions were traced through their exported callers and compared with the previous function bodies. **Other game builds are unsupported.** Future updates require revalidation. The recorded gameplay evidence covers the earlier build; 0.2.56.0 gameplay remains pending.

### Verification

Recorded tests reached the main menu and Settings, exercised a diagnostic BepInEx plugin, and entered sandbox vehicle simulation. All 229 prepared loader files match the tested loader entry by SHA-256. The included bridge source builds with zero errors; existing/upstream and restore warnings remain. Packaging checks are separate from runtime testing.

See [validation and limitations](package/VALIDATION.md) and [package checks](package/PACKAGE-CHECKS.txt). Full campaigns, long sessions and arbitrary third-party mod combinations have not been verified.

### Source and licenses

- [Browse the modified bridge source](src/Il2CppInterop).
- [Changes and build instructions](src/Il2CppInterop/LOCAL-CHANGES.md).
- [Preparation script](package/Prepare-Loader.ps1).
- [Third-party notices](package/THIRD-PARTY-NOTICES.md).

The patched bridge and preparation scripts are LGPL-3.0-only; TerraFX is MIT. Corresponding bridge source and full license texts are included in the release ZIP. BepInEx and its other components are downloaded from their official distribution during preparation. This project is not an official BepInEx or Sprocket release and implies no upstream endorsement.

No personal saves, blueprints, proprietary Sprocket binaries, generated Sprocket assemblies or gameplay plugins are included.
