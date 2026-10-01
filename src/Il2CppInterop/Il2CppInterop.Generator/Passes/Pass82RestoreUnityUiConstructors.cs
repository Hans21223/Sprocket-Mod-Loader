using AsmResolver.DotNet;
using AsmResolver.DotNet.Signatures;
using AsmResolver.PE.DotNet.Metadata.Tables;
using Il2CppInterop.Common;
using Il2CppInterop.Generator.Contexts;
using Il2CppInterop.Generator.Extensions;
using Il2CppInterop.Generator.Utils;
using Microsoft.Extensions.Logging;

namespace Il2CppInterop.Generator.Passes;

/// <summary>
/// Restores a managed convenience constructor stripped from Unity's native metadata.
/// Constructor unstripping is intentionally disabled by the general unstrip pass,
/// so reconstruct this small, known body using the existing native allocation and
/// property wrappers. It does not require a guessed native constructor address.
/// </summary>
public static class Pass82RestoreUnityUiConstructors
{
    public static void DoPass(RewriteGlobalContext context)
    {
        var assembly = context.TryGetAssemblyByName("UnityEngine.CoreModule");
        var type = assembly?.TryGetTypeByName("UnityEngine.RectOffset");
        if (type?.OriginalType == null || assembly == null) return;

        // Only the native-backed RectOffset layout with an owned pointer and
        // source-style reference can safely use its parameterless constructor.
        var original = type.OriginalType;
        if (!original.Fields.Any(f => f.Name == "m_Ptr" && !f.IsStatic &&
                                      f.Signature?.FieldType.FullName == "System.IntPtr") ||
            !original.Fields.Any(f => f.Name == "m_SourceStyle" && !f.IsStatic &&
                                      f.Signature?.FieldType.FullName == "System.Object")) return;

        if (RestoreRectOffset(type.NewType, assembly.Imports.Module))
            Logger.Instance.LogInformation("Restored UnityEngine.RectOffset(int, int, int, int) managed constructor");
    }

    internal static bool RestoreRectOffset(TypeDefinition type, ModuleDefinition module)
    {
        if (type.FullName != "UnityEngine.RectOffset" || type.IsValueType ||
            type.BaseType?.FullName != "Il2CppSystem.Object") return false;

        static bool IsInstanceVoid(MethodDefinition method) =>
            !method.IsStatic && method.Signature?.HasThis == true &&
            method.Signature.ReturnType.FullName == "System.Void";

        // Leave any already restored or game-provided overload unchanged.
        if (type.Methods.Any(m => m.Name == ".ctor" && IsInstanceVoid(m) &&
                                  m.Signature!.ParameterTypes.Count == 4 &&
                                  m.Signature.ParameterTypes.All(p => p.FullName == "System.Int32"))) return false;

        var defaultCtors = type.Methods.Where(m => m.Name == ".ctor" &&
            m.IsPublic && IsInstanceVoid(m) && m.Signature!.ParameterTypes.Count == 0 &&
            m.CilMethodBody != null).Take(2).ToArray();
        if (defaultCtors.Length != 1) return false;
        var defaultCtor = defaultCtors[0];

        string[] names = ["left", "right", "top", "bottom"];
        var setters = new MethodDefinition[4];
        for (var i = 0; i < names.Length; i++)
        {
            var candidates = type.Methods.Where(m => m.Name == "set_" + names[i] &&
                m.IsPublic && IsInstanceVoid(m) && m.Signature!.ParameterTypes.Count == 1 &&
                m.Signature.ParameterTypes[0].FullName == "System.Int32" && m.CilMethodBody != null)
                .Take(2).ToArray();
            if (candidates.Length != 1) return false;
            setters[i] = candidates[0];
        }

        var constructor = new MethodDefinition(".ctor",
            MethodAttributes.Public | MethodAttributes.SpecialName |
            MethodAttributes.RuntimeSpecialName | MethodAttributes.HideBySig,
            MethodSignature.CreateInstance(module.Void()));
        foreach (var name in names) constructor.AddParameter(module.Int(), name);
        constructor.CilMethodBody = new();
        var body = constructor.CilMethodBody.Instructions;
        body.Add(OpCodes.Ldarg_0);
        body.Add(OpCodes.Call, defaultCtor);
        for (var i = 0; i < names.Length; i++)
        {
            body.Add(OpCodes.Ldarg_0);
            body.Add(OpCodes.Ldarg, constructor.Parameters[i]);
            body.Add(OpCodes.Call, setters[i]);
        }
        body.Add(OpCodes.Ret);
        type.Methods.Add(constructor);
        return true;
    }
}
