Mod Manager 1.3.6: works alongside the [Sprocket Mod API](https://github.com/furryaxw/SprocketModAPI). The loader is unchanged at 1.2.2.

- **Optional mods aren't reported as missing:** a mod that declares another plugin as a soft dependency (`[BepInDependency(..., SoftDependency)]`), such as Quality of Life 1.8.7, Battle Editor 0.17.31 and Language 0.2.0 with the Sprocket Mod API, works without it. **Mod report** no longer says it "needs SprocketModAPI" when the API isn't installed.
- **Mods turned off in the game's Mods menu:** the Sprocket Mod API turns a mod off by renaming `X.dll` to `X.dll.disable`. Mod report now says the mod is turned off there (instead of "files deleted outside the Mod Manager"), and **Disable** removes the renamed file along with the rest of the mod.
- Fixed the metadata reader's custom-attribute type tags (ECMA-335 tags 2 and 3), which the soft-dependency check is the first to use.
- **Sprocket-Mod-Manager-1.3.6.zip:** existing users replace the program files in `ModManager` and keep `games.json`, mods, state and backups. **Sprocket-Mod-Loader-1.2.2.zip** is attached unchanged for new installations.

All 69 manager tests and the self-test pass (Python 3.14, Windows).
