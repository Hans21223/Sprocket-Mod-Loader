# Validation and limitations

Runtime evidence was collected on 23 September 2026 using Sprocket 0.2.55.5 / Unity 6000.3.21f1 with the exact GameAssembly fingerprint in README.md.

## Recorded runtime checks

- Original loader without plugins: an access violation in Class_GetFieldDefaultValue_Hook.Hook was recorded. Earlier no-plugin runs also hung during main-menu loading.
- Patched runtime: build completed with zero errors; 184 upstream/existing warnings remained.
- Binary profile validator passed the fingerprint, three PE unwind function boundaries, six call edges, generic argument-layout evidence and the incorrect signature-match evidence.
- Patched loader without plugins: main menu displayed, Settings responded, and this test process exited with code 0.
- Diagnostic BepInEx plugin: native generic-list operations passed, enum reflection returned 339 fields, and an injected MonoBehaviour received Update calls.
- Sandbox Flat loaded; vehicle simulation started; logs showed Vehicle Control and continuing plugin updates through frame 20000.
- Later turret-mod logs recorded successful in-game blueprint conversions and reloads using the same patched runtime. The turret mod is a separate package.

## Not established

Full campaigns, long-term stability, every third-party mod combination, standalone MelonLoader and other game builds have not been validated. The final simulation run's clean exit was not captured. The individual contribution of each of the three runtime corrections was not isolated experimentally. Personal logs/screenshots and game files are deliberately excluded from this sharing pack.

Package preparation checks are documented in PACKAGE-CHECKS.txt. They verify packaging and checksums, not a new game session.

## 1.2.1 Unity UI constructor regression, 2 October 2026

The supplied SprocketModAPI log identifies a missing four-integer `UnityEngine.RectOffset` constructor in the F1 and keybinding UI. Both installed generated wrapper caches were confirmed to omit that overload while retaining the native-backed empty constructor and all four padding setters. The new generator pass delegates to those existing members before writing the assemblies and native method maps; it adds no fictitious native method pointer.

The generator and separate existing-cache repair tool build successfully. 200 focused checks passed across the generator and repair tool: constructor allocation and argument order, absent/native-member guards, idempotence, existing wrapper method preservation, and native method-token mapping. The previously released Runtime, Common, HarmonySupport and TerraFX DLLs remain byte-identical. Opening the native F1 and keybinding menus in a new game session was not performed. No turret-spawn repair is claimed: the supplied screenshot contains no matching first exception for that separate report.

## 1.2.0 by-reference struct regression, 24 September 2026

The crash dump for editor entry with Sprocket Tweaks 1.1.0 identified an invalid string access through its by-reference WheelArrayBlueprint patch. With the corrected bridge, the editor loaded, wheel weights were reported, the air-tyre adjustment ran (166.5 to 8.3 kg), and original Hello Melon's cannon callback ran. See MELON-BYREF-CRASH.md for evidence and limits. The earlier shared-hook tests remain passing.

## 1.1.0 shared-hook regression, 24 September 2026

111 native relay checks pass; HarmonySupport builds with zero errors. Original Hello Melon 1.0.0 and Sprocket QoL 1.3.0 ran together through MLLoader 2.3.9 in the sandbox cannon inspector. The Hello Melon hook logged success, the QoL Gun length panel rendered, and the game remained running. See MELON-HOOK-CRASH.md for details and limits.
