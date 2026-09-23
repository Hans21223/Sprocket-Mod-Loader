Unofficial BepInEx be.788 compatibility pack for **Sprocket 0.2.55.5 / Unity 6000.3.21f1, Windows x64**.

Download **Sprocket-Mod-Loader-1.0.0.zip**, extract it, and run **Prepare Loader.cmd**. Read the included README before installing. The script downloads and checks the official BepInEx base, then prepares the patched loader. It does not change the game automatically.

The bridge repairs the incorrect field-default hook target, uses the verified Class::Init function, and matches this binary's generic-method calling convention. The precise cause of the earlier silent black-screen hang was not isolated; the field-hook crash is directly evidenced.

The release includes installation/removal instructions, an explanation of the original failure, corresponding bridge source, licenses and checksums. It contains no gameplay mods or personal game files.

Recorded runtime tests covered the main menu, Settings, a diagnostic managed plugin and sandbox simulation. Package preparation matches the tested loader's 229 files. Full campaigns and every plugin combination are unverified. This release rejects unsupported Sprocket binaries; it is not a general Unity 6 or MelonLoader fix.

ZIP SHA-256:
`e0c1e52f1eb3e976d27ed788aaba47ae87d9f48dc6165de25dc9b437ee51d7ac`

Use the named release asset, not GitHub's automatically generated Source code ZIP, for installation.
