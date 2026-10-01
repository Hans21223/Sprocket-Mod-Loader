# Unity UI constructor compatibility checks

Focused checks for the generator's `Pass82RestoreUnityUiConstructors.RestoreRectOffset` helper. Tests read the actual BepInEx and MelonLoader `UnityEngine.CoreModule` wrappers, restore a copy in memory, serialize only to a separate evidence directory, and check that every existing method retains its signature and body. They also execute the reconstructed body against a managed stand-in with the same base-type name, so argument order and exactly one allocation are checked without starting Unity.

The tests preserve input files. Existing repaired overloads are first verified as unchanged, then removed from the in-memory copy to exercise restoration again. Guard cases cover absent/private/bodyless/ambiguous constructors and setters, static or incorrectly typed setters, incompatible types, and existing overloads.

After building the generator's `netstandard2.1` Release target:

```powershell
dotnet run --project tools/UnityUiCompatibility.Tests -c Release -- "D:\Projects\SprocketInteropPatch\TestGame" "D:\Projects\SprocketInteropPatch\evidence\unity-ui-generator-tests"
```

Success prints `UNITY_UI_GENERATOR_TESTS_OK`. These checks validate generated managed code and preservation of wrapper methods; they do not claim a game-runtime menu test.
