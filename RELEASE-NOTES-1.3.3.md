Mod Manager 1.3.3: never closes without a word. The loader is unchanged from 1.2.0.

Double-clicked, `modman.pyw` runs without a console, so before this release a problem at startup made it seem not to open at all. Now:

- **Opened inside the ZIP:** Windows' ZIP view looks like a folder, but a file opened from it runs alone, without the manager's other files. The manager now says so: drag the `ModManager` folder out of the ZIP first.
- **Python without Tkinter** (the part that draws windows, the "tcl/tk and IDLE" option in the Python installer): the manager says so and how to add it. This message uses Windows' own message box, so it shows even though Tkinter is missing.
- **Any other error**, at startup or from a button: shown in a message box, with the full error saved in `modman-error.log` in the `ModManager` folder (or in Temp if that folder can't be written), to send when asking for help.
- **Python older than 3.9:** the message now uses Windows' message box too.
- **Sprocket-Mod-Manager-1.3.3.zip:** extract `ModManager` anywhere it can stay. Existing users replace `modman.pyw` and keep their configuration and data; `loader_setup.py` and `mod_compat.py` are unchanged from 1.3.2.

On Windows (Python 3.14): the self-test (with new checks for the ZIP case and the error log), the 14 loader-setup tests and the 7 metadata-reader tests pass, and the file parses as Python 3.8 and 3.9. The message boxes themselves weren't clicked through.
