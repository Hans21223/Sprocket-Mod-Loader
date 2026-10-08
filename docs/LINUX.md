# Linux and Steam Deck install

Sprocket is a Windows game, so on Linux it runs through Steam's Proton. The mod loader works the same way there, with two differences:

- **Mod Manager doesn't run on Linux.** It uses Windows-only functions, so install the loader with the terminal commands below instead.
- **Steam needs one launch option** so Proton loads the loader's `winhttp.dll` (step 3). Without it, the game starts unmodded.

This guide has not been tested on a real Linux PC yet. If something doesn't work, send `BepInEx/LogOutput.log` from the game folder.

## 1. Find the game folder

In Steam, right-click **Sprocket** → **Manage** → **Browse local files**. It's usually one of these:

- `~/.local/share/Steam/steamapps/common/Sprocket` (normal Steam, Steam Deck)
- `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Sprocket` (Flatpak Steam)
- `<your drive>/SteamLibrary/steamapps/common/Sprocket` (another library)

Launch Sprocket at least once without mods first, so Proton sets it up. Then close it.

## 2. Install the loader

Open a terminal (on Steam Deck, switch to Desktop Mode and open **Konsole**). Change the first line if your game folder is somewhere else, then paste all of it:

```bash
cd ~/.local/share/Steam/steamapps/common/Sprocket || exit
[ -f Sprocket.exe ] || { echo "This is not the Sprocket folder"; exit 1; }
curl -fL -o bepinex.zip 'https://builds.bepinex.dev/projects/bepinex_be/788/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788%2B5b766a3.zip'
curl -fL -o patch.zip 'https://github.com/Hans21223/Sprocket-Mod-Loader/releases/download/v1.2.2/Sprocket-Mod-Loader-1.2.2.zip'
sha256sum -c <<'SUMS' || exit
f4cc496bd098a0df4164b81e3737297707f13a47c2478dba2f60eefab784817a  bepinex.zip
c1eed21905511ec32ba2042c2c99c10a18f44850f9edac853b07483faad13055  patch.zip
SUMS
unzip -oq bepinex.zip
unzip -oq patch.zip 'Sprocket-Mod-Loader-1.2.2/Patch/*' -d patch-tmp
cp -r patch-tmp/Sprocket-Mod-Loader-1.2.2/Patch/BepInEx .
rm -rf patch-tmp bepinex.zip patch.zip
echo "Loader installed"
```

What it does:
- downloads official BepInEx be.788 and the Sprocket 1.2.2 patch;
- checks both files' SHA-256 (it stops if either doesn't match);
- unpacks BepInEx into the game folder, then copies the patch's five DLLs over BepInEx's.

Both `bepinex.zip: OK` and `patch.zip: OK` must appear before `Loader installed`.

If upgrading an existing loader, close Sprocket and [back up and rename its generated cache folders](UNITY-UI-COMPATIBILITY.md#upgrading-an-existing-installation) before the next launch. Old wrapper caches may otherwise retain the missing F1 menu constructor.

No `unzip` or `curl`? Install them with your package manager, for example `sudo apt install unzip curl` or `sudo pacman -S unzip curl`.

## 3. Add the launch option

In Steam, right-click **Sprocket** → **Properties** → **General** → **Launch options**, and paste:

```
WINEDLLOVERRIDES="winhttp=n,b" %command%
```

This tells Proton to use the loader's `winhttp.dll` instead of its own. You need it every time, so leave it there.

## 4. Launch and check

Start Sprocket from Steam. The first start takes longer than usual while BepInEx sets itself up. Once the main menu appears, close the game and check that `BepInEx/LogOutput.log` exists in the game folder. If it does, the loader works.

If there's no `BepInEx/LogOutput.log`, the launch option is missing or mistyped. If the game won't start, try **Properties** → **Compatibility** → **Proton Experimental**.

## 5. Add mods

- **BepInEx mods** (for example [Sprocket Quality of Life](https://github.com/Hans21223/Sprocket-Quality-of-Life)): put the mod's `.dll` in `BepInEx/plugins`.
- **MelonLoader mods:** first download **MLLoader IL2CPP BepInEx6 V0.7.3 / 2.3.9** from [Tong317's Nexus page](https://www.nexusmods.com/ironnest/mods/26). Unpack its `BepInEx` and `MLLoader` folders into the game folder, then repeat the `cp -r patch-tmp/...` part of step 2 (all of step 2 is fine too) so the patch's DLLs stay on top. Put MelonLoader mods in `MLLoader/Mods`.

Linux cares about capital letters in folder names. If a mod's ZIP has a `bepinex` or `plugins` folder with different capitals, move its files into the existing `BepInEx/plugins` folder instead of making a second folder next to it.

## Remove everything

Remove the launch option from step 3. Then, in the game folder:

```bash
rm -rf BepInEx MLLoader dotnet winhttp.dll doorstop_config.ini .doorstop_version changelog.txt
```

Steam's **Verify integrity of game files** doesn't delete these extra files, so it's not enough on its own. Your saves and tanks aren't in these folders, so they're safe.
