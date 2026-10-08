"""Read-only native profile checks; requires pefile and capstone, never starts the game."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import capstone
from capstone.x86_const import X86_OP_IMM
import pefile


PROFILES = {
    '18A9A15B5E5F11898ED4DC34FC3E2D4C12950C3B37AC1FA499E8B00592DEDD56': {
        'version': '0.2.55.5', 'metadata': '6B0D5FB3E62F4F765C2E56289B8DCD8BC81F21FCCEF938D69CEDFFA5D31C52E0',
        'class': 0x4E4160, 'field': 0x4945E0, 'generic': 0x4CF780,
        'field_caller': 0x489B00, 'virtual_caller': 0x4D9A50, 'context_caller': 0x4CF740,
        'field_lookup': 0x5208D8,
    },
    'ADB36B5F04662BE0D40C6E548C797394659A9C0D4B009E3C0E718833ABF90B3A': {
        'version': '0.2.56.0', 'metadata': '1B3052E0BC7391633366F8E246BB61F56B4F21D290A67949CB4E44CB5FEB2912',
        'class': 0x4E46B0, 'field': 0x494B30, 'generic': 0x4CFCD0,
        'field_caller': 0x48A050, 'virtual_caller': 0x4D9FA0, 'context_caller': 0x4CFC90,
        'field_lookup': 0x520E38,
    },
}
PROLOGUES = {'class': '40534883ec20488bd9', 'field': '48895c2408', 'generic': '40555356574154'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class Image:
    def __init__(self, path):
        self.path, self.hash = path, sha(path)
        self.profile = PROFILES[self.hash]
        self.pe = pefile.PE(str(path), fast_load=True)
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT'],
                                                  pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXCEPTION']])
        self.data = self.pe.get_memory_mapped_image()
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.exports = {s.name.decode(): s.address for s in self.pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
        self.ends = {e.struct.BeginAddress: e.struct.EndAddress for e in self.pe.DIRECTORY_ENTRY_EXCEPTION}
        self.disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.disassembler.detail = True

    def instructions(self, rva, size=None):
        end = rva + size if size is not None else self.ends[rva]
        return list(self.disassembler.disasm(self.data[rva:end], self.base + rva))

    def jumps(self, rva, size=None):
        return [i.operands[0].imm - self.base for i in self.instructions(rva, size)
                if (i.mnemonic == 'call' or i.mnemonic.startswith('j')) and len(i.operands) == 1
                and i.operands[0].type == X86_OP_IMM]

    def validate(self, metadata):
        profile = self.profile
        assert sha(metadata) == profile['metadata'], 'Native/metadata fingerprint mismatch'
        for name, prologue in PROLOGUES.items():
            rva, expected = profile[name], bytes.fromhex(prologue)
            assert rva in self.ends, f'{name}: not a PE unwind function entry'
            assert self.data[rva:rva + len(expected)] == expected, f'{name}: unexpected entry bytes'
        assert profile['class'] in self.jumps(self.exports['mono_class_instance_size'])
        assert profile['field_caller'] in self.jumps(self.exports['il2cpp_field_static_get_value'], 5)
        assert profile['field'] in self.jumps(profile['field_caller'])
        assert profile['virtual_caller'] in self.jumps(self.exports['il2cpp_object_get_virtual_method'], 5)
        assert profile['context_caller'] in self.jumps(profile['virtual_caller'])
        assert profile['generic'] in self.jumps(profile['context_caller'])
        assert profile['field_lookup'] in self.jumps(profile['field'])
        caller = profile['context_caller']
        assert self.data[caller + 0x18:caller + 0x34] == bytes.fromhex(
            '488b424048894c24204c89442428488b481048894c2430488d4c2420'), 'Generic context ABI changed'
        assert self.data[profile['class'] + 9:profile['class'] + 16] == bytes.fromhex('f6813501000002')
        assert 'mov rdi, rdx' in [i.mnemonic + ' ' + i.op_str for i in self.instructions(profile['field'])]
        broad = bytes.fromhex('48895c24084889742410574883ec40488b4110')
        assert self.data.find(broad) >= 0, 'Expected broad-signature false-positive evidence absent'
        assert self.data[profile['field']:profile['field'] + len(broad)] != broad
        return {'version': profile['version'], 'native_sha256': self.hash, 'metadata_sha256': sha(metadata),
                'hook_rvas': {name: f"0x{profile[name]:X}" for name in PROLOGUES},
                'checks': '3 unwind entries, 3 prologues, 7 call edges, generic ABI, class flag, field output ABI, false-positive evidence'}

    def normalized(self, name):
        rva = self.profile[name]
        result = []
        for instruction in self.instructions(rva):
            operand = re.sub(r'rip [+-] 0x[0-9a-f]+', 'rip + RELOC', instruction.op_str)
            if (instruction.mnemonic.startswith('j') or instruction.mnemonic == 'call') and len(instruction.operands) == 1:
                if instruction.operands[0].type == X86_OP_IMM:
                    target = instruction.operands[0].imm - self.base
                    operand = 'FieldLookupHelper' if target == self.profile['field_lookup'] else f'RELATIVE:{target - rva:X}'
            result.append((instruction.mnemonic, operand))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True, help='GameAssembly.dll to inspect')
    parser.add_argument('--metadata', type=Path, help='Matching global-metadata.dat')
    parser.add_argument('--compare', type=Path, help='Previous validated GameAssembly.dll')
    args = parser.parse_args()
    image = Image(args.game)
    metadata = args.metadata or args.game.parent / 'Sprocket_Data/il2cpp_data/Metadata/global-metadata.dat'
    result = image.validate(metadata)
    if args.compare:
        previous = Image(args.compare)
        comparisons = {}
        for name in ('class', 'field', 'generic', 'field_caller', 'virtual_caller', 'context_caller', 'field_lookup'):
            old, current = previous.normalized(name), image.normalized(name)
            assert old == current, f'{name}: native instruction or ABI change beyond the verified relocations'
            comparisons[name] = {'instructions': len(current), 'relocation_normalized_identical': True}
        result['compared_version'] = previous.profile['version']
        result['function_comparisons'] = comparisons
    print('PROFILE_VALIDATION_OK')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
