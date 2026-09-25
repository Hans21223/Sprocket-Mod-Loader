Mod Manager 1.3.2: one click installs everything. The loader is unchanged from 1.2.0.

- **Finds Sprocket by itself.** On first start the manager looks next to its own folder, then in every Steam library. The `ModManager` folder no longer has to sit inside the game folder.
- **Finds MLLoader by itself.** **Install mod loader** uses the MLLoader 2.3.9 ZIP from Downloads, the Desktop, or in or next to the manager folder, checked by SHA-256. It asks only when there's none. MLLoader still has to be downloaded from Nexus Mods by hand, because Nexus needs a login.
- **MLLoader is optional.** Without its ZIP, setup can install BepInEx and the Sprocket patch alone, enough for BepInEx mods. Click **Install mod loader** again later to add MLLoader. Setup never removes MLLoader while MelonLoader mods use it.
- **Clearer Mod report.** It starts by saying if the loader isn't installed, hasn't run yet, or shares the game folder with a separate MelonLoader. A mod that needs the missing loader is told to click **Install mod loader** rather than blamed. Enabling a BepInEx plugin before BepInEx is installed is refused with that instruction.
- **Remove mod button.** Select a mod and click **Remove mod**: it's disabled (the game's original files come back) and the manager's copy is deleted, after asking first.
- **Sprocket-Mod-Manager-1.3.2.zip:** extract `ModManager` anywhere it can stay. Existing users replace `modman.pyw`, `loader_setup.py` and `mod_compat.py` and keep their configuration and data.

The manager's 21 unit tests pass on Python 3.10 and 3.12, including new tests for finding the game and MLLoader and for installing with and without MLLoader. The main window was driven headlessly through first-run game detection and both setup paths, and Remove mod was clicked on an enabled mod. Not yet run on Windows.
