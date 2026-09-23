# Sprocket Mod Loader

An unofficial **BepInEx be.788 compatibility patch** for **Sprocket 0.2.55.5 / Unity 6000.3.21f1 on Windows x64**. It repairs the IL2CPP bridge so compatible BepInEx mods can run on the tested game build.

**[Download version 1.0.0](https://github.com/Hans21223/Sprocket-Mod-Loader/releases/tag/v1.0.0)**

Download **Sprocket-Mod-Loader-1.0.0.zip** from the release assets. Extract it and double-click **Prepare Loader.cmd**. It downloads the exact official BepInEx build, checks the files, and creates a **Ready-to-copy** folder. It does not automatically change or launch the game. Follow the [installation and removal instructions](package/README.md) before copying its contents beside Sprocket.exe.

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

**Other game builds are unsupported.** A Sprocket update requires revalidation, not just changing this hash. This is not a universal Unity 6 fix, and it does not establish MLLoader or MelonLoader compatibility.

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
