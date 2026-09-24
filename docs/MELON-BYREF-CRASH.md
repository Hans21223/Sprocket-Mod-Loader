# Editor-entry crash with Sprocket Tweaks: fixed in 1.2.0

The shared-hook repair in 1.1.0 solved the Hello Melon / QoL alias collision. A second crash occurred with Sprocket Tweaks 1.1.0 simply entering the vehicle editor. Both defects were real; passing the first test did not cover the second.

The Windows crash dump's managed stack identified `WheelBuild.Prefix(ref WheelArrayBlueprint)` calling `WheelArrayBlueprint.get_MeshGuid`, then `Il2CppStringToManaged` and `il2cpp_string_length`. The string pointer was invalid.

`WheelArrayBlueprint` is a native value type represented by an `Il2CppSystem.ValueType` wrapper on the managed side. A native by-reference argument points directly to its struct data. The old Harmony bridge treated it like a reference to an object pointer, dereferenced its first field, and wrapped that as the blueprint object. Accessing MeshGuid then read an invalid string. The upstream code explicitly left this by-reference boxed-value-type case unimplemented.

The bridge now boxes a copy of the actual incoming struct, passes a reference to that managed wrapper to Harmony, and copies the complete unboxed struct back to the caller's buffer afterward. Primitive and ordinary object-reference arguments keep their existing paths. The gameplay mod's wheel feature was not removed or disabled.

## Validation

- HarmonySupport builds with zero errors (existing upstream warnings remain).
- Test copy loaded original Hello Melon 1.0.0, Sprocket Tweaks 1.1.0, MLLoader 2.3.9 and Sprocket QoL.
- Vehicle editor opened with the tank and wheels visible. The same wheel-build path that previously crashed completed.
- Logs recorded part-weight callbacks, Hello Melon's cannon Harmony callback, and the tyre adjustment from 166.5 kg to 8.3 kg. The game continued updating in sandbox.
- This verifies the reported editor crash and those callbacks, not a complete campaign, every mod feature, or standalone MelonLoader. Sprocket Tweaks' engine-base calculation reported zero and left that weight unchanged; this release does not claim to fix that separate mod calculation.
- A later shutdown produced a separate UnityPlayer access violation after preferences were saved. Its cause is not isolated. This release is a preview and does not claim crash-free shutdown.

Only the tested Sprocket game build is supported. Use the 1.2.0 package or the manager's Install mod loader button. Close the game before installation. Raw dumps, game assemblies and personal logs are not included in this repository.
