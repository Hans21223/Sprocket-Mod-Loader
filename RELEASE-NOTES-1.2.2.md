Adds a separately traced loader profile for **Sprocket 0.2.56.0 / Unity 6000.3.21f1**, while retaining the exact **0.2.55.5** profile. Runtime and installer verify the matching native DLL and metadata before using game-specific targets. The previous shared-hook, by-reference struct and Unity UI constructor fixes are included.

- **Sprocket-Mod-Loader-1.2.2.zip:** five compatibility libraries, preparation helper, corresponding bridge source and license notices. Download official BepInEx be.788 separately or use the helper.
- **Sprocket-Mod-Manager-1.3.5.zip:** source-only Windows manager and updated installer. Replace its program files while retaining games.json, mods, state and backups.
- Each ZIP has a SHA-256 checksum file.

Manager 1.3.5 records Steam build and metadata context so an old native backup cannot overwrite an updated game. Mixed game builds require Steam verification. Confirmed exited crash processes no longer block installation; live or uncertain processes still do. Disabling a manually preinstalled mod preserves its duplicate backup outside the game, and changed mod DLLs remain tracked when disabling cannot finish.

**Existing installations:** close Sprocket and install through the manager that owns the loader. If game files were mixed across versions, first use Steam's **Verify integrity of game files**. After installing the patch, back up and rename generated `BepInEx/interop` and, when present, `MLLoader/MelonLoader/Il2CppAssemblies` caches so the next launch regenerates them. Preserve plugins, settings and Unity base libraries. See the [cache upgrade instructions](https://github.com/Hans21223/Sprocket-Mod-Loader/blob/main/docs/UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation).

**Validation:** the new native fingerprint matches Steam build 25808118. Seven hook, caller and helper functions match the previous build after verified relocations; prologues, call paths and calling conventions passed offline checks. Runtime/Common/HarmonySupport built with zero errors and 184 existing warnings. All 111 shared-hook checks, 66 manager fixture tests and the manager self-test passed. Prepared loader files, package CRCs and checksums were verified. No game session was launched for this update; 0.2.56.0 startup, editor operation and gameplay remain for user testing. The previously documented shutdown issue remains unresolved.

The compatibility comment below conservatively records the new game version. The release also supports the exact 0.2.55.5 native/metadata pair; future game builds need new validation.

<!-- sp-compat {"hamish.sprocket": "0.2.56.0", "bepinex.bepinex": "6.0.0-be.788"} -->
