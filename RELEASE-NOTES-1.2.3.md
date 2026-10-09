**Game updates no longer need a new loader** when they keep Unity's IL2CPP runtime unchanged, which is the usual case for Sprocket's patches and experimental builds such as **0.2.56.1**.

Until now the loader only accepted the exact game files it had been checked against, so every Sprocket update turned all mods off until a new loader was released. Loader 1.2.3 finds its three native hook targets in each game build itself, at every start:

- It follows the same exported call paths that were traced by hand for 0.2.55.5 and 0.2.56.0.
- It accepts each target only as the single candidate with the verified entry bytes, calling-convention bytes and function length.

An update that changes that runtime code, for example a new Unity version, is still refused. Mods then stay off, the game runs normally, and the log says why. BepInEx and MLLoader already regenerate their interop assemblies after an update.

- **Sprocket-Mod-Loader-1.2.3.zip:** the five compatibility libraries, preparation helper, corresponding bridge source and license notices. Download official BepInEx be.788 separately or use the helper.
- **Sprocket-Mod-Manager-1.3.7.zip:** source-only Windows manager. **Install mod loader** installs loader 1.2.3 and checks the game with the same trace instead of a list of exact file fingerprints. Replace its program files while keeping games.json, mods, state and backups.
- Each ZIP has a SHA-256 checksum file.

**Updating:** close Sprocket and install through the manager that owns the loader, or copy the three changed DLLs from `Patch/BepInEx/core` (Runtime, Common, HarmonySupport) over the old ones. The interop caches don't need resetting. After that, game updates like 0.2.56.1 need nothing.

**Testing:**
- On Sprocket 0.2.56.1, after Steam's update, the loader traced the runtime and loaded BepInEx, MLLoader and four plugins: Sprocket Mod API, Battle Editor, Map Framework and Quality of Life. The game reached the main menu.
- Run against the real game files, the trace finds exactly the hand-verified targets of 0.2.55.5 and 0.2.56.0 and refuses a broken call path.
- All 111 shared-hook checks and 70 manager tests passed.

Individual mods can still need their own updates when the game code they change is changed.

<!-- sp-compat {"hamish.sprocket": ["0.2.55.5", "0.2.56.0", "0.2.56.1"], "bepinex.bepinex": "6.0.0-be.788"} -->
