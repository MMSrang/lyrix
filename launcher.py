"""Einstiegspunkt für PyInstaller."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from lyrix.main import main
    sys.exit(main())
