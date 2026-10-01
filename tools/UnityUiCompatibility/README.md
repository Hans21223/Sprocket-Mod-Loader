# Unity UI constructor compatibility

SprocketModAPI 0.3.0 uses `new UnityEngine.RectOffset(left, right, top, bottom)` in its F1 mod menu and keybinding UI. The current Unity 6 generated wrappers omit this managed convenience constructor. The resulting `MissingMethodException` disables those two UI controllers for the rest of the session; ordinary hotkeys continue working.

The generator's `Pass82RestoreUnityUiConstructors` restores the overload before writing assemblies and native method maps. It calls the existing parameterless constructor once, then the four existing padding setters. It adds no native method pointer and makes no changes to third-party mod DLLs.

The executable here repairs existing generated wrapper caches. It refuses to overwrite its input, verifies every existing wrapper method remains unchanged, and remaps the companion `MethodAddressToToken.db` by method signature and duplicate declaration order. Native addresses and records belonging to other assemblies stay unchanged. `MethodXrefScanCache.db` stays untouched.

Build with a .NET 8 SDK and set `CecilPath` if Mono.Cecil is elsewhere:

```powershell
dotnet build tools/UnityUiCompatibility/UnityUiCompatibility.csproj -c Release -p:CecilPath="C:\path\to\BepInEx\core\Mono.Cecil.dll"
dotnet tools/UnityUiCompatibility/bin/Release/net8.0/UnityUiCompatibility.dll self-test C:\temp\rectoffset-tests
```

With Sprocket closed, repair an existing installation:

```powershell
& .\tools\UnityUiCompatibility\Repair-UnityUi.ps1 -GamePath 'C:\path\to\Sprocket'
```

Use `-DotNetPath` to select a .NET host and `-RepairTool` if using a copied build. Keep the DLL, runtimeconfig, deps and Mono.Cecil dependency together. The script stages and verifies all repairs before installation, retains originals and a checksum manifest under `GamePath\UnityUiRepair`, and restores changed files if installation fails. Both BepInEx and MLLoader cache locations are supported when present. It does not create a loader or change mod files.

Restart the game after repairing: the failed UI controller cannot recover inside the same session. This repair removes the reported missing constructor; opening both menus still needs game testing. Regenerating caches with an older generator can remove it again, so use the updated generator or rerun the repair after regeneration.

The separate report about failing to spawn after adding a turret has no exception in the supplied screenshot. It needs the first exception in a full log from that failed spawn attempt. The menu's constructor error does not establish the cause of that failure.
