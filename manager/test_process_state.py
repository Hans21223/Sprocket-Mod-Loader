"""Read-only Windows process status: live, exited, and permission failures."""
import ctypes
from pathlib import Path
import runpy
import types
import unittest
from unittest.mock import patch


module = runpy.run_path(str(Path(__file__).with_name('modman.pyw')))
process_exited, pids = module['process_exited'], module['pids']
thread_counts = module['process_thread_counts']


class Kernel:
    def __init__(self, *, handle=123, wait=0x102, code=259, query=True):
        self.handle, self.wait, self.code, self.query = handle, wait, code, query
        self.opened, self.closed = [], []

    def OpenProcess(self, access, inherit, pid):
        self.opened.append((access, inherit, pid))
        return self.handle

    def WaitForSingleObject(self, handle, timeout):
        assert handle == self.handle and timeout == 0
        return self.wait

    def GetExitCodeProcess(self, handle, pointer):
        assert handle == self.handle
        ctypes.cast(pointer, ctypes.POINTER(module['wt'].DWORD)).contents.value = self.code
        return self.query

    def CloseHandle(self, handle):
        self.closed.append(handle)


class SnapshotKernel(Kernel):
    def __init__(self, rows=(), *, snapshot=456, failure=False):
        super().__init__()
        self.rows, self.snapshot, self.failure = list(rows), snapshot, failure
        self.position = 0

    def CreateToolhelp32Snapshot(self, flags, pid):
        assert flags == 2 and pid == 0
        return self.snapshot

    def Process32FirstW(self, snapshot, pointer):
        self.position = 0
        return self.write(pointer)

    def Process32NextW(self, snapshot, pointer):
        self.position += 1
        return self.write(pointer)

    def write(self, pointer):
        if self.position >= len(self.rows):
            ctypes.set_last_error(5 if self.failure else 18)
            return False
        entry = ctypes.cast(pointer, ctypes.POINTER(module['ProcessEntry32W'])).contents
        assert entry.dwSize == ctypes.sizeof(module['ProcessEntry32W'])
        entry.th32ProcessID, entry.cntThreads, entry.szExeFile = self.rows[self.position]
        return True


class ProcessTests(unittest.TestCase):
    def test_live_process_retained_and_query_uses_read_only_rights(self):
        kernel = Kernel()
        self.assertFalse(process_exited(42, kernel))
        self.assertEqual(kernel.opened, [(0x101000, False, 42)])
        self.assertEqual(kernel.closed, [123])

    def test_exited_process_excluded_even_for_still_active_exit_code(self):
        kernel = Kernel(wait=0, code=259)
        self.assertTrue(process_exited(42, kernel))
        self.assertEqual(kernel.closed, [123])

    def test_wait_failure_with_confirmed_exit_code_excludes_process(self):
        kernel = Kernel(wait=0xFFFFFFFF, code=0xC0000005)
        self.assertTrue(process_exited(42, kernel))
        self.assertEqual(kernel.closed, [123])

    def test_access_denied_open_is_retained(self):
        kernel = Kernel(handle=None)
        self.assertFalse(process_exited(42, kernel))
        self.assertEqual(kernel.closed, [])

    def test_access_denied_live_process_with_execution_threads_is_retained(self):
        self.assertFalse(process_exited(42, Kernel(handle=None), thread_count=1))

    def test_access_denied_shell_with_confirmed_zero_threads_is_excluded(self):
        self.assertTrue(process_exited(42, Kernel(handle=None), thread_count=0))

    def test_live_wait_result_wins_over_older_zero_thread_snapshot(self):
        self.assertFalse(process_exited(42, Kernel(), thread_count=0))

    def test_wait_and_query_failure_is_retained(self):
        kernel = Kernel(wait=0xFFFFFFFF, query=False, code=0)
        self.assertFalse(process_exited(42, kernel))
        self.assertEqual(kernel.closed, [123])

    def test_unknown_wait_with_still_active_code_is_retained(self):
        self.assertFalse(process_exited(42, Kernel(wait=0xFFFFFFFF, code=259)))

    def test_pid_listing_keeps_small_live_or_inaccessible_processes(self):
        output = (b'"Sprocket.exe","42","Console","1","48 K"\r\n'
                  b'"Sprocket.exe","43","Console","1","200,000 K"\r\n'
                  b'"Sprocket.exe","44","Console","1","40 K"\r\n'
                  b'"Another.exe","45","Console","1","200,000 K"\r\n')
        status = {42: False, 43: True, 44: False}
        with patch.dict(pids.__globals__, process_exited=lambda pid, **kwargs: status[pid],
                        process_thread_counts=lambda exe: {42: 1, 43: 0, 44: 1}), \
                patch.object(module['subprocess'], 'run', return_value=types.SimpleNamespace(stdout=output)):
            self.assertEqual(pids('Sprocket.exe'), [42, 44])

    def test_kernel_snapshot_filters_names_and_preserves_zero_count(self):
        kernel = SnapshotKernel([(42, 0, 'Sprocket.exe'), (43, 12, 'Sprocket.exe'), (44, 0, 'Another.exe')])
        self.assertEqual(thread_counts('Sprocket.exe', kernel), {42: 0, 43: 12})
        self.assertEqual(kernel.closed, [456])

    def test_failed_snapshot_does_not_report_any_confirmed_zero_threads(self):
        self.assertEqual(thread_counts('Sprocket.exe', SnapshotKernel(snapshot=module['wt'].HANDLE(-1).value)), {})
        kernel = SnapshotKernel([(42, 0, 'Sprocket.exe')], failure=True)
        self.assertEqual(thread_counts('Sprocket.exe', kernel), {})
        self.assertEqual(kernel.closed, [456])

    def test_access_denied_missing_from_snapshot_is_retained(self):
        output = b'"Sprocket.exe","42","Console","1","48 K"\r\n'
        with patch.dict(pids.__globals__, k32=Kernel(handle=None), process_thread_counts=lambda exe: {}), \
                patch.object(module['subprocess'], 'run', return_value=types.SimpleNamespace(stdout=output)):
            self.assertEqual(pids('Sprocket.exe'), [42])


if __name__ == '__main__':
    unittest.main()
