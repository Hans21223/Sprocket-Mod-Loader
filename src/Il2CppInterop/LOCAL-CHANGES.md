# Local bridge changes (2026-09-23)

Source base: BepInEx/Il2CppInterop commit 81a6f78c8b653e0da4a3420ac4cd00819e8b6292.
This is an unofficial modified version, distributed under LGPL-3.0-only.

Changed files:
- Injection/InjectorHelpers.cs: select the hash-verified Sprocket Class::Init target and one-argument generic hook.
- Injection/Hooks/Class_GetFieldDefaultValue_Hook.cs: use the verified field-default target for this Sprocket binary.
- Injection/Hooks/SprocketGenericMethodHook.cs: new one-argument generic-method detour.
- Injection/SprocketUnity6Profile.cs: new exact game fingerprint, addresses and prologue guards.

The four paths above are under Il2CppInterop.Runtime. Other upstream source files are unchanged.
Source archive copies carry a dated comment identifying these modifications. The comments were added for redistribution; they do not alter the compiled behavior.

## Build

Install .NET SDK 8 (the tested SDK was 8.0.425). Extract this archive and open a terminal in Il2CppInterop. Run:

    dotnet build Il2CppInterop.Runtime/Il2CppInterop.Runtime.csproj -c Release -p:GeneratePackageOnBuild=false

NuGet access is required to restore dependencies. Runtime targets .NET 6 and Common targets .NET Standard 2.0. Keep the repository's included Runtime/Libs/Il2Cppmscorlib.dll reference; do not substitute a game-generated assembly. Output is under bin/Il2CppInterop.Runtime/net6.0 and bin/Il2CppInterop.Common/netstandard2.0. TerraFX.Interop.Windows 10.0.22621.2 is a NuGet dependency; deploy its DLL alongside Runtime and Common. Build metadata may differ across environments; no byte-identical build is promised.

No Sprocket executable, game assets, personal data or generated Sprocket assemblies are included. The Libs reference assembly is the one tracked in the upstream repository.

## Future game builds

Re-establish function boundaries, exported call paths and calling conventions against the new binary, then test startup, injected components and gameplay. Do not merely replace the allowed game hash. The existing constants apply only to the fingerprint documented in SprocketUnity6Profile.cs.
