// Modified 2026-09-23 for the unofficial Sprocket Unity 6000.3.21 profile; see LOCAL-CHANGES.md.
using System;
using System.Linq;
using System.Runtime.InteropServices;
using Il2CppInterop.Common;
using Il2CppInterop.Common.XrefScans;
using Il2CppInterop.Runtime.Runtime;
using Il2CppInterop.Runtime.Startup;
using Microsoft.Extensions.Logging;

namespace Il2CppInterop.Runtime.Injection.Hooks
{
    internal unsafe class SprocketGenericMethodHook : Hook<SprocketGenericMethodHook.MethodDelegate>
    {
        public override string TargetMethodName => "GenericMethod::GetMethod";
        public override MethodDelegate GetDetour() => Hook;

        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        internal delegate Il2CppMethodInfo* MethodDelegate(Il2CppGenericMethod* gmethod);

        private Il2CppMethodInfo* Hook(Il2CppGenericMethod* gmethod)
        {
            if (gmethod == null || gmethod->methodDefinition == null)
                return Original(gmethod);

            if (ClassInjector.InflatedMethodFromContextDictionary.TryGetValue((IntPtr)gmethod->methodDefinition, out var methods))
            {
                var instancePointer = gmethod->context.method_inst;
                if (methods.Item2.TryGetValue((IntPtr)instancePointer, out var inflatedMethodPointer))
                    return (Il2CppMethodInfo*)inflatedMethodPointer;

                var typeArguments = new Type[instancePointer->type_argc];
                for (var i = 0; i < instancePointer->type_argc; i++)
                    typeArguments[i] = ClassInjector.SystemTypeFromIl2CppType(instancePointer->type_argv[i]);
                var inflatedMethod = methods.Item1.MakeGenericMethod(typeArguments);
                Logger.Instance.LogTrace("Inflated method: {InflatedMethod}", inflatedMethod.Name);
                inflatedMethodPointer = (IntPtr)ClassInjector.ConvertMethodInfo(inflatedMethod,
                    UnityVersionHandler.Wrap(UnityVersionHandler.Wrap(gmethod->methodDefinition).Class));
                methods.Item2.Add((IntPtr)instancePointer, inflatedMethodPointer);

                return (Il2CppMethodInfo*)inflatedMethodPointer;
            }

            return Original(gmethod);
        }

        public override IntPtr FindTargetMethod() => SprocketUnity6Profile.GenericMethod;
    }
}
