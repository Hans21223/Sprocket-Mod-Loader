using System.Runtime.InteropServices;
using Il2CppInterop.HarmonySupport;
using Il2CppInterop.Runtime.Injection;

static class Program
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int Unary(int value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate long Wrong(long value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void ByRef(ref int value);
    static int checks;
    static void Check(bool value, string message) { if (!value) throw new Exception(message); checks++; }

    static void Main()
    {
        int nativeCalls = 0, aCalls = 0, bCalls = 0;
        Unary original = value => { nativeCalls++; return value + 1; };
        FakeDetour physical = null;
        var site = new SprocketNativeHookChain(typeof(Unary), relay => physical = new FakeDetour(original, relay));
        Unary invoke = (Unary)physical.Relay;
        Check(invoke(3) == 4, "Empty relay must preserve original");
        IntPtr nextA = 0, nextB = 0;
        object a = new(), b = new();
        site.Install(a, (Unary)(value => { aCalls++; return Marshal.GetDelegateForFunctionPointer<Unary>(nextA)(value) + 10; }), p => nextA = p);
        site.Install(b, (Unary)(value => { bCalls++; return Marshal.GetDelegateForFunctionPointer<Unary>(nextB)(value) * 2; }), p => nextB = p);
        Check(invoke(3) == 28, "Both aliases must run and reach the native original");
        Check(nativeCalls == 2 && aCalls == 1 && bCalls == 1, "No recursion or duplicate calls");
        site.Install(a, (Unary)(value => { aCalls++; return Marshal.GetDelegateForFunctionPointer<Unary>(nextA)(value) + 100; }), p => nextA = p);
        Check(invoke(3) == 208, "Rebuilding older alias must preserve newer alias");
        site.Install(b, (Unary)(value => Marshal.GetDelegateForFunctionPointer<Unary>(nextB)(value)), p => nextB = p);
        Check(invoke(3) == 104, "Removing B's Harmony patches must preserve A");
        site.Install(a, (Unary)(value => Marshal.GetDelegateForFunctionPointer<Unary>(nextA)(value)), p => nextA = p);
        Check(invoke(3) == 4, "Removing all patches must preserve native behavior");
        bool rejected = false;
        try { site.Install(new object(), (Wrong)(value => value), _ => throw new Exception("Must not mutate chain")); }
        catch (NotSupportedException) { rejected = true; }
        Check(rejected && invoke(3) == 4, "Wrong ABI must be rejected without breaking the chain");
        Check(physical.Applies == 1 && physical.Disposes == 0, "One physical detour, no callback detours");
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        Check(invoke(3) == 4, "Delegate roots must survive a full GC");

        FakeDetour refPhysical = null;
        ByRef refOriginal = (ref int value) => value += 2;
        var refSite = new SprocketNativeHookChain(typeof(ByRef), relay => refPhysical = new FakeDetour(refOriginal, relay));
        IntPtr refNext = 0;
        refSite.Install(new object(), (ByRef)((ref int value) => { Marshal.GetDelegateForFunctionPointer<ByRef>(refNext)(ref value); value *= 5; }), p => refNext = p);
        int number = 4;
        ((ByRef)refPhysical.Relay)(ref number);
        Check(number == 30, "Reference arguments must be forwarded correctly");

        // Patching refreshes one owner; it must not grow the native detour stack.
        for (int i = 0; i < 100; i++)
        {
            int extra = i;
            site.Install(a, (Unary)(value => Marshal.GetDelegateForFunctionPointer<Unary>(nextA)(value) + extra), p => nextA = p);
            Check(invoke(3) == 4 + extra, "Repeated patch refresh changed chain order");
        }
        Check(physical.Applies == 1, "Refresh must not reapply physical hooks");
        Console.WriteLine($"NATIVE_CHAIN_TESTS_OK: {checks} checks; alias chaining, refresh/unpatch forwarding, GC, ABI rejection and byref arguments");
        TraceGameBuilds();
    }

    // Hook targets traced from real game builds listed in SPROCKET_GAME_ASSEMBLIES (';'-separated; never distributed).
    static readonly Dictionary<string, SprocketUnity6Profile.Targets> Traced = new()
    {
        ["18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56"] = new(0x4E4160, 0x4945E0, 0x4CF780), // 0.2.55.5
        ["ADB36B5F04662BE0D40C6E548C797394659A9C0D4B009E3C0E718833ABF90B3A"] = new(0x4E46B0, 0x494B30, 0x4CFCD0), // 0.2.56.0
        ["FCF745C40A02406A4D757A859A8FFCEF67D82835C98BE557312861E843B04FFC"] = new(0x4E4790, 0x494C10, 0x4CFDB0), // 0.2.56.1
    };
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr LoadLibraryExW(string path, IntPtr file, int flags);
    [DllImport("kernel32")] static extern bool FreeLibrary(IntPtr module);

    static void TraceGameBuilds()
    {
        var paths = (Environment.GetEnvironmentVariable("SPROCKET_GAME_ASSEMBLIES") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries);
        foreach (var path in paths)
        {
            var copy = Path.Combine(Path.GetTempPath(), $"GameAssembly-trace-{Guid.NewGuid():N}.dll");
            File.Copy(path, copy);
            var module = LoadLibraryExW(copy, IntPtr.Zero, 1); // DONT_RESOLVE_DLL_REFERENCES: mapped, never run
            try
            {
                Check(module != IntPtr.Zero, $"{path}: could not be mapped");
                IntPtr Export(string name) => NativeLibrary.TryGetExport(module, name, out var address) ? address : IntPtr.Zero;
                var targets = SprocketUnity6Profile.Trace(module, Export, out var failure);
                Check(targets != null, $"{path}: {failure}");
                var hash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(path)));
                if (Traced.TryGetValue(hash, out var expected)) Check(targets == expected, $"{path}: traced {targets}, verified {expected}");
                Check(SprocketUnity6Profile.Trace(module, name => name == "mono_class_instance_size" ? IntPtr.Zero : Export(name), out failure) == null
                    && failure == "Class::Init not found", "A broken call path must be refused");
                Console.WriteLine($"GAME_TRACE_OK: {path} -> {targets}{(Traced.ContainsKey(hash) ? " (matches the verified trace)" : " (new build)")}");
            }
            finally { if (module != IntPtr.Zero) FreeLibrary(module); File.Delete(copy); }
        }
        if (paths.Length == 0) Console.WriteLine("GAME_TRACE_SKIPPED: set SPROCKET_GAME_ASSEMBLIES to GameAssembly.dll paths");
    }

    sealed class FakeDetour : IDetour
    {
        public readonly Delegate Original, Relay;
        public int Applies, Disposes;
        public FakeDetour(Delegate original, Delegate relay) { Original = original; Relay = relay; }
        public IntPtr Target => OriginalTrampoline;
        public IntPtr Detour => Marshal.GetFunctionPointerForDelegate(Relay);
        public IntPtr OriginalTrampoline => Marshal.GetFunctionPointerForDelegate(Original);
        public void Apply() => Applies++;
        public void Dispose() => Disposes++;
        public T GenerateTrampoline<T>() where T : Delegate => (T)Original;
    }
}
