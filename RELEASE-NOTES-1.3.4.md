Mod Manager 1.3.4: download recovery and clean unmodding. The loader is unchanged from 1.2.0.

- **Download recovery:** if an official download is interrupted, cut off mid-file, or blocked by a network filter or antivirus, setup retries up to three times and explains clearly what happened. If you download the official ZIP in your browser, the manager finds and verifies it in your Downloads folder automatically (even if renamed by the browser with ` (1)` or `%2B`).
- **Remove all mods button:** removes every installed mod, deletes loader leftovers (interop caches, logs, settings), and restores original game files, leaving Sprocket completely unmodded.
- **Sprocket-Mod-Manager-1.3.4.zip:** extract `ModManager` anywhere it can stay. Existing users replace files in `ModManager` and keep their configuration and data.

On Windows (Python 3.14): all 26 unit tests pass, covering download retries, cut-off detection, browser download fallback, and complete clean removal.
