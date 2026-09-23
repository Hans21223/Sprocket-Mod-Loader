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

Full campaigns, long-term stability, every third-party mod combination, MLLoader, real MelonLoader and other game builds have not been validated. The final simulation run's clean exit was not captured. The individual contribution of each of the three runtime corrections was not isolated experimentally. Personal logs/screenshots and game files are deliberately excluded from this sharing pack.

Package preparation checks are documented in PACKAGE-CHECKS.txt. They verify packaging and checksums, not a new game session.
