# MelonLoader/BepInEx shared-hook crash fixed in 1.1.0

## Trigger and evidence

Hello Melon 1.0.0 patches `Il2CppSprocket.Vehicles.Cannons.Editor.CannonEditor.OnGUI`. Sprocket QoL 1.3.0 patches `Sprocket.Vehicles.Cannons.Editor.CannonEditor.OnGUI`. The managed wrappers have different identities, but point to the same native game function.

The original backend installed two independent native detours. With BepInEx be.788's jump-following code, the second installation resolved the existing detour as an export thunk and attached to the first hook's managed callback entry. The original logs contain this redirection, and Windows recorded repeated access violations in coreclr.dll when the cannon inspector was used.

Pointing Hello Melon at the canonical wrapper avoided the crash in an intermediate diagnostic test. That workaround was then reverted: **the final fix changes the loader, and Hello Melon 1.0.0 remains byte-for-byte unchanged.**

## Loader change

`Il2CppInterop.HarmonySupport.dll` now shares one physical native detour among wrappers that point to the same native function, for the existing hash-verified Sprocket profile. Each wrapper retains its own Harmony patches and type conversions. Its original-call pointer forwards to the preceding wrapper, and the oldest wrapper forwards to the real game function. Updating a patch changes these links instead of patching a managed callback thunk.

The stable relay and retired delegates remain alive for the process lifetime. Signatures are checked before adding another wrapper. Other games retain the upstream hook implementation. This change belongs to the BepInEx/Il2CppInterop compatibility layer used by MLLoader; it is not a replacement for standalone MelonLoader.

## Verification on 24 September 2026

- 111 focused checks pass against the actual relay code: two aliases, forwarding to the original exactly once, patch refresh, removal of patch effects, ABI mismatch rejection, full garbage collection, by-reference arguments, and 100 repeated refreshes.
- HarmonySupport builds with zero errors.
- Sprocket test copy runs the patched HarmonySupport, MLLoader 2.3.9, Sprocket QoL 1.3.0, and **original Hello Melon 1.0.0**.
- Hello Melon original SHA-256: `3AF88490CE7DA26C656DB2E4627387684F2A4EAED2F0939D499FADE2205723D5`.
- The sandbox vehicle editor loaded. Opening the cannon inspector produced `HELLO_MELON Harmony patch ran (a Cannon panel opened)` while the QoL **Gun length** section was visible in that same panel. The game remained running.

This verifies the reported collision. It does not establish compatibility with every MelonLoader mod, every native hook API, every patch ordering arrangement, or other game versions. The separate earlier startup failure and the long startup delay are different issues. A nonfatal MLLoader diagnostic about an access-denied process operation still appears during startup; this patch does not address it.

## Install or update

Use the 1.1.0 release and its installation instructions. Existing 1.0.0 users can close Sprocket, back up their old `BepInEx/core/Il2CppInterop.HarmonySupport.dll`, and replace it with the DLL at that path in `Patch`. For a manager-owned installation, update the loader's stored mod while disabled, then re-enable it. Do not overwrite a running game's DLLs.

MLLoader and gameplay mods remain separate downloads. No Hello Melon or QoL DLL is bundled in the loader release.
