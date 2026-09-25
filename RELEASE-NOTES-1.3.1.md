Mod Manager 1.3.1: runs on Python 3.9 and newer. The loader is unchanged from 1.2.0.

- **Fix:** on Python 3.10 and older, 1.3.0 stopped at startup with *"module 'hashlib' has no attribute 'file_digest'"*. The manager now hashes files in chunks itself, with the same results, so it runs on **Python 3.9+** (it said 3.11+ before). On Python older than 3.9 it now says which version it needs instead of failing with an error.
- **Sprocket-Mod-Manager-1.3.1.zip:** extract as ModManager beside Sprocket.exe. Existing users replace `modman.pyw` and `loader_setup.py` and keep their configuration and data. Everything else is as in 1.3.0.
- Manual setup is unchanged: use **Sprocket-Mod-Loader-1.2.0.zip** from the 1.2.0 release.

The manager self-test, the nine loader-setup tests and the four metadata-reader tests pass; the new hashing gives the same SHA-256 as before, and the files parse under Python 3.8 and 3.9 grammar. Tested on Python 3.14; not yet run on a real 3.9 or 3.10 install.
