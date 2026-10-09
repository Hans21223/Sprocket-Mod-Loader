// Modified 2026-10-10: trace the native targets of each game build instead of pinning exact GameAssembly hashes.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using Il2CppInterop.Common;
using Microsoft.Extensions.Logging;

namespace Il2CppInterop.Runtime.Injection;

// Sprocket's Unity 6000.3.21f1 IL2CPP runtime. The three hook targets are not exported, and every game update moves
// them. They are traced from exported entry points along the call paths established for 0.2.55.5 and 0.2.56.0, and
// each is accepted only as the single candidate with the verified entry bytes, ABI bytes and function length. An
// update that changes this runtime code is refused rather than guessed at.
internal static class SprocketUnity6Profile
{
    internal sealed record Targets(int ClassInit, int FieldDefault, int GenericMethod);
    private static readonly Lazy<Targets?> Verified = new(Verify);
    internal static bool Active => Verified.Value != null;
    private static Targets Current => Verified.Value ?? throw new InvalidOperationException("Sprocket profile is not active");

    private static Targets? Verify()
    {
        if (!OperatingSystem.IsWindows() || IntPtr.Size != 8 ||
            !string.Equals(Path.GetFileNameWithoutExtension(Environment.ProcessPath), "Sprocket", StringComparison.OrdinalIgnoreCase))
            return null;
        var module = InjectorHelpers.Il2CppModule.BaseAddress;
        var targets = Trace(module, name => NativeLibrary.TryGetExport(module, name, out var address) ? address : IntPtr.Zero, out var failure)
            ?? throw new NotSupportedException($"This Sprocket update changed the game's IL2CPP runtime ({failure}). " +
                "Mods stay off until the Sprocket Mod Loader is updated for it.");
        Logger.Instance.LogInformation("Sprocket / Unity 6000.3.21f1 runtime traced: Class::Init 0x{ClassInit:X}, " +
            "field default 0x{FieldDefault:X}, generic method 0x{GenericMethod:X}", targets.ClassInit, targets.FieldDefault, targets.GenericMethod);
        return targets;
    }

    // module: a mapped x64 GameAssembly; export: its exported function addresses (zero when absent).
    internal static Targets? Trace(IntPtr module, Func<string, IntPtr> export, out string failure)
    {
        failure = "";
        int pe = Marshal.ReadInt32(module, 0x3C);
        if (Marshal.ReadInt32(module, pe) != 0x4550 || Marshal.ReadInt16(module, pe + 24) != 0x20B)
        { failure = "not an x64 image"; return null; }
        // RUNTIME_FUNCTION entries give each non-leaf function's start and end.
        int table = Marshal.ReadInt32(module, pe + 24 + 112 + 3 * 8), tableSize = Marshal.ReadInt32(module, pe + 24 + 112 + 3 * 8 + 4);
        var ends = new Dictionary<int, int>(tableSize / 12);
        for (int i = 0; i < tableSize / 12; i++)
            ends.TryAdd(Marshal.ReadInt32(module, table + i * 12), Marshal.ReadInt32(module, table + i * 12 + 4));

        byte At(int rva) => Marshal.ReadByte(module, rva);
        int Displaced(int rva, int length) => rva + length + Marshal.ReadInt32(module, rva + length - 4);
        bool Bytes(int rva, string hex)
        {
            var expected = Convert.FromHexString(hex);
            for (int i = 0; i < expected.Length; i++) if (At(rva + i) != expected[i]) return false;
            return true;
        }
        int Size(int rva) => ends.TryGetValue(rva, out var end) ? end - rva : -1;
        int Export(string name) { var address = export(name); return address == IntPtr.Zero ? -1 : (int)(address.ToInt64() - module.ToInt64()); }
        // An exported thunk starts with a jump to its implementation.
        int Thunk(string name) { int rva = Export(name); return rva >= 0 && At(rva) == 0xE9 ? Displaced(rva, 5) : -1; }
        // Function starts reached by a call or jump with a 32-bit displacement. Scanning every offset also reads some
        // displacements out of other instructions; those rarely land on a function start, and the checks reject them.
        List<int> Callees(int rva)
        {
            var found = new List<int>();
            if (!ends.TryGetValue(rva, out var end)) return found;
            for (int at = rva; at + 5 <= end; at++)
            {
                int target = At(at) is 0xE8 or 0xE9 ? Displaced(at, 5)
                    : At(at) == 0x0F && (At(at + 1) & 0xF0) == 0x80 && at + 6 <= end ? Displaced(at, 6) : -1;
                if (ends.ContainsKey(target) && !found.Contains(target)) found.Add(target);
            }
            return found;
        }
        string missing = "";
        int One(string name, IEnumerable<int> candidates, int size, Func<int, bool> verified)
        {
            var matches = new List<int>();
            foreach (var rva in candidates) if (Size(rva) == size && verified(rva)) matches.Add(rva);
            if (matches.Count == 1) return matches[0];
            if (missing.Length == 0) missing = matches.Count == 0 ? $"{name} not found" : $"{name} is ambiguous";
            return -1;
        }

        int fieldCaller = Thunk("il2cpp_field_static_get_value"), virtualCaller = Thunk("il2cpp_object_get_virtual_method");
        // Class::Init tests its initialized flag at +0x135 (mono_class_instance_size -> Class::Init).
        int classInit = One("Class::Init", Callees(Export("mono_class_instance_size")), 103,
            rva => Bytes(rva, "40534883EC20488BD9" + "F6813501000002"));
        // Field::StaticGetValue -> GetDefaultFieldValue(field, out value).
        int fieldDefault = One("Field::StaticGetValue", new[] { fieldCaller }, 96, _ => true) < 0 ? -1
            : One("GetDefaultFieldValue", Callees(fieldCaller), 341, rva => Bytes(rva, "48895C2408"));
        // Object::GetVirtualMethod -> GetGenericVirtualMethod, which passes the 24-byte generic context in RCX ->
        // GenericMethod::GetMethod(const GenericMethod&).
        int context = One("Object::GetVirtualMethod", new[] { virtualCaller }, 239, _ => true) < 0 ? -1
            : One("GetGenericVirtualMethod", Callees(virtualCaller), 62,
                rva => Bytes(rva + 0x18, "488B424048894C24204C89442428488B481048894C2430488D4C2420"));
        int genericMethod = context < 0 ? -1 : One("GenericMethod::GetMethod", Callees(context), 2338, rva => Bytes(rva, "40555356574154"));
        failure = missing;
        return classInit < 0 || fieldDefault < 0 || genericMethod < 0 ? null : new Targets(classInit, fieldDefault, genericMethod);
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

    internal static int ClassInitRva => Current.ClassInit;
    // mono_class_instance_size -> Class::Init, checks initialized bit at +0x135.
    internal static IntPtr ClassInit => Address(Current.ClassInit, new byte[] { 0x40, 0x53, 0x48, 0x83, 0xEC, 0x20, 0x48, 0x8B, 0xD9 });
    // il2cpp_field_static_get_value -> Field::StaticGetValue -> GetDefaultFieldValue.
    internal static IntPtr FieldDefault => Address(Current.FieldDefault, new byte[] { 0x48, 0x89, 0x5C, 0x24, 0x08 });
    // Object::GetVirtualMethod -> GetGenericVirtualMethod -> GetMethod(GenericMethod&).
    internal static IntPtr GenericMethod => Address(Current.GenericMethod, new byte[] { 0x40, 0x55, 0x53, 0x56, 0x57, 0x41, 0x54 });
}
