# Local bridge changes (2026-09-23, 2026-09-24 and 2026-10-02)

Source base: BepInEx/Il2CppInterop commit 81a6f78c8b653e0da4a3420ac4cd00819e8b6292.
This is an unofficial modified version, distributed under LGPL-3.0-only.

Changed files:
- Injection/InjectorHelpers.cs: select the hash-verified Sprocket Class::Init target and one-argument generic hook.
- Injection/Hooks/Class_GetFieldDefaultValue_Hook.cs: use the verified field-default target for this Sprocket binary.
- Injection/Hooks/SprocketGenericMethodHook.cs: new one-argument generic-method detour.
- Injection/SprocketUnity6Profile.cs: new exact game fingerprint, addresses and prologue guards.

The four paths above are under Il2CppInterop.Runtime.

Version 1.1.0 also modifies Il2CppInterop.HarmonySupport/Il2CppDetourMethodPatcher.cs and adds SprocketNativeHookChain.cs beside it. For the verified Sprocket profile, different managed wrappers for the same native function share one physical detour. A stable relay selects the newest wrapper; copied native MethodInfo structures forward each wrapper to its predecessor and ultimately the original game function. Rebuilding Harmony patches updates this chain without hooking reverse-P/Invoke callback thunks. Other games keep the upstream backend.

Version 1.2.0 repairs by-reference Il2CppSystem.ValueType argument conversion in Il2CppDetourMethodPatcher. It boxes the data at the incoming struct address instead of dereferencing its first field as an object pointer, then copies the entire unboxed struct back after the call. This fixes the observed WheelArray.Build / WheelArrayBlueprint.MeshGuid crash with Sprocket Tweaks 1.1.0. Blittable references and ordinary object references retain their original conversion paths. Runtime validation covers the reported Sprocket wheel/editor case, not all possible value types or games.

Version 1.2.1 adds `Il2CppInterop.Generator/Passes/Pass82RestoreUnityUiConstructors.cs` and runs it from `Runners/InteropAssemblyGenerator.cs` after Unity unstripping and before native method maps and assembly output. It restores the missing managed `UnityEngine.RectOffset(int left, int right, int top, int bottom)` convenience constructor only when the expected native-backed wrapper, empty constructor and padding setters are present. The overload calls the empty constructor once and then each setter; it does not fabricate a native constructor pointer. This addresses SprocketModAPI's reported F1/keybinding menu `MissingMethodException` without rewriting its mod DLL. Generator and cache-repair builds plus 200 focused checks passed; native in-game menus have not been retested.

Hook sites and retired delegates intentionally remain rooted for the process lifetime so a native caller cannot return through collected callbacks. Removing a wrapper's Harmony patches rebuilds its body as a forwarding wrapper; it does not dispose the shared hook and disrupt other wrappers. This supports both canonical Sprocket types and MLLoader's Il2CppSprocket aliases without modifying the mods.
Source archive copies carry a dated comment identifying these modifications. The comments were added for redistribution; they do not alter the compiled behavior.

## Build

Install .NET SDK 8 (the tested SDK was 8.0.425). Extract this archive and open a terminal in Il2CppInterop. Run:

    dotnet build Il2CppInterop.HarmonySupport/Il2CppInterop.HarmonySupport.csproj -c Release -p:GeneratePackageOnBuild=false

NuGet access is required to restore dependencies. Runtime targets .NET 6 and Common targets .NET Standard 2.0. Keep the repository's included Runtime/Libs/Il2Cppmscorlib.dll reference; do not substitute a game-generated assembly. Output is under bin/Il2CppInterop.Runtime/net6.0 and bin/Il2CppInterop.Common/netstandard2.0. TerraFX.Interop.Windows 10.0.22621.2 is a NuGet dependency; deploy its DLL alongside Runtime and Common. Build metadata may differ across environments; no byte-identical build is promised.

HarmonySupport output is under bin/Il2CppInterop.HarmonySupport/net6.0. The release preserves the three already-tested 1.0.0 dependency DLLs and adds the rebuilt HarmonySupport DLL. The repository's tests/NativeHookChain console project exercises the actual relay implementation without proprietary game assemblies.

For the 1.2.1 Generator overlay, run:

    dotnet build Il2CppInterop.Generator/Il2CppInterop.Generator.csproj -c Release -f netstandard2.1 -p:GeneratePackageOnBuild=false

The output is `bin/Il2CppInterop.Generator/netstandard2.1/Il2CppInterop.Generator.dll`. Keep the existing Runtime, Common, HarmonySupport and TerraFX DLLs from 1.2.0. Only the new Generator DLL is added in 1.2.1. Its assembly version remains compatible with be.788, so existing wrapper caches must be regenerated or repaired after upgrading. Focused generator and cache-repair tests and the optional .NET 8 cache-repair source are in the public repository's `tools/UnityUiCompatibility.Tests` and `tools/UnityUiCompatibility` folders; these tools are not required for a fresh loader installation.

No Sprocket executable, game assets, personal data or generated Sprocket assemblies are included. The Libs reference assembly is the one tracked in the upstream repository.

## Future game builds

Re-establish function boundaries, exported call paths and calling conventions against the new binary, then test startup, injected components and gameplay. Do not merely replace the allowed game hash. The existing constants apply only to the fingerprint documented in SprocketUnity6Profile.cs.
