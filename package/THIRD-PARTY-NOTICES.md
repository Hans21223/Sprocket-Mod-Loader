# Third-party notices and source provenance

This unofficial package changes Il2CppInterop, not the upstream BepInEx project name or ownership. No upstream endorsement is implied.

## Redistributed files

| Component | Origin | License |
| --- | --- | --- |
| Il2CppInterop.Runtime.dll (modified) | BepInEx/Il2CppInterop, source base 81a6f78c8b653e0da4a3420ac4cd00819e8b6292 | LGPL-3.0-only |
| Il2CppInterop.Common.dll (matching build) | Same Il2CppInterop source base | LGPL-3.0-only |
| TerraFX.Interop.Windows.dll 10.0.22621.2 (unmodified dependency) | TerraFX.Interop.Windows NuGet package; repository commit fadce5a41fa5e6f0282e80e96f033d0a2c130991 | MIT |

Il2CppInterop authors: knah, BepInEx and other upstream contributors. Existing upstream notices are retained in the included source. Corresponding source for Runtime and Common, their project files and upstream build scripts are in Source/Il2CppInterop-patched-source.zip. Local changes dated 2026-09-23 and reproduction instructions are listed in that archive's LOCAL-CHANGES.md. Replacement/rebuilding of these libraries is permitted under their licenses; the compatibility fingerprint guards unsupported game binaries, not user modifications to this library.

TerraFX: Copyright (c) Tanner Gooding and Contributors. The complete MIT notice is included in Licenses/TerraFX-MIT.txt. Source: https://github.com/terrafx/terrafx.interop.windows/tree/fadce5a41fa5e6f0282e80e96f033d0a2c130991

Il2CppInterop source: https://github.com/BepInEx/Il2CppInterop/tree/81a6f78c8b653e0da4a3420ac4cd00819e8b6292

LGPL v3 incorporates GPL v3; both full texts are in Licenses. The preparation scripts and local bridge changes are distributed under LGPL-3.0-only. Documentation may be copied with the package.

## Downloaded on the recipient's computer

The official BepInEx be.788 ZIP is not embedded in this sharing package. Prepare Loader downloads it from https://builds.bepinex.dev/projects/bepinex_be and verifies its exact SHA-256 before extracting it and applying the local bridge overlay. BepInEx, Doorstop, .NET and bundled third-party components retain their own licenses and attribution. The download includes the upstream runtime notices; the script preserves them.

BepInEx source for be.788: https://github.com/BepInEx/BepInEx/tree/5b766a3b7f6c164d4798924a93f3acf4db769d06

To redistribute the assembled Ready-to-copy folder separately, also satisfy the source and notice requirements for its additional upstream components. Sharing this original source-inclusive patch package and letting recipients obtain the official base avoids stripping those components from their upstream distribution context.
