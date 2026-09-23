# Why original BepInEx showed a black screen or crashed

The loader reached Sprocket, but its Il2CppInterop bridge made assumptions that did not match Sprocket's Unity 6000.3.21f1 native code. Reinstalling the same loader or removing MLLoader did not correct those assumptions.

## The confirmed crash

The original bridge searched for a byte pattern to locate a Unity function that reads a field's default value. In this game, the pattern also matched an unrelated generated function. The loader picked that wrong function and attached its hook there. When it ran, the hook interpreted the wrong data as Unity field information and the baseline crashed with an access violation.

The recorded stack names `Il2CppInterop.Runtime.Injection.Hooks.Class_GetFieldDefaultValue_Hook.Hook`. Binary inspection showed the incorrect match at relative address `0x16D540`; the actual field-default target is `0x4945E0`, reached through the exported field-value call path. This is direct crash evidence, not just an interpretation of a warning.

## Two other compatibility corrections

1. **Class initialization:** the old signatures could not locate `Class::Init`, so the bridge logged `Class::Init signatures have been exhausted, using a substitute!`. The patched bridge directly uses the verified initialization function at `0x4E4160`. This is a direct call target, not an additional detour.
2. **Generic methods:** the upstream Unity 6 hook expected three arguments. This Sprocket binary uses a pointer to a single `Il2CppGenericMethod` structure. Its caller builds a 24-byte structure and passes its address. The patch uses a matching one-argument hook at `0x4CF780`.

All addresses above are offsets from the loaded GameAssembly module, so normal address randomization is preserved. The patch verifies the complete GameAssembly.dll hash and expected starting bytes before using these addresses.

## Why it looked like a black scene

The earlier runs reached main-menu scene loading but did not finish presenting the menu. BepInEx alone reproduced that hang, so MLLoader was not necessary to cause it. A bridge failure at this point can prevent normal startup from completing, leaving a black screen or causing a process crash.

**The exact cause of the earlier silent hang was not isolated.** The missing Class::Init warning alone does not prove that its fallback froze the game. The baseline access violation establishes the field-hook crash; the disassembly establishes the generic calling-convention mismatch. All three corrections were tested together, rather than in separate A/B runs.

## What changed

The pack overlays `Il2CppInterop.Runtime.dll` with the patched runtime and supplies its matching `Il2CppInterop.Common.dll` plus `TerraFX.Interop.Windows.dll`, needed by the newer upstream memory scanner. The remaining BepInEx be.788 loader files come from the official archive.

The result reached the menu, responded in Settings, ran a diagnostic managed plugin, and entered sandbox vehicle simulation in the recorded tests. It is a compatibility repair for one verified Sprocket build, not proof that every mod or future Unity version will work. The same result does not establish that real MelonLoader or MLLoader now works.
