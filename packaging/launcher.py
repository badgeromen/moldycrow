"""PyInstaller entry point (the package's __main__ uses a relative import, which a frozen script can't)."""
import sys

from moldycrow.app import main

sys.exit(main())
