using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Reflection;
using System.Runtime.Loader;
using Attributes = Mono.Cecil.MethodAttributes;

if (args.Length == 2 && args[0] == "verify")
{
    using var assembly = AssemblyDefinition.ReadAssembly(args[1]);
    var type = Repair.Type(assembly);
    if (Repair.Constructor(type, 4) == null) throw new InvalidOperationException("RectOffset(Int32,Int32,Int32,Int32) is missing.");
    Console.WriteLine("RECTOFFSET_OVERLOAD_PRESENT: " + args[1]);
}
else if (args.Length == 3 && args[0] == "apply") Repair.Apply(args[1], args[2]);
else if (args.Length == 5 && args[0] == "remap") TokenMapRepair.Apply(args[1], args[2], args[3], args[4]);
else if (args.Length == 2 && args[0] == "self-test") Repair.Test(args[1]);
else throw new ArgumentException("Usage: apply <input.dll> <output.dll> | remap <old.dll> <new.dll> <old.db> <new.db> | verify <file.dll> | self-test <output-directory>");

static class Repair
{
    internal static TypeDefinition Type(AssemblyDefinition assembly)
    {
        if (assembly.Name.Name != "UnityEngine.CoreModule" || assembly.Name.HasPublicKey)
            throw new InvalidOperationException("Only an unsigned UnityEngine.CoreModule wrapper is supported.");
        return assembly.MainModule.Types.Single(t => t.FullName == "UnityEngine.RectOffset");
    }
    internal static MethodDefinition? Constructor(TypeDefinition type, int count) => type.Methods.SingleOrDefault(m =>
        m.IsConstructor && !m.IsStatic && m.IsPublic && m.Parameters.Count == count
        && m.Parameters.All(p => p.ParameterType.FullName == "System.Int32"));

    static void Add(AssemblyDefinition assembly)
    {
        var type = Type(assembly);
        if (Constructor(type, 4) != null) return;
        var empty = Constructor(type, 0) ?? throw new InvalidOperationException("RectOffset's native empty constructor is missing.");
        if (!empty.HasBody) throw new InvalidOperationException("RectOffset's constructor has no managed wrapper body.");
        var names = new[] { "left", "right", "top", "bottom" };
        var setters = names.Select(name => type.Methods.SingleOrDefault(m => m.Name == "set_" + name && m.IsPublic && !m.IsStatic
            && m.HasBody && m.Parameters.Count == 1 && m.Parameters[0].ParameterType.FullName == "System.Int32" && m.ReturnType.FullName == "System.Void")
            ?? throw new InvalidOperationException("RectOffset setter missing: " + name)).ToArray();
        var method = new MethodDefinition(".ctor", Attributes.Public | Attributes.HideBySig | Attributes.SpecialName | Attributes.RTSpecialName,
            assembly.MainModule.TypeSystem.Void);
        foreach (string name in names) method.Parameters.Add(new ParameterDefinition(name, Mono.Cecil.ParameterAttributes.None, assembly.MainModule.TypeSystem.Int32));
        type.Methods.Add(method);
        var il = method.Body.GetILProcessor();
        il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Call, empty);
        for (int i = 0; i < setters.Length; i++)
        {
            il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Ldarg, method.Parameters[i]); il.Emit(OpCodes.Call, setters[i]);
        }
        il.Emit(OpCodes.Ret);
    }

    internal static void Apply(string input, string output, bool fixture = false)
    {
        input = Path.GetFullPath(input); output = Path.GetFullPath(output);
        if (string.Equals(input, output, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("Use a separate output file; installation must preserve a backup.");
        using var assembly = AssemblyDefinition.ReadAssembly(input);
        if (!fixture)
        {
            var type = Type(assembly);
            if (type.BaseType?.FullName != "Il2CppSystem.Object" ||
                !new[] { "NativeFieldInfoPtr_m_Ptr", "NativeFieldInfoPtr_m_SourceStyle" }.All(name =>
                    type.Fields.Any(f => f.Name == name && f.IsStatic && f.FieldType.FullName == "System.IntPtr")))
                throw new InvalidOperationException("Only a generated, native-backed RectOffset wrapper is supported.");
        }
        if (Constructor(Type(assembly), 4) != null)
        {
            File.Copy(input, output, true);
            Console.WriteLine("RECTOFFSET_ALREADY_COMPATIBLE: unchanged");
            return;
        }
        var before = Snapshot(assembly);
        Add(assembly);
        assembly.Write(output);
        using var written = AssemblyDefinition.ReadAssembly(output);
        var after = Snapshot(written);
        foreach (var old in before)
            if (!after.TryGetValue(old.Key, out var value) || value != old.Value)
                throw new InvalidOperationException("An existing wrapper method changed: " + old.Key);
        if (after.Count != before.Count + 1 || Constructor(Type(written), 4) == null)
            throw new InvalidOperationException("Wrapper repair did not add exactly one constructor.");
        Console.WriteLine("RECTOFFSET_REPAIRED: native empty constructor + four existing setters; " + before.Count + " existing methods preserved");
    }
    static Dictionary<string, string> Snapshot(AssemblyDefinition assembly)
    {
        IEnumerable<TypeDefinition> Types(TypeDefinition type) => new[] { type }.Concat(type.NestedTypes.SelectMany(Types));
        // Unity's unstripped wrappers can contain duplicate signatures. Match
        // each existing declaration by its unchanged order within that signature.
        return assembly.MainModule.Types.SelectMany(Types).SelectMany(t => t.Methods)
            .GroupBy(m => m.FullName, StringComparer.Ordinal)
            .SelectMany(group => group.Select((method, index) => new { Key = group.Key + "#" + index, Method = method }))
            .ToDictionary(entry => entry.Key, entry => entry.Method.Attributes + "|" + entry.Method.ImplAttributes + "|" +
                (entry.Method.HasBody ? string.Join(";", entry.Method.Body.Instructions.Select(i => i.OpCode + " " + i.Operand)) : "no body"));
    }
    internal static void Test(string directory)
    {
        Directory.CreateDirectory(directory);
        string original = Path.Combine(directory, "fixture-original.dll"), repaired = Path.Combine(directory, "fixture-repaired.dll"), again = Path.Combine(directory, "fixture-again.dll");
        using (var assembly = AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("UnityEngine.CoreModule", new Version(1, 0)), "fixture", ModuleKind.Dll))
        {
            var module = assembly.MainModule;
            var type = new TypeDefinition("UnityEngine", "RectOffset", Mono.Cecil.TypeAttributes.Public | Mono.Cecil.TypeAttributes.Class, module.TypeSystem.Object);
            module.Types.Add(type);
            var created = new FieldDefinition("created", Mono.Cecil.FieldAttributes.Public, module.TypeSystem.Int32); type.Fields.Add(created);
            var empty = new MethodDefinition(".ctor", Attributes.Public | Attributes.SpecialName | Attributes.RTSpecialName | Attributes.HideBySig, module.TypeSystem.Void);
            type.Methods.Add(empty); var body = empty.Body.GetILProcessor();
            body.Emit(OpCodes.Ldarg_0); body.Emit(OpCodes.Call, module.ImportReference(typeof(object).GetConstructor(System.Type.EmptyTypes)!));
            body.Emit(OpCodes.Ldarg_0); body.Emit(OpCodes.Ldc_I4_1); body.Emit(OpCodes.Stfld, created); body.Emit(OpCodes.Ret);
            foreach (string name in new[] { "left", "right", "top", "bottom" })
            {
                var field = new FieldDefinition(name, Mono.Cecil.FieldAttributes.Public, module.TypeSystem.Int32); type.Fields.Add(field);
                var setter = new MethodDefinition("set_" + name, Attributes.Public | Attributes.SpecialName | Attributes.HideBySig, module.TypeSystem.Void);
                setter.Parameters.Add(new ParameterDefinition(module.TypeSystem.Int32)); type.Methods.Add(setter);
                var il = setter.Body.GetILProcessor(); il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Ldarg_1); il.Emit(OpCodes.Stfld, field); il.Emit(OpCodes.Ret);
            }
            assembly.Write(original);
        }
        Apply(original, repaired, fixture: true); Apply(repaired, again, fixture: true);
        if (!File.ReadAllBytes(repaired).SequenceEqual(File.ReadAllBytes(again))) throw new Exception("Repair must be byte-identical when repeated.");
        var context = new AssemblyLoadContext("RectOffset fixture", true);
        try
        {
            var type = context.LoadFromAssemblyPath(Path.GetFullPath(repaired)).GetType("UnityEngine.RectOffset")!;
            foreach (var values in new[] { new[] { 24, 24, 24, 24 }, new[] { 16, 16, 0, 0 }, new[] { -1, 2, 5, 9 }, new[] { 0, 0, 0, 0 } })
            {
                var instance = Activator.CreateInstance(type, values.Select(v => (object)v).ToArray())!;
                if ((int)type.GetField("created")!.GetValue(instance)! != 1) throw new Exception("Native allocation must occur exactly once.");
                int i = 0;
                foreach (string name in new[] { "left", "right", "top", "bottom" })
                    if ((int)type.GetField(name)!.GetValue(instance)! != values[i++]) throw new Exception("Padding side order is wrong.");
            }
        }
        finally { context.Unload(); }
        Console.WriteLine("RECTOFFSET_FIXTURE_TESTS_OK: constructor allocation, all four sides, negative/zero padding and idempotence");
        TokenMapRepair.Test(directory);
    }
}
