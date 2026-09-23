// Modified 2026-09-23 for the unofficial Sprocket Unity 6000.3.21 profile; see LOCAL-CHANGES.md.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Il2CppInterop.Common;
using Microsoft.Extensions.Logging;

namespace Il2CppInterop.Runtime.Injection;

// Local compatibility profile. RVAs are valid ONLY for the fingerprint below.
// Never apply these addresses to another Unity build or a changed GameAssembly.
internal static class SprocketUnity6Profile
{
    internal const string GameAssemblySha256 = "18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56";
    private static readonly Lazy<bool> Verified = new(Verify);
    internal static bool Active => Verified.Value;

    private static bool Verify()
    {
        if (!OperatingSystem.IsWindows() || IntPtr.Size != 8 ||
            !string.Equals(Path.GetFileNameWithoutExtension(Environment.ProcessPath), "Sprocket", StringComparison.OrdinalIgnoreCase))
            return false;
        using var stream = File.OpenRead(InjectorHelpers.Il2CppModule.FileName);
        using var sha = SHA256.Create();
        var hash = Convert.ToHexString(sha.ComputeHash(stream));
        if (hash != GameAssemblySha256)
            throw new NotSupportedException("This local Sprocket bridge requires the verified Unity 6000.3.21f1 GameAssembly. Game updated: disable this patch and rebuild the profile.");
        Logger.Instance.LogInformation("Sprocket Unity 6000.3.21f1 compatibility profile: SHA-256 verified");
        return true;
    }

    internal static IntPtr Address(int rva, byte[] expectedPrologue)
    {
        if (!Active) throw new InvalidOperationException("Sprocket profile is not active");
        if (rva < 0 || rva + expectedPrologue.Length > InjectorHelpers.Il2CppModule.ModuleMemorySize)
            throw new InvalidOperationException("Sprocket hook address is outside GameAssembly");
        var address = InjectorHelpers.Il2CppModule.BaseAddress + rva;
        for (var i = 0; i < expectedPrologue.Length; i++)
            if (Marshal.ReadByte(address, i) != expectedPrologue[i])
                throw new NotSupportedException($"Sprocket hook prologue mismatch at RVA 0x{rva:X}");
        return address;
    }

    // mono_class_instance_size -> Class::Init, checks initialized bit at +0x135.
    internal static IntPtr ClassInit => Address(0x4E4160, new byte[] { 0x40, 0x53, 0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9 });
    // il2cpp_field_static_get_value -> Field::StaticGetValue -> GetDefaultFieldValue.
    internal static IntPtr FieldDefault => Address(0x4945E0, new byte[] { 0x48, 0x89, 0x5C, 0x24, 0x08 });
    // Object::GetVirtualMethod -> GetGenericVirtualMethod -> GetMethod(GenericMethod&).
    internal static IntPtr GenericMethod => Address(0x4CF780, new byte[] { 0x40, 0x55, 0x53, 0x56, 0x57, 0x41, 0x54 });
}
