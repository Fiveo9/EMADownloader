"""Allow `python -m ema_downloader.webapp` to launch the local web UI."""

import sys

from ema_downloader.webapp import main

if __name__ == "__main__":
    sys.exit(main())
