"""PyInstaller entry point for the standalone Windows build (see ema_downloader.spec).

Double-clicking the built exe starts the local web UI and opens the browser;
the console window shows the address and logs, and closing it exits the app.
"""

import multiprocessing
import sys

from ema_downloader.webapp import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
