"""Main entrypoint for running package as a module: python -m ema_downloader."""

import sys
from ema_downloader.cli import main

if __name__ == "__main__":
    sys.exit(main())
