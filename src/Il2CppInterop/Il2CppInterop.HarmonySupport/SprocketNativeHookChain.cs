// Modified 2026-09-24: one physical detour per Sprocket native method, including MLLoader aliases.
using System.Reflection.Emit;
using System.Runtime.InteropServices;
using Il2CppInterop.Runtime.Injection;

namespace Il2CppInterop.HarmonySupport;

/// <summary>
/// Different generated wrappers can name the same native method. Give each wrapper
/// its own managed patch body, but never detour another wrapper's reverse-P/Invoke
/// thunk. Each body calls its predecessor through its copied native MethodInfo.
/// Sites and retired delegates deliberately live for the process lifetime: native
/// callers can still be inside an older body during a Harmony patch refresh.
/// </summary>
internal sealed class SprocketNativeHookChain
{
    private sealed class Entry
    {
        internal object Owner;
        internal IntPtr Pointer;
        internal Action<IntPtr> SetOriginal;
    }

    private readonly object gate = new();
    private readonly List<Entry> entries = new();
    private readonly List<Delegate> roots = new();
    private readonly Type returnType;
    private readonly Type[] parameterTypes;
    private readonly IntPtr headSlot;
    private readonly IDetour detour;

    internal SprocketNativeHookChain(Type delegateType, Func<Delegate, IDetour> createDetour)
    {
        var invoke = delegateType.GetMethod("Invoke");
        returnType = invoke.ReturnType;
        parameterTypes = invoke.GetParameters().Select(p => p.ParameterType).ToArray();
        headSlot = Marshal.AllocHGlobal(IntPtr.Size);
        Marshal.WriteIntPtr(headSlot, IntPtr.Zero);

        // Stable native entry point. The slot changes when a logical patch is
        // installed/rebuilt; the game's machine code is patched only once.
        var relay = new DynamicMethod("SprocketNativeHookChain_Relay", returnType, parameterTypes,
            typeof(SprocketNativeHookChain), true);
        var il = relay.GetILGenerator();
        for (var i = 0; i < parameterTypes.Length; i++) il.Emit(OpCodes.Ldarg, i);
        il.Emit(OpCodes.Ldc_I8, headSlot.ToInt64());
        il.Emit(OpCodes.Conv_I);
        il.Emit(OpCodes.Ldind_I);
        il.EmitCalli(OpCodes.Calli, CallingConvention.Cdecl, returnType, parameterTypes);
        il.Emit(OpCodes.Ret);
        var relayDelegate = relay.CreateDelegate(delegateType);
        roots.Add(relayDelegate);
        detour = createDetour(relayDelegate);
        Marshal.WriteIntPtr(headSlot, detour.OriginalTrampoline);
        detour.Apply();
    }

    internal void Install(object owner, Delegate target, Action<IntPtr> setOriginal)
    {
        lock (gate)
        {
            var invoke = target.GetType().GetMethod("Invoke");
            if (invoke.ReturnType != returnType ||
                !invoke.GetParameters().Select(p => p.ParameterType).SequenceEqual(parameterTypes))
                throw new NotSupportedException("Native aliases have incompatible signatures; refusing to chain their hooks.");

            var pointer = Marshal.GetFunctionPointerForDelegate(target);
            var entry = entries.Find(e => ReferenceEquals(e.Owner, owner));
            if (entry == null)
            {
                entry = new Entry { Owner = owner };
                entries.Add(entry);
            }
            roots.Add(target);
            entry.Pointer = pointer;
            entry.SetOriginal = setOriginal;

            // Oldest wrapper calls the real native trampoline. Newer wrappers
            // call the older wrapper, preserving both sets of Harmony patches.
            var next = detour.OriginalTrampoline;
            foreach (var item in entries)
            {
                item.SetOriginal(next);
                next = item.Pointer;
            }
            Thread.MemoryBarrier();
            Marshal.WriteIntPtr(headSlot, next);
        }
    }
}
