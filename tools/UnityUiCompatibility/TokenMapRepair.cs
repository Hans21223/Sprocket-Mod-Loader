using System.Buffers.Binary;
using System.Reflection;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

/// <summary>
/// Remaps the companion Il2CppInterop method-address database after a managed
/// wrapper is rewritten. Native RVAs and records belonging to other assemblies
/// are preserved byte-for-byte. Always use the original, unrepaired database as
/// input, together with its original wrapper, and install both repaired files.
/// </summary>
internal static class TokenMapRepair
{
    const int Magic = 0x4D544D55, Version = 1, HeaderLength = 20;
    sealed record Map(byte[] Bytes, int DataOffset, int Methods, int CoreAssembly);

    internal static int Apply(string originalWrapper, string repairedWrapper, string originalDatabase, string outputDatabase)
    {
        originalDatabase = Path.GetFullPath(originalDatabase);
        outputDatabase = Path.GetFullPath(outputDatabase);
        if (string.Equals(originalDatabase, outputDatabase, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Use a separate database output file; preserve the original map for rollback.");

        using var beforeAssembly = AssemblyDefinition.ReadAssembly(originalWrapper);
        using var afterAssembly = AssemblyDefinition.ReadAssembly(repairedWrapper);
        if (beforeAssembly.Name.Name != "UnityEngine.CoreModule" ||
            beforeAssembly.Name.FullName != afterAssembly.Name.FullName)
            throw new InvalidOperationException("The original and repaired CoreModule wrappers must have the same assembly identity.");

        var beforeMethods = Methods(beforeAssembly);
        var afterMethods = Methods(afterAssembly);
        var replacements = new Dictionary<int, int>();
        foreach (var pair in beforeMethods)
        {
            if (!afterMethods.TryGetValue(pair.Key, out var after))
                throw new InvalidOperationException("An original wrapper method disappeared: " + pair.Key);
            if (pair.Value.FullName != after.FullName || pair.Value.Attributes != after.Attributes ||
                pair.Value.ImplAttributes != after.ImplAttributes)
                throw new InvalidOperationException("An original wrapper method identity changed: " + pair.Key);
            replacements.Add(pair.Value.MetadataToken.ToInt32(), after.MetadataToken.ToInt32());
        }

        var input = Read(originalDatabase);
        var output = (byte[])input.Bytes.Clone();
        int changed = 0, coreEntries = 0;
        for (int i = 0; i < input.Methods; i++)
        {
            int offset = checked(input.DataOffset + input.Methods * 8 + i * 8);
            int assemblyIndex = BinaryPrimitives.ReadInt32LittleEndian(input.Bytes.AsSpan(offset + 4, 4));
            if (assemblyIndex != input.CoreAssembly) continue;
            coreEntries++;
            int oldToken = BinaryPrimitives.ReadInt32LittleEndian(input.Bytes.AsSpan(offset, 4));
            if (!replacements.TryGetValue(oldToken, out int newToken))
                throw new InvalidOperationException("CoreModule database token does not resolve in its original wrapper: " + oldToken.ToString("X8"));
            if (oldToken == newToken) continue;
            BinaryPrimitives.WriteInt32LittleEndian(output.AsSpan(offset, 4), newToken);
            changed++;
        }
        if (coreEntries == 0) throw new InvalidOperationException("The database has no CoreModule method entries.");

        File.WriteAllBytes(outputDatabase, output);
        var written = Read(outputDatabase);
        if (!written.Bytes.SequenceEqual(output)) throw new IOException("The repaired token database was not written correctly.");
        Console.WriteLine("RECTOFFSET_TOKEN_MAP_REPAIRED: " + changed + " changed tokens; " + coreEntries + " CoreModule entries; native addresses and other assemblies preserved");
        return changed;
    }

    static Dictionary<string, MethodDefinition> Methods(AssemblyDefinition assembly)
    {
        IEnumerable<TypeDefinition> Nested(TypeDefinition type) => new[] { type }.Concat(type.NestedTypes.SelectMany(Nested));
        var result = new Dictionary<string, MethodDefinition>(StringComparer.Ordinal);
        foreach (var type in assembly.MainModule.Types.SelectMany(Nested))
        {
            // Existing wrappers can contain two unstripped methods with the same
            // display signature. Cecil preserves their declaration order, so use
            // the per-type duplicate ordinal instead of discarding either token.
            var ordinals = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (var method in type.Methods)
            {
                ordinals.TryGetValue(method.FullName, out int ordinal);
                ordinals[method.FullName] = ordinal + 1;
                result.Add(method.FullName + "#" + ordinal, method);
            }
        }
        return result;
    }

    static Map Read(string path)
    {
        byte[] bytes = File.ReadAllBytes(path);
        if (bytes.Length < HeaderLength) throw new InvalidDataException("Token database header is truncated.");
        using var stream = new MemoryStream(bytes, false);
        using var reader = new BinaryReader(stream, Encoding.UTF8, false);
        if (reader.ReadInt32() != Magic || reader.ReadInt32() != Version)
            throw new InvalidDataException("Unsupported Il2CppInterop token database format.");
        int assemblies = reader.ReadInt32(), methods = reader.ReadInt32(), dataOffset = reader.ReadInt32();
        if (assemblies <= 0 || assemblies > 100000 || methods <= 0 || dataOffset < HeaderLength ||
            dataOffset > bytes.Length || (long)dataOffset + (long)methods * 16 != bytes.Length)
            throw new InvalidDataException("Invalid token database counts or offsets.");
        int core = -1;
        for (int i = 0; i < assemblies; i++)
        {
            string name = reader.ReadString();
            if (stream.Position > dataOffset) throw new InvalidDataException("Token database assembly names overlap method data.");
            if (new AssemblyName(name).Name != "UnityEngine.CoreModule") continue;
            if (core >= 0) throw new InvalidDataException("Token database contains multiple CoreModule assemblies.");
            core = i;
        }
        if (stream.Position != dataOffset || core < 0)
            throw new InvalidDataException("Token database assembly table is invalid or CoreModule is absent.");
        for (int i = 0; i < methods; i++)
        {
            int offset = checked(dataOffset + methods * 8 + i * 8);
            int token = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(offset, 4));
            int assemblyIndex = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(offset + 4, 4));
            if ((token & unchecked((int)0xFF000000)) != 0x06000000 || (token & 0x00FFFFFF) == 0 ||
                assemblyIndex < 0 || assemblyIndex >= assemblies)
                throw new InvalidDataException("Invalid method token or assembly index in token database.");
        }
        return new Map(bytes, dataOffset, methods, core);
    }

    internal static void Test(string directory)
    {
        Directory.CreateDirectory(directory);
        string original = Path.Combine(directory, "map-wrapper-original.dll"), repaired = Path.Combine(directory, "map-wrapper-repaired.dll");
        string input = Path.Combine(directory, "map-original.db"), output = Path.Combine(directory, "map-repaired.db"), unchanged = Path.Combine(directory, "map-unchanged.db");
        using (var assembly = AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("UnityEngine.CoreModule", new Version(1, 0)), "map fixture", ModuleKind.Dll))
        {
            var module = assembly.MainModule;
            var first = new TypeDefinition("UnityEngine", "RectOffset", Mono.Cecil.TypeAttributes.Public | Mono.Cecil.TypeAttributes.Class, module.TypeSystem.Object);
            var last = new TypeDefinition("UnityEngine", "TrailingType", Mono.Cecil.TypeAttributes.Public | Mono.Cecil.TypeAttributes.Class, module.TypeSystem.Object);
            module.Types.Add(first); module.Types.Add(last);
            foreach (var type in new[] { first, last })
            {
                var method = new MethodDefinition("Existing", Mono.Cecil.MethodAttributes.Public | Mono.Cecil.MethodAttributes.Static, module.TypeSystem.Void);
                method.Body.GetILProcessor().Emit(OpCodes.Ret); type.Methods.Add(method);
                if (type == first)
                {
                    var duplicate = new MethodDefinition("Existing", method.Attributes, module.TypeSystem.Void);
                    duplicate.Body.GetILProcessor().Emit(OpCodes.Nop);
                    duplicate.Body.GetILProcessor().Emit(OpCodes.Ret);
                    type.Methods.Add(duplicate);
                }
            }
            assembly.Write(original);
        }
        using (var assembly = AssemblyDefinition.ReadAssembly(original))
        {
            var method = new MethodDefinition("Added", Mono.Cecil.MethodAttributes.Public | Mono.Cecil.MethodAttributes.Static, assembly.MainModule.TypeSystem.Void);
            method.Body.GetILProcessor().Emit(OpCodes.Ret); assembly.MainModule.Types.Single(t => t.Name == "RectOffset").Methods.Add(method);
            assembly.Write(repaired);
        }
        int[] tokens;
        string coreName;
        using (var assembly = AssemblyDefinition.ReadAssembly(original))
        {
            tokens = Methods(assembly).Values.Select(m => m.MetadataToken.ToInt32()).ToArray();
            coreName = assembly.Name.FullName;
        }
        using (var stream = File.Create(input))
        using (var writer = new BinaryWriter(stream, Encoding.UTF8, false))
        {
            writer.Write(Magic); writer.Write(Version); writer.Write(2); writer.Write(4); writer.Write(0);
            writer.Write(coreName); writer.Write("AnotherAssembly, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null");
            int dataOffset = checked((int)stream.Position);
            writer.Write(0x100L); writer.Write(0x110L); writer.Write(0x120L); writer.Write(0x130L);
            writer.Write(tokens[0]); writer.Write(0); writer.Write(tokens[1]); writer.Write(0);
            writer.Write(tokens[2]); writer.Write(0); writer.Write(0x06000001); writer.Write(1);
            stream.Position = 16; writer.Write(dataOffset);
        }
        if (Apply(original, repaired, input, output) != 1) throw new Exception("Fixture must remap the shifted trailing method token.");
        var before = Read(input); var after = Read(output);
        int changedOffset = before.DataOffset + before.Methods * 8 + 16;
        for (int i = 0; i < before.Bytes.Length; i++)
            if (i < changedOffset || i >= changedOffset + 4)
                if (before.Bytes[i] != after.Bytes[i]) throw new Exception("Token repair changed an address, header or unrelated record.");
        if (Apply(repaired, repaired, output, unchanged) != 0 || !File.ReadAllBytes(output).SequenceEqual(File.ReadAllBytes(unchanged)))
            throw new Exception("A no-op token mapping must remain byte-identical.");
        void Reject(string file, Action<byte[]> mutate)
        {
            byte[] bytes = File.ReadAllBytes(input); mutate(bytes); string bad = Path.Combine(directory, file); File.WriteAllBytes(bad, bytes);
            try { Apply(original, repaired, bad, Path.Combine(directory, "must-not-write.db")); }
            catch (InvalidDataException) { return; }
            catch (InvalidOperationException) { return; }
            throw new Exception("Malformed token map was accepted: " + file);
        }
        Reject("bad-map-magic.db", b => b[0] = 0);
        Reject("bad-map-offset.db", b => BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(16, 4), int.MaxValue));
        Reject("bad-map-index.db", b => BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(before.DataOffset + before.Methods * 8 + 4, 4), 9));
        Reject("bad-map-token.db", b => BinaryPrimitives.WriteInt32LittleEndian(b.AsSpan(before.DataOffset + before.Methods * 8, 4), 0x060000FF));
        Console.WriteLine("RECTOFFSET_TOKEN_MAP_TESTS_OK: duplicate signatures, shifted tokens, native address preservation, other assemblies, no-op identity and malformed input rejection");
    }
}
