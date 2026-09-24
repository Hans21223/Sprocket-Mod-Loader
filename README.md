# Sprocket Mod Loader

An unofficial **BepInEx be.788 compatibility patch** for **Sprocket 0.2.55.5 / Unity 6000.3.21f1 on Windows x64**. It repairs the IL2CPP bridge so compatible BepInEx mods can run on the tested game build.

**[Download Mod Manager 1.3.0](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/tag/v1.3.0)** · **[Download loader 1.2.0](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/tag/v1.2.0)**

For one-click setup, download **Sprocket-Mod-Manager-1.3.0.zip**, extract it beside Sprocket.exe as ModManager, open `modman.pyw`, and click **Install mod loader**. First use asks for your MLLoader 2.3.9 ZIP from Nexus. Requires Python 3.11+ on Windows. [Manager instructions](manager/README.md).

For manual setup, download **Sprocket-Mod-Loader-1.2.0.zip** from the 1.2.0 release (the loader is unchanged in 1.3.0). Extract it and double-click **Prepare Loader.cmd** to create a **Ready-to-copy** folder. Follow the [installation and removal instructions](package/README.md).

**Prefer no PowerShell?** The manager button uses Python, and [manual File Explorer installation](package/MANUAL-INSTALL.md) requires no installer script. The preparation helper is optional.

**New in 1.3.0 (Mod Manager):** mods added as loose DLLs install where their loader looks, found by reading each DLL (never running it). Disabling a mod works across drives. Enabling a mod warns if it can't fully work in this game, and **Mod report** explains every enabled mod: things it needs that the game doesn't have, game or Unity code it calls that this build lacks, unused libraries, and which mod each error in the last game session came from. [Details](manager/README.md#where-mods-go-and-why-a-mod-doesnt-work).

**New in 1.2.0:** fixes the editor-entry crash with Sprocket Tweaks caused by incorrectly converting by-reference wheel structs. The editor, air-tyre adjustment and Hello Melon cannon callback passed the recorded test. [Cause and validation](docs/MELON-BYREF-CRASH.md).

**Preview:** a separate crash during shutdown remains unresolved. The tested editor fix does not establish crash-free gameplay or shutdown.

**New in 1.1.0:** fixes the native-hook collision between MLLoader mods and BepInEx mods. Original Hello Melon 1.0.0 and Sprocket QoL now run their cannon-inspector patches together in the tested setup. [Cause, fix and validation](docs/MELON-HOOK-CRASH.md).

This is a loader package; gameplay mods are installed separately. The repository's GitHub-generated source ZIP is intended for developers, not the player download.

## Why the original loader failed

The original Il2CppInterop bridge selected the wrong internal function for its field-default-value hook. The baseline crashed inside that hook. The patch also corrects a generic-method calling convention and supplies a verified class-initialization target.

Earlier tests hung on a black screen during menu loading, including with BepInEx alone. The exact cause of that silent hang was not isolated; the Class::Init warning alone does not prove the fallback caused it. See the [full failure explanation](package/WHY-THE-OLD-LOADER-FAILED.md).

## How the patch works

BepInEx starts its .NET loader through Doorstop. Il2CppInterop connects managed mods to Sprocket's native IL2CPP game code. This package replaces the bridge runtime with a build using three verified native targets for this exact game binary, plus its matching Common library and TerraFX dependency. It does not patch Sprocket.exe or GameAssembly.dll on disk.

The bridge checks the GameAssembly.dll SHA-256 and function starting bytes before using the game-specific targets:

```text
18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56
```

**Other game builds are unsupported.** A Sprocket update requires revalidation, not just changing this hash. This is not a universal Unity 6 fix, and only the documented MLLoader test combination has been verified. Standalone MelonLoader is not covered.

## Verification

Recorded tests reached the main menu and Settings, exercised a diagnostic BepInEx plugin, and entered sandbox vehicle simulation. All 229 prepared loader files match the tested loader entry by SHA-256. The included bridge source builds with zero errors; existing/upstream and restore warnings remain. Packaging checks are separate from runtime testing.

See [validation and limitations](package/VALIDATION.md) and [package checks](package/PACKAGE-CHECKS.txt). Full campaigns, long sessions and arbitrary third-party mod combinations have not been verified.

## Source and licenses

- [Browse the modified bridge source](src/Il2CppInterop).
- [Changes and build instructions](src/Il2CppInterop/LOCAL-CHANGES.md).
- [Preparation script](package/Prepare-Loader.ps1).
- [Third-party notices](package/THIRD-PARTY-NOTICES.md).

The patched bridge and preparation scripts are LGPL-3.0-only; TerraFX is MIT. Corresponding bridge source and full license texts are included in the release ZIP. BepInEx and its other components are downloaded from their official distribution during preparation. This project is not an official BepInEx or Sprocket release and implies no upstream endorsement.

No personal saves, blueprints, proprietary Sprocket binaries, generated Sprocket assemblies or gameplay plugins are included.
