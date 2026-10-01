using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using AsmResolver.DotNet;
using AsmResolver.DotNet.Code.Cil;
using AsmResolver.DotNet.Collections;
using AsmResolver.DotNet.Signatures;
using AsmResolver.PE.DotNet.Cil;
using Il2CppInterop.Generator.Extensions;
using Il2CppInterop.Generator.Passes;
using MAttributes = AsmResolver.PE.DotNet.Metadata.Tables.MethodAttributes;
using TAttributes = AsmResolver.PE.DotNet.Metadata.Tables.TypeAttributes;
using FAttributes = AsmResolver.PE.DotNet.Metadata.Tables.FieldAttributes;

var game = args.Length > 0 ? Path.GetFullPath(args[0]) : @"D:\Projects\SprocketInteropPatch\TestGame";
var output = args.Length > 1 ? Path.GetFullPath(args[1]) : Path.Combine(Path.GetTempPath(), "UnityUiCompatibilityTests-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(output);
var suite = new Suite(output);
suite.RealWrapper(Path.Combine(game, "BepInEx", "interop", "UnityEngine.CoreModule.dll"), "BepInEx");
suite.RealWrapper(Path.Combine(game, "MLLoader", "MelonLoader", "Il2CppAssemblies", "UnityEngine.CoreModule.dll"), "MelonLoader");
suite.NegativeCases();
suite.ExecuteFixture();
Console.WriteLine($"UNITY_UI_GENERATOR_TESTS_OK: {suite.Checks} checks; actual BepInEx and MelonLoader wrappers, serialized constructor, side order, allocation, preservation, idempotence, incomplete-type guards");
Console.WriteLine("Evidence: " + output);

sealed class Suite(string output)
{
    static readonly string[] Sides = ["left", "right", "top", "bottom"];
    static readonly MethodInfo Restore = typeof(Pass82RestoreUnityUiConstructors).GetMethod("RestoreRectOffset", BindingFlags.Static | BindingFlags.NonPublic)
        ?? throw new MissingMethodException("Generator pass does not expose the expected internal RestoreRectOffset helper.");
    public int Checks { get; private set; }
    void Check(bool condition, string message)
    {
        Checks++;
        if (!condition) throw new InvalidOperationException(message);
    }
    static bool Apply(TypeDefinition type, ModuleDefinition module) => (bool)Restore.Invoke(null, [type, module])!;
    static TypeDefinition Rect(ModuleDefinition module) => module.GetAllTypes().Single(t => t.FullName == "UnityEngine.RectOffset");
    static MethodDefinition? Four(TypeDefinition type) => type.Methods.SingleOrDefault(m => m.Name == ".ctor" && !m.IsStatic
        && m.Signature!.ParameterTypes.Count == 4 && m.Signature.ParameterTypes.All(p => p.FullName == "System.Int32"));
    static string Hash(string file) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file)));
    static string Operand(object? value) => value switch
    {
        null => "",
        Parameter p => $"argument:{p.Index}:{p.Name}:{p.ParameterType.FullName}",
        IMethodDescriptor m => m.FullName,
        IFieldDescriptor f => f.FullName,
        CilInstruction i => "branch:" + i.Offset,
        _ => value.ToString() ?? ""
    };
    static string Method(MethodDefinition method) => method.FullName + "|" + method.Attributes + "|" + method.ImplAttributes + "|"
        + string.Join(",", method.Parameters.Select(p => p.Index + ":" + p.Name + ":" + p.ParameterType.FullName)) + "|"
        + (method.CilMethodBody == null ? "no body" : string.Join(";", method.CilMethodBody.Instructions.Select(i => i.OpCode.Code + " " + Operand(i.Operand))));
    static string[] Snapshot(ModuleDefinition module, MethodDefinition? excluded = null) => module.GetAllTypes()
        .SelectMany(t => t.Methods).Where(m => m != excluded).Select(Method).ToArray();

    public void RealWrapper(string input, string name)
    {
        Check(File.Exists(input), name + " wrapper is missing: " + input);
        string originalHash = Hash(input);
        var module = ModuleDefinition.FromFile(input);
        var type = Rect(module);
        // Test the stripped real wrapper even if another test has already installed a repaired copy.
        if (Four(type) is { } existing)
        {
            Check(!Apply(type, module), name + " changed an existing overload.");
            type.Methods.Remove(existing);
        }
        var before = Snapshot(module);
        Check(Apply(type, module), name + " failed to restore its stripped overload.");
        var restored = Four(type)!;
        Check(restored != null, name + " restored no four-int constructor.");
        Constructor(type, restored!, name);
        Check(before.SequenceEqual(Snapshot(module, restored)), name + " modified existing method bodies or signatures.");
        int methodCount = type.Methods.Count;
        string[] after = Snapshot(module);
        Check(!Apply(type, module), name + " repeated restoration did not skip.");
        Check(type.Methods.Count == methodCount && after.SequenceEqual(Snapshot(module)), name + " repeated restoration modified metadata.");
        string file = Path.Combine(output, name + ".UnityEngine.CoreModule.dll");
        module.Write(file);
        var written = ModuleDefinition.FromFile(file);
        var writtenType = Rect(written);
        var writtenCtor = Four(writtenType)!;
        Constructor(writtenType, writtenCtor, name + " serialized");
        Check(before.SequenceEqual(Snapshot(written, writtenCtor)), name + " serialization changed existing methods.");
        Check(!Apply(writtenType, written), name + " serialized overload not recognized on repeat.");
        Check(Hash(input) == originalHash, name + " input file changed.");
        Console.WriteLine($"REAL_WRAPPER_OK: {name}; {before.Length} existing methods unchanged; source SHA256 {originalHash}");
    }

    void Constructor(TypeDefinition type, MethodDefinition method, string name)
    {
        Check(method.IsPublic && !method.IsStatic && method.IsSpecialName && method.IsRuntimeSpecialName, name + " constructor flags are wrong.");
        Check(method.Signature!.HasThis && method.Signature.ReturnType.FullName == "System.Void", name + " constructor signature is wrong.");
        Check(method.Parameters.Select(p => p.Name?.ToString()).SequenceEqual(Sides), name + " argument names/side order are wrong.");
        var body = method.CilMethodBody!.Instructions;
        Check(body.Count == 15, name + " constructor body has unexpected operations.");
        Check(body[0].OpCode.Code == CilCode.Ldarg_0 && body[1].OpCode.Code == CilCode.Call, name + " must allocate through the empty constructor first.");
        Check(body[1].Operand is IMethodDescriptor c && c.DeclaringType!.FullName == type.FullName && c.Name == ".ctor"
            && c.Signature!.ParameterTypes.Count == 0, name + " allocation call targets the wrong constructor.");
        for (int i = 0; i < Sides.Length; i++)
        {
            int offset = 2 + i * 3;
            Check(body[offset].OpCode.Code == CilCode.Ldarg_0, name + " setter receiver is wrong.");
            Check(body[offset + 1].OpCode.Code == CilCode.Ldarg && body[offset + 1].Operand is Parameter p && p.Index == i && p.MethodSignatureIndex == i + 1,
                name + " setter uses the wrong argument at " + Sides[i] + ": " + body[offset + 1].OpCode.Code + " " + Operand(body[offset + 1].Operand)
                + (body[offset + 1].Operand is Parameter actual ? " signature-index=" + actual.MethodSignatureIndex : ""));
            Check(body[offset + 2].OpCode.Code == CilCode.Call && body[offset + 2].Operand is IMethodDescriptor s
                && s.DeclaringType!.FullName == type.FullName && s.Name == "set_" + Sides[i]
                && s.Signature!.ParameterTypes.Count == 1 && s.Signature.ParameterTypes[0].FullName == "System.Int32",
                name + " setter target/side order is wrong at " + Sides[i]);
        }
        Check(body[^1].OpCode.Code == CilCode.Ret, name + " constructor must return normally.");
    }

    static ModuleDefinition Fixture()
    {
        var module = new ModuleDefinition("RectOffsetFixture");
        new AssemblyDefinition("RectOffsetFixture", new Version(1, 0)).Modules.Add(module);
        var baseType = new TypeDefinition("Il2CppSystem", "Object", TAttributes.Public | TAttributes.Class, module.CorLibTypeFactory.Object.Type);
        module.TopLevelTypes.Add(baseType);
        var baseCtor = InstanceMethod(module, baseType, ".ctor");
        baseCtor.CilMethodBody!.Instructions.Add(CilOpCodes.Ldarg_0);
        var clrCtor = module.DefaultImporter.ImportMethod(typeof(object).GetConstructor(Type.EmptyTypes)!);
        baseCtor.CilMethodBody.Instructions.Add(CilOpCodes.Call, clrCtor);
        baseCtor.CilMethodBody.Instructions.Add(CilOpCodes.Ret);
        var rect = new TypeDefinition("UnityEngine", "RectOffset", TAttributes.Public | TAttributes.Class, baseType);
        module.TopLevelTypes.Add(rect);
        var allocations = new FieldDefinition("allocations", FAttributes.Public, new FieldSignature(module.CorLibTypeFactory.Int32));
        rect.Fields.Add(allocations);
        var empty = InstanceMethod(module, rect, ".ctor");
        var body = empty.CilMethodBody!.Instructions;
        body.Add(CilOpCodes.Ldarg_0); body.Add(CilOpCodes.Call, baseCtor);
        body.Add(CilOpCodes.Ldarg_0); body.Add(CilOpCodes.Ldarg_0); body.Add(CilOpCodes.Ldfld, allocations);
        body.Add(CilOpCodes.Ldc_I4_1); body.Add(CilOpCodes.Add); body.Add(CilOpCodes.Stfld, allocations); body.Add(CilOpCodes.Ret);
        foreach (string side in Sides)
        {
            var field = new FieldDefinition(side, FAttributes.Public, new FieldSignature(module.CorLibTypeFactory.Int32));
            rect.Fields.Add(field);
            var setter = InstanceMethod(module, rect, "set_" + side, module.CorLibTypeFactory.Int32);
            body = setter.CilMethodBody!.Instructions;
            body.Add(CilOpCodes.Ldarg_0); body.Add(CilOpCodes.Ldarg_1); body.Add(CilOpCodes.Stfld, field); body.Add(CilOpCodes.Ret);
        }
        return module;
    }
    static MethodDefinition InstanceMethod(ModuleDefinition module, TypeDefinition type, string name, params TypeSignature[] parameters)
    {
        var method = new MethodDefinition(name, MAttributes.Public | MAttributes.HideBySig | MAttributes.SpecialName
            | (name == ".ctor" ? MAttributes.RuntimeSpecialName : 0), MethodSignature.CreateInstance(module.CorLibTypeFactory.Void, parameters));
        method.CilMethodBody = new CilMethodBody();
        type.Methods.Add(method);
        return method;
    }
    void Reject(string name, Action<ModuleDefinition, TypeDefinition> change)
    {
        var module = Fixture(); var type = Rect(module); change(module, type);
        var before = Snapshot(module); int count = type.Methods.Count;
        Check(!Apply(type, module), name + " should skip restoration.");
        Check(count == type.Methods.Count && before.SequenceEqual(Snapshot(module)), name + " changed methods despite skipping.");
    }
    public void NegativeCases()
    {
        Reject("wrong type", (_, t) => t.Name = "NotRectOffset");
        Reject("wrong base", (m, t) => t.BaseType = m.CorLibTypeFactory.Object.Type);
        Reject("no native empty constructor", (_, t) => t.Methods.Remove(t.Methods.Single(m => m.Name == ".ctor")));
        Reject("private native empty constructor", (_, t) => t.Methods.Single(m => m.Name == ".ctor").IsPublic = false);
        Reject("empty constructor without body", (_, t) => t.Methods.Single(m => m.Name == ".ctor").CilMethodBody = null);
        Reject("ambiguous empty constructors", (m, t) => InstanceMethod(m, t, ".ctor"));
        foreach (string side in Sides)
        {
            Reject("missing " + side, (_, t) => t.Methods.Remove(t.Methods.Single(m => m.Name == "set_" + side)));
            Reject("private " + side, (_, t) => t.Methods.Single(m => m.Name == "set_" + side).IsPublic = false);
            Reject("static " + side, (_, t) => t.Methods.Single(m => m.Name == "set_" + side).IsStatic = true);
            Reject("bodyless " + side, (_, t) => t.Methods.Single(m => m.Name == "set_" + side).CilMethodBody = null);
            Reject("wrong parameter " + side, (m, t) => t.Methods.Single(x => x.Name == "set_" + side).Signature!.ParameterTypes[0] = m.CorLibTypeFactory.Int64);
            Reject("ambiguous " + side, (m, t) => InstanceMethod(m, t, "set_" + side, m.CorLibTypeFactory.Int32));
        }
        var module = Fixture(); var type = Rect(module);
        var existing = InstanceMethod(module, type, ".ctor", Enumerable.Repeat<TypeSignature>(module.CorLibTypeFactory.Int32, 4).ToArray());
        existing.CilMethodBody!.Instructions.Add(CilOpCodes.Ret);
        var before = Snapshot(module);
        Check(!Apply(type, module) && before.SequenceEqual(Snapshot(module)), "existing game-provided overload must remain untouched.");
        Console.WriteLine("NEGATIVE_GUARDS_OK: existing, incomplete, ambiguous and incompatible types preserved");
    }
    public void ExecuteFixture()
    {
        var module = Fixture(); var type = Rect(module);
        Check(Apply(type, module), "managed execution fixture restoration failed.");
        Constructor(type, Four(type)!, "managed execution fixture");
        string file = Path.Combine(output, "RectOffsetFixture.dll"); module.Write(file);
        var context = new AssemblyLoadContext("RectOffset restored pass fixture", true);
        try
        {
            var runtime = context.LoadFromAssemblyPath(file).GetType("UnityEngine.RectOffset")!;
            foreach (int[] values in new[] { new[] { 24, 24, 24, 24 }, new[] { 16, 16, 0, 0 }, new[] { -1, 2, 5, 9 }, new[] { 0, 0, 0, 0 }, new[] { int.MinValue, int.MaxValue, -200, 400 } })
            {
                var instance = Activator.CreateInstance(runtime, values.Select(v => (object)v).ToArray())!;
                Check((int)runtime.GetField("allocations")!.GetValue(instance)! == 1, "native allocation wrapper must execute exactly once.");
                for (int i = 0; i < Sides.Length; i++)
                    Check((int)runtime.GetField(Sides[i])!.GetValue(instance)! == values[i], "restored constructor executed wrong side " + Sides[i]);
            }
        }
        finally { context.Unload(); }
        Console.WriteLine("EXECUTED_CONSTRUCTOR_OK: allocation once; padding order and negative/zero/extreme values preserved");
    }
}
