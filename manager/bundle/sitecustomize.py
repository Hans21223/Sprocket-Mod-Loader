# "Mod Manager.exe" is Python's own pythonw.exe, renamed: signed by the Python Software Foundation, so there's no unsigned
# launcher for antivirus to doubt. Started without a script, it opens the manager beside it.
import os
import sys

if os.path.basename(sys.executable).lower() == "mod manager.exe":
    root = os.path.dirname(sys.executable)
    os.environ.setdefault("TCL_LIBRARY", os.path.join(root, "python", "tcl", "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", os.path.join(root, "python", "tcl", "tk8.6"))
    if not sys.argv[0] and len(sys.argv) <= 1:
        code = 0
        try:
            import runpy
            sys.argv = [os.path.join(root, "modman.pyw")]
            runpy.run_path(sys.argv[0], run_name="__main__")
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 0
        except BaseException:
            import ctypes
            import traceback
            ctypes.windll.user32.MessageBoxW(None, traceback.format_exc(), "Mod Manager", 0x10)
            code = 1
        os._exit(code)  # the manager has closed: Python's own start-up, with no script, mustn't carry on
