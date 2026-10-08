// Modified 2026-10-08: separately traced Sprocket 0.2.55.5 and 0.2.56.0 native profiles.
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
    internal const string UpdatedGameAssemblySha256 = "ADB36B5F04662BE0D40C6E548C797394659A9C0D4B009E3C0E718833ABF90B3A";
    private sealed record NativeProfile(string Version, string MetadataSha256,
        int ClassInitRva, int FieldDefaultRva, int GenericMethodRva);
    private static readonly Lazy<NativeProfile?> Verified = new(Verify);
    internal static bool Active => Verified.Value != null;
    private static NativeProfile Current => Verified.Value ?? throw new InvalidOperationException("Sprocket profile is not active");

    private static NativeProfile? Verify()
    {
        if (!OperatingSystem.IsWindows() || IntPtr.Size != 8 ||
            !string.Equals(Path.GetFileNameWithoutExtension(Environment.ProcessPath), "Sprocket", StringComparison.OrdinalIgnoreCase))
            return null;
        using var stream = File.OpenRead(InjectorHelpers.Il2CppModule.FileName);
        using var sha = SHA256.Create();
        var hash = Convert.ToHexString(sha.ComputeHash(stream));
        var profile = hash switch
        {
            GameAssemblySha256 => new NativeProfile("0.2.55.5",
                "6B0D5FB3E62F4F765C2E56289B8DCD8BC81F21FCCEF938D69CEDFFA5D31C52E0", 0x4E4160, 0x4945E0, 0x4CF780),
            UpdatedGameAssemblySha256 => new NativeProfile("0.2.56.0",
                "1B3052E0BC7391633366F8E246BB61F56B4F21D290A67949CB4E44CB5FEB2912", 0x4E46B0, 0x494B30, 0x4CFCD0),
            _ => throw new NotSupportedException("This local Sprocket bridge requires a verified Unity 6000.3.21f1 GameAssembly. Game updated: disable this patch and rebuild the profile.")
        };
        var metadata = Path.Combine(Path.GetDirectoryName(InjectorHelpers.Il2CppModule.FileName)!,
            "Sprocket_Data", "il2cpp_data", "Metadata", "global-metadata.dat");
        if (!File.Exists(metadata))
            throw new NotSupportedException("Sprocket game metadata is missing. Verify the game files in Steam before using this patch.");
        using var metadataStream = File.OpenRead(metadata);
        if (Convert.ToHexString(sha.ComputeHash(metadataStream)) != profile.MetadataSha256)
            throw new NotSupportedException("Sprocket GameAssembly and game metadata belong to different builds. Verify the game files in Steam before using this patch.");
        Logger.Instance.LogInformation("Sprocket {Version} / Unity 6000.3.21f1 compatibility profile: native and metadata SHA-256 verified", profile.Version);
        return profile;
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
    internal static IntPtr ClassInit => Address(Current.ClassInitRva, new byte[] { 0x40, 0x53, 0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9 });
    // il2cpp_field_static_get_value -> Field::StaticGetValue -> GetDefaultFieldValue.
    internal static IntPtr FieldDefault => Address(Current.FieldDefaultRva, new byte[] { 0x48, 0x89, 0x5C, 0x24, 0x08 });
    // Object::GetVirtualMethod -> GetGenericVirtualMethod -> GetMethod(GenericMethod&).
    internal static IntPtr GenericMethod => Address(Current.GenericMethodRva, new byte[] { 0x40, 0x55, 0x53, 0x56, 0x57, 0x41, 0x54 });
}
